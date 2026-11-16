"""US-66: walking or riding, from the phone's own motion sensors (no Google service, nothing sent).

The PO's case (16.11.2026, 19:05): following tram 17 Plainpalais → Bel-Air then tram 14 to Les Esserts, he walked
instead. Nothing noticed it. Now: still walking a minute after tram 17 left → "You're on foot: tram 17 left without
you", with other ways from there — walking to Stand for tram 14 among them (US-65). Riding (no steps) or the setting
off: nothing of the kind. The sensors' reading is shown on the followed journey.
Motion is simulated with DeviceMotion events (accelerometer magnitude): walking = a 1.9 Hz swing of ±2.5 m/s²;
riding = small irregular vibrations; still = almost nothing. transport.opendata.ch is mocked; stops are real."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAINPALAIS = st("8587907", "Genève, Plainpalais", 46.19809, 6.14305)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20424, 6.14206)
STAND = st("8592906", "Genève, Stand", 46.2036, 6.14105)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
S = {"base": None}
def at(m): return S["base"] + dt.timedelta(minutes=m)
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    calls = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, b, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(b, t1, "arrival", "")}
def trip(m):   # tram 17 at m (Plainpalais → Bel-Air +4), walk 2, tram 14 at m+8 (Stand +2, Jonction +5, Les Esserts +12)
    return {"sections": [ride("T", "17", "Annemasse, Perrier-Aubrac", PLAINPALAIS, BELAIR, at(m), at(m + 4), "C", "F"), walk(BELAIR, BELAIR, at(m + 4), at(m + 6)),
                         ride("T", "14", "Bernex-Vailly", BELAIR, ESSERTS, at(m + 8), at(m + 20), "B", "B", mid=[(STAND, at(m + 10)), (JONCTION, at(m + 13))])]}
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        hm = q.get("time", ["19:00"])[0]; m = int(hm[:2]) * 60 + int(hm[3:5]) - (19 * 60)
        body = {"connections": [trip(7)] if m < 7 else [trip(12)]}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": []}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
norm = lambda s: " ".join(s.split())
FEED = """([kind, secs]) => { const n = Math.round(secs * 1000 / 16);
  for (let i = 0; i < n; i++) { const t = (window.__ft = (window.__ft || 0) + 0.016); let z = 9.81;
    if (kind === 'walk') z += 2.5 * Math.sin(2 * Math.PI * 1.9 * t) + (Math.random() - 0.5) * 0.6;
    else if (kind === 'ride') z += 0.3 * Math.sin(2 * Math.PI * 0.4 * t) + (Math.random() - 0.5) * 0.5;
    else z += (Math.random() - 0.5) * 0.04;
    window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.2, y: 0.1, z }, interval: 16 })); } }"""

errors = []
def session(b, settings):
    S["base"] = dt.datetime(2026, 11, 16, 19, 0, tzinfo=tz)
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=S["base"].timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": settings, "journey:from": STOP(PLAINPALAIS), "journey:to": STOP(ESSERTS)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(500)
    cards = pg.locator("#journeyList .jr")
    n = next(i for i, c in enumerate(cards.all_inner_texts()) if "17" in c)   # the API's journey (tram 17, then 14)
    cards.nth(n).click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    return ctx, pg
def run(pg, ms):
    pg.clock.run_for(ms); pg.wait_for_timeout(250)
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
def move(pg, kind, secs):   # in 10-s steps, the clock moving with the samples
    for _ in range(int(secs // 10)): pg.evaluate(FEED, [kind, 10]); run(pg, 10000)
card = lambda pg: norm(pg.locator("#alarmList .alarm").first.inner_text())

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ON = {"footMaxMin": 15, "realWalk": False, "alightReminder": False}

    # 1. walking instead of tram 17 (19:07): noticed a minute after it left, other ways from there
    ctx, pg = session(b, ON)
    run(pg, 7 * 60000 + 5000)                     # 19:07:05
    move(pg, "walk", 120)                         # to 19:09:05
    c = card(pg)
    assert "Capteurs : 🚶 à pied" in c, c
    assert "Vous êtes à pied : le Tram 17 de 19:07 est parti sans vous" in c, c
    pg.wait_for_function("() => document.querySelector('#alarmList .trip-warn') && document.querySelector('#alarmList .trip-warn').innerText.includes('Stand')", timeout=10000)
    w = norm(pg.locator("#alarmList .trip-warn").first.inner_text())
    assert "🚶 Genève, Stand › Tram 14" in w, w
    pg.screenshot(path=str(OUT / "walking-sensors.png"))
    print("walking     →", w[:160])
    ctx.close()

    # 2. on board (vibrations, no steps): nothing of the kind; first still at the stop
    ctx, pg = session(b, ON)
    run(pg, 6 * 60000)                            # 19:06
    move(pg, "still", 20)
    assert "Capteurs : immobile" in card(pg), card(pg)
    move(pg, "ride", 160)                         # 19:06:20 → 19:09:00
    c = card(pg)
    assert "Capteurs : en mouvement, sans pas" in c and "Vous êtes à pied" not in c, c
    ctx.close()
    print("on board    → 'en mouvement, sans pas', no warning")

    # 3. setting off: no reading, no warning
    ctx, pg = session(b, dict(ON, motionSensors=False))
    run(pg, 7 * 60000 + 5000); move(pg, "walk", 120)
    c = card(pg)
    assert "Capteurs" not in c and "Vous êtes à pied" not in c, c
    ctx.close()
    print("setting off → nothing")
    b.close()
print("errors:", errors); assert not errors
print("OK")
