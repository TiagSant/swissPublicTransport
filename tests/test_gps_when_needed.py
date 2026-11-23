"""US-69: the GPS only when it helps; the motion sensors follow the ride in between.

A tram followed with the sensors on: the GPS is switched on and off (recorded by wrapping navigator.geolocation).
- until 2 min after it left: on (which run was boarded);
- then, in a vehicle as the sensors say: off ("GPS en veille" shown);
- stopped 2 min in traffic: on after 90 s (a doubt), off again once moving;
- from 3 min before leaving the stop before the get-off stop: on — the reminder rings when leaving it;
- the stops served sensed by the sensors (still 20 s, then moving): a delay reported afterwards does not put a stop
  served back to come.
Without sensor data: on all the ride, as before.
Synthetic line (stops 2 ... 7 on a straight 6 km line from Confignon, croisée, real); transport.opendata.ch mocked."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def at(h, m, s=0): return dt.datetime(2026, 11, 17, h, m, s, tzinfo=tz)
A, Z = (46.178810, 6.089810), (46.2168, 6.1448)
def on_line(f): return (A[0] + (Z[0] - A[0]) * f, A[1] + (Z[1] - A[1]) * f)
def st(id_, name, f): p = on_line(f); return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": p[0], "y": p[1]}}
FIRST = {"id": "8587386", "name": "Confignon, croisée", "coordinate": {"type": "WGS84", "x": A[0], "y": A[1]}}
STOPS = [(st("9000002", "Arrêt 2", .15), at(8, 32)), (st("9000003", "Arrêt 3", .30), at(8, 34)), (st("9000004", "Arrêt 4", .50), at(8, 36)),
         (st("9000005", "Arrêt 5", .70), at(8, 38)), (st("9000006", "Arrêt 6", .85), at(8, 40))]
LAST = (st("9000007", "Arrêt 7", 1.0), at(8, 42))
# the tram is held 2 min in traffic after Arrêt 3: +2 reported from 08:35 — for Arrêt 3 too, though it was just left
S = {"delay": 0}
def prog(kind, t, d): return {kind: fmt(t + dt.timedelta(minutes=d))} if d else {}
def connection():
    pl = [{"station": FIRST, "departure": fmt(at(8, 30))}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in STOPS] + [{"station": LAST[0], "arrival": fmt(LAST[1])}]
    return {"sections": [{"journey": {"category": "T", "number": "14", "to": "Meyrin-Gravière", "operator": "TPG", "passList": pl}, "walk": None,
             "departure": {"station": FIRST, "departure": fmt(at(8, 30)), "departureTimestamp": int(at(8, 30).timestamp()), "platform": "A", "prognosis": {}, "delay": None},
             "arrival": {"station": LAST[0], "arrival": fmt(LAST[1]), "arrivalTimestamp": int(LAST[1].timestamp()), "platform": "", "prognosis": {}, "delay": None}}]}
def board():
    d = S["delay"]
    return [{"category": "T", "number": "14", "to": "Meyrin-Gravière", "operator": "TPG",
             "stop": {"station": FIRST, "departure": fmt(at(8, 30)), "departureTimestamp": int(at(8, 30).timestamp()), "platform": "A", "prognosis": {}, "delay": 0},
             "passList": [{"station": FIRST}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": prog("arrival", t, d if t >= at(8, 34) else 0)} for s, t in STOPS + [LAST]]}]
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [connection()]}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": board() if q.get("id") == [FIRST["id"]] else []}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
# where the tram is: (fraction of the line, still?) — 20 s at each stop, 2 min in traffic at .38 (08:35-08:37)
PLAN = [(at(8, 30), 0, False), (at(8, 32), .15, True), (at(8, 32, 20), .15, False), (at(8, 34), .30, True), (at(8, 34, 20), .30, False),
        (at(8, 35), .38, True), (at(8, 37), .38, False), (at(8, 38), .50, True), (at(8, 38, 20), .50, False), (at(8, 40), .70, True),
        (at(8, 40, 20), .70, False), (at(8, 42), .85, True), (at(8, 42, 20), .85, False), (at(8, 44), 1.0, True)]
def where(t):
    if t <= PLAN[0][0]: return 0, "still"
    for (t0, f0, s0), (t1, f1, _) in zip(PLAN, PLAN[1:]):
        if t0 <= t < t1: return (f0, "still") if s0 else (f0 + (f1 - f0) * (t - t0).total_seconds() / (t1 - t0).total_seconds(), "ride")
    return 1.0, "still"
FEED = """([kind, secs]) => { const n = Math.round(secs * 1000 / 16);
  for (let i = 0; i < n; i++) { const t = (window.__ft = (window.__ft || 0) + 0.016); let z = 9.81;
    if (kind === 'ride') z += 0.3 * Math.sin(2 * Math.PI * 0.4 * t) + (Math.random() - 0.5) * 0.5;
    else z += (Math.random() - 0.5) * 0.04;
    window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.2, y: 0.1, z }, interval: 16 })); } }"""
WRAP = """(() => { const g = navigator.geolocation, w = g.watchPosition.bind(g), c = g.clearWatch.bind(g); window.__gpsLog = [];
  g.watchPosition = (...a) => { window.__gpsLog.push([Date.now(), 'on']); return w(...a); };
  g.clearWatch = id => { window.__gpsLog.push([Date.now(), 'off']); return c(id); }; })();"""
errors = []
def session(b, motion):
    ctx = b.new_context(viewport={"width": 390, "height": 1000}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": A[0], "longitude": A[1], "accuracy": 10})
    ctx.add_init_script(WRAP)
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(8, 28, 30).timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "motionSensors": motion}, "journey:from": STOP(FIRST), "journey:to": STOP(LAST[0])}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    return ctx, pg
def now(pg): return dt.datetime.fromtimestamp(pg.evaluate("Date.now()") / 1000, tz)
RANG = []
def ride_until(pg, ctx, until, motion=True):
    while now(pg) < until:
        t = now(pg); f, kind = where(t); p = on_line(f)
        ctx.set_geolocation({"latitude": p[0], "longitude": p[1], "accuracy": 10})
        if t >= at(8, 35): S["delay"] = 2
        if motion: pg.evaluate(FEED, [kind, 10])
        pg.clock.run_for(10000); pg.wait_for_timeout(100)
        while pg.is_visible("#alarmBanner"): RANG.append((now(pg), pg.inner_text("#abTitle"))); pg.click("#abOk")
def gps_on(pg):   # the GPS on now? (last switch)
    log = pg.evaluate("window.__gpsLog")
    return bool(log) and log[-1][1] == "on"
card = lambda pg: " ".join(pg.locator("#alarmList .alarm").first.inner_text().split())
def passed(pg): return pg.evaluate("""() => [...document.querySelectorAll('#alarmList .trip .via li')].map(li => li.classList.contains('passed'))""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx, pg = session(b, True)
    ride_until(pg, ctx, at(8, 31, 0))
    assert gps_on(pg), pg.evaluate("window.__gpsLog")
    print("08:31 boarding     → GPS on")
    ride_until(pg, ctx, at(8, 34, 40))
    assert not gps_on(pg) and "GPS en veille" in card(pg) and "dans un véhicule" in card(pg), (pg.evaluate("window.__gpsLog"), card(pg))
    print("08:34 between stops→ GPS off · 'GPS en veille'")
    ride_until(pg, ctx, at(8, 35, 50))
    pv = passed(pg)
    assert pv[:2] == [True, True] and pv[2] is False, pv   # Arrêt 3 "08:36" by time, served by the sensors at 08:34
    print("08:35 delay +2     → Arrêt 3 stays passed (served, sensed):", pv)
    ride_until(pg, ctx, at(8, 36, 50))
    assert gps_on(pg), pg.evaluate("window.__gpsLog")
    print("08:36 traffic 90 s → GPS on")
    ride_until(pg, ctx, at(8, 38, 0))
    assert not gps_on(pg), pg.evaluate("window.__gpsLog")
    print("08:38 moving again → GPS off")
    ride_until(pg, ctx, at(8, 39, 20))   # Arrêt 6 at 08:42 live: on from 08:39
    assert gps_on(pg), pg.evaluate("window.__gpsLog")
    print("08:39 approach     → GPS on (3 min before leaving Arrêt 6, 08:42 live)")
    ride_until(pg, ctx, at(8, 43, 30))
    off = [t.strftime("%H:%M:%S") for t, x in RANG if "descendez" in x]
    assert off and "08:42:20" <= off[0] <= "08:43:10", off
    print("get-off reminder   →", off[0], "(leaving Arrêt 6, 08:42:20)")
    log = pg.evaluate("window.__gpsLog"); on = 0; last = None
    for ms, k in log:
        if k == "on": last = ms
        elif last: on += ms - last; last = None
    if last: on += pg.evaluate("Date.now()") - last
    print(f"GPS on {on / 60000:.1f} min of the 13.5-min ride ({len(log)} switches)")
    ctx.close()

    # without the sensors: on all the ride, as before
    ctx, pg = session(b, False)
    RANG.clear(); ride_until(pg, ctx, at(8, 39, 0), motion=False)
    log = pg.evaluate("window.__gpsLog")
    assert log and log[-1][1] == "on" and all(k == "on" for _, k in log if _ >= at(8, 30).timestamp() * 1000), log
    print("no sensors         → GPS on all the ride")
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
