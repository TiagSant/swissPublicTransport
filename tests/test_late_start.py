"""US-62: late start or first ride missed — other departures offered, alarms moved.

Journey followed: from home (about 500 m from Petit-Lancy, Les Esserts) → tram 14 at 07:43 → Genève, Jonction.
A. Position: still at home at 07:38 — the 07:43 can no longer be reached on foot: "You won't make the Tram 14 at
   07:43", departures from where the rider is (not the 07:43). Taking the 07:52: "Leave" rings again at its new time.
B. No position: "I'm leaving later" → departures from home; the one chosen moves the alarms.
C. Position at the stop, but still there 2 min after the tram left: "missed?" — "I'm on board after all" dismisses it."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); DAY = dt.datetime(2026, 11, 16, 7, 0, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: DAY + dt.timedelta(minutes=m)
hm = lambda ms: dt.datetime.fromtimestamp(ms / 1000, tz).strftime("%H:%M")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
JON = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
HOME = (46.1918, 6.1150)                       # ~460 m from the stop
def end(s, m, kind, plat=""): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(m0): return {"journey": {"category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG",
                                  "passList": [{"station": ESS, "departure": fmt(at(m0))}, {"station": JON, "arrival": fmt(at(m0 + 7))}]},
                      "walk": None, "departure": end(ESS, m0, "departure", "A"), "arrival": end(JON, m0 + 7, "arrival")}
RUNS = (38, 43, 47, 52, 57, 62)
def entry(m):
    return {"stop": {"station": ESS, "departure": fmt(at(m)), "departureTimestamp": int(at(m).timestamp()), "platform": "A", "prognosis": {}, "delay": 0},
            "category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG",
            "passList": [{"station": ESS, "departure": fmt(at(m))}, {"station": JON, "arrival": fmt(at(m + 7))}]}
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        hh, mm = map(int, q["time"][0].split(":")); asked = hh * 60 + mm - 7 * 60
        body = {"connections": [{"sections": [ride(m)]} for m in RUNS if m >= asked][:4]}
    elif u.path.endswith("/stationboard"):
        body = {"station": ESS, "stationboard": [entry(m) for m in RUNS] if q.get("id", [""])[0] == ESS["id"] else []}
    else:
        body = {"stations": [dict(ESS, distance=460)]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
def follow(b, where):
    opts = dict(viewport={"width": 390, "height": 1200}, locale="en-US", timezone_id="Europe/Zurich")
    if where: opts.update(permissions=["geolocation"], geolocation={"latitude": where[0], "longitude": where[1], "accuracy": 8})
    ctx = b.new_context(**opts)
    ctx.route("https://transport.opendata.ch/**", api); ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(30).timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }",
                {"tab": "journey", "lang": "en", "settings": {"footMaxMin": 0, "realWalk": False, "prepMin": 5, "marginMin": 1, "alightReminder": False},
                 "journey:from": {"kind": "point", "coord": list(HOME), "near": None},
                 "journey:to": {"kind": "stop", "id": JON["id"], "name": JON["name"], "coord": [JON["coordinate"]["x"], JON["coordinate"]["y"]]}})
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(800)
    pg.locator("#journeyList .jr", has_text="→ 07:50").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    dismiss(pg)
    return ctx, pg
NOTES = []   # trip warnings (title, text), as they rang
def dismiss(pg):
    while pg.is_visible("#alarmBanner"):
        if pg.get_attribute("#alarmBanner", "data-kind") == "trip": NOTES.append((pg.inner_text("#abTitle"), pg.inner_text("#abBody")))
        pg.click("#abOk")
def until(pg, m, where=None):
    while pg.evaluate("Date.now()") < at(m).timestamp() * 1000:
        if where: pg.context.set_geolocation({"latitude": where[0] + (pg.evaluate("Date.now()") % 7) * 1e-7, "longitude": where[1], "accuracy": 8}); pg.wait_for_timeout(120)
        pg.clock.run_for(int(min(20000, at(m).timestamp() * 1000 - pg.evaluate("Date.now()")))); dismiss(pg)
alarm = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
trip = lambda pg: " ".join(pg.locator("#alarmList .trip").first.inner_text().split())

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    # ---- A. still at home: can't make it
    ctx, pg = follow(b, HOME)
    until(pg, 38.5, HOME); pg.wait_for_timeout(1500); pg.clock.run_for(2000); pg.wait_for_timeout(1500)
    dismiss(pg); tx = trip(pg)
    assert "You won’t make the Tram 14 at 07:43" in tx and "Not on the planned ride" in tx, tx
    # PO 23.11.2026: warned once the other departures are found, with the best one
    assert NOTES == [("🔔 You won’t make the Tram 14 at 07:43", "Other departures from where you are. "
                      "Best: Tram 14 at 07:47 · leave 07:39, arrive 07:54. Other choices in the app.")], NOTES
    opts = [" ".join(x.split()) for x in pg.locator("#alarmList .trip-warn .trip-alt").all_inner_texts()]
    assert opts and not any("at 07:43" in o for o in opts) and any("Tram 14 at 07:52" in o for o in opts), opts
    pg.screenshot(path=str(OUT / "late-start.png"))
    pg.locator("#alarmList .trip-alt", has_text="Tram 14 at 07:52").click(); pg.wait_for_timeout(400)
    a = alarm(pg)
    assert hm(a["first"]["sched"]) == "07:52" and not a.get("late") and not a["fired"].get("leave"), (a["first"], a["fired"])
    pg.clock.run_for(int((at(44.1).timestamp() - at(38.5).timestamp()) * 1000) - 4000); pg.wait_for_timeout(500)
    assert pg.is_visible("#alarmBanner") and pg.get_attribute("#alarmBanner", "data-kind") == "leave", "Leave rings for the 07:52"
    print("A position  → “You won’t make the Tram 14 at 07:43”:", opts, "→ 07:52 taken; Leave re-armed")
    ctx.close()

    # ---- B. no position: "I'm leaving later"
    ctx, pg = follow(b, None)
    pg.locator("#alarmList button[data-act=late]").click(); pg.wait_for_selector("#alarmList .trip-warn .trip-alt", timeout=10000)
    tx = trip(pg)
    assert "Leaving later: other departures" in tx, tx
    opts = [" ".join(x.split()) for x in pg.locator("#alarmList .trip-warn .trip-alt").all_inner_texts()]
    assert not any("at 07:43" in o or "at 07:38" in o for o in opts) and any("Tram 14 at 07:47" in o for o in opts), opts   # later only
    pg.locator("#alarmList .trip-alt", has_text="Tram 14 at 07:47").click(); pg.wait_for_timeout(400)
    a = alarm(pg)
    assert hm(a["first"]["sched"]) == "07:47" and not a.get("late") and not a["fired"].get("leave"), a["fired"]
    print("B button    → “I’m leaving later”:", opts, "→ 07:47 taken, alarms moved")
    ctx.close()

    # ---- C. at the stop, still there 2 min after the tram left
    ctx, pg = follow(b, (46.18812, 6.11312))
    until(pg, 46, (46.18812, 6.11312)); pg.wait_for_timeout(1500); pg.clock.run_for(2000); pg.wait_for_timeout(1500)
    dismiss(pg); tx = trip(pg)
    assert "Tram 14 at 07:43 missed?" in tx, tx
    assert NOTES[-1][0] == "🔔 Tram 14 at 07:43 missed?" and NOTES[-1][1].startswith("Other departures from where you are. Best: "), NOTES
    pg.locator("#alarmList button[data-act=late-ok]").click(); pg.wait_for_timeout(300)
    until(pg, 48, (46.18812, 6.11312)); pg.wait_for_timeout(800)
    assert "missed?" not in trip(pg) and alarm(pg).get("lateOk"), trip(pg)
    print("C position  → “Tram 14 at 07:43 missed?”; “I’m on board after all” dismisses it for good")
    ctx.close()
    b.close()
print("errors:", errors); assert not errors
print("OK")
