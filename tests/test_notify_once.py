"""BUG-26: a notification rings once, even after the phone slept or Android closed the page.

The PO received the notifications while the app was in the background, then all of them again, at once, when he
opened it. Two causes, both replayed here with the network held (as on a phone asleep):
1. Live refreshes piled up (one a minute, each waiting for the network) and each one, once the network came back,
   saved the alarms as they were when it started: the "rang" marks set meanwhile were lost and the alarms rang again.
2. A warning rang in a live refresh, then the refresh waited for its alternatives and the page was closed before it
   saved: the warning's mark was lost and it rang again when the app was opened."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
tz = ZoneInfo("Europe/Zurich"); DAY = dt.datetime(2026, 3, 10, 14, 0, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: DAY + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
CRO = st("8592001", "Confignon, croisée", 46.1742, 6.0858)
JON = st("8592002", "Genève, Jonction", 46.200687, 6.129467)
def end(s, m, kind): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": "A" if kind == "departure" else "", "prognosis": {}, "delay": None}
T14 = {"journey": {"category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG",
                   "passList": [{"station": CRO, "departure": fmt(at(40))}, {"station": JON, "arrival": fmt(at(52))}]},
       "walk": None, "departure": end(CRO, 40, "departure"), "arrival": end(JON, 52, "arrival")}
def entry(m):
    return {"stop": {"station": CRO, "departure": fmt(at(m)), "departureTimestamp": int(at(m).timestamp()), "platform": "A", "prognosis": {"departure": fmt(at(m))}, "delay": 0},
            "category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG",
            "passList": [{"station": CRO, "departure": fmt(at(m))}, {"station": JON, "arrival": fmt(at(m + 12))}]}
S = {"gone": False}
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        body = {"connections": [{"sections": [T14]}]}
    elif u.path.endswith("/stationboard"):
        mins = [m for m in (30, 35, 40, 45, 50, 55, 60, 65) if not (S["gone"] and m == 40)]
        body = {"station": CRO, "stationboard": [entry(m) for m in mins] if q.get("id", [""])[0] == CRO["id"] else []}
    else:
        body = {"stations": [CRO]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}

# Notifications counted in storage (kept when the page is opened again); requests held on demand, as with no network
INIT = """
Object.defineProperty(Navigator.prototype, 'serviceWorker', { get: () => undefined });
window.Notification = class { constructor(title) { const n = JSON.parse(localStorage.getItem('__notes') || '[]'); n.push(title); localStorage.setItem('__notes', JSON.stringify(n)); }
  static get permission() { return 'granted'; } static requestPermission() { return Promise.resolve('granted'); } };
const realFetch = window.fetch.bind(window);
window.__hold = null; window.__held = [];
window.fetch = (url, init) => window.__hold && String(url).includes(window.__hold)
  ? new Promise(res => window.__held.push(() => res(realFetch(url, Object.assign({}, init, { signal: undefined })))))
  : realFetch(url, init);
window.__release = () => { window.__hold = null; const h = window.__held.splice(0); h.forEach(go => go()); return h.length; };
"""
errors = []
def start(b):
    ctx = b.new_context(viewport={"width": 390, "height": 1100}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.add_init_script(INIT)
    ctx.route("https://transport.opendata.ch/**", api); ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(20).timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }",
                {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "motionSensors": False}, "journey:from": STOP(CRO), "journey:to": STOP(JON)})
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(1000)
    pg.locator("#journeyList .jr").first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pg.clock.run_for(70000); pg.wait_for_timeout(1000)   # a first live refresh, network up
    pg.evaluate("localStorage.setItem('__notes', '[]')")
    return ctx, pg
notes = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('__notes') || '[]')")
fired = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].fired")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # ---- 1. phone asleep 18 min: no network, the alarms ring meanwhile; then the network comes back
    ctx, pg = start(b)
    pg.evaluate("window.__hold = 'transport.opendata.ch'")
    for _ in range(18): pg.clock.run_for(60000)              # 14:21 → 14:39: "Get ready" (14:29) and "Leave" (14:39)
    rang = notes(pg)
    assert len(rang) == 2, rang
    held = pg.evaluate("window.__held.length")
    assert held <= 1 + 18 // 5, f"{held} requests waiting: live refreshes piled up"   # one at a time; a new one after 5 min stuck
    pg.evaluate("window.__release()"); pg.wait_for_timeout(2000)
    pg.clock.run_for(10000); pg.wait_for_timeout(1000)        # the app opened: the refresh ends, the clock ticks
    after = notes(pg)
    assert after == rang, f"rang again: {after}"
    f = fired(pg); assert f.get("ready") and f.get("leave"), f
    ctx.close(); print("asleep      → rang once each:", rang, f"({held} requests waiting)")

    # ---- 2. the tram disappears: the warning rings, then the page is closed while the replacement is looked for
    ctx, pg = start(b)
    S["gone"] = True
    pg.evaluate("window.__hold = '/connections'")             # the search for what replaces it never ends
    pg.clock.run_for(70000); pg.wait_for_timeout(1500)
    rang = notes(pg)
    assert len(rang) == 1 and "supprimé" in rang[0], rang
    pg.reload(); pg.wait_for_timeout(1500)                    # Android closed the page; the rider opens the app
    pg.clock.run_for(70000); pg.wait_for_timeout(1500)
    after = notes(pg)
    assert after == rang, f"rang again: {after}"
    ctx.close(); print("page closed → the warning rang once:", rang)
    S["gone"] = False
    b.close()
print("errors:", errors); assert not errors
print("OK")
