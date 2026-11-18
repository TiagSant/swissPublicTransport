"""BUG-23: off the vehicle at the get-off stop, before the arrival time announced.

The PO (18.11.2026, ~09:10): tram 14 Les Esserts → Jonction (quai B), then bus 2 from quai D. Waiting for the bus, the
followed journey still said "on board tram 14": the ride lasted until its live arrival announced (09:11), and the tram
came earlier (here 09:09). Now the ride is over once the rider is seen off it at the get-off stop — and moving inside
the vehicle is not getting off (PO):
1. GPS + sensors (his case): steps inside the tram between stops, then to the doors while it comes in: still on board;
   off at quai B and walking to quai D: "done", "Next: Bus 2", well before 09:11.
2. staying on board (the tram stops 20 s at Jonction, a few steps to the doors, then goes on): still on board — the
   times end the ride, as before.
3. off, a step or two, then standing at the stop (same platform): "done" after 30 s there.
4. without GPS, sensors only: 10 s of steps in the tram: still on board; 40 s walking off: "done".
Positions of the stops and platforms real (Les Esserts, Jonction A/B/D); the line between them synthetic.
transport.opendata.ch mocked."""
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
def at(h, m, s=0): return dt.datetime(2026, 11, 18, h, m, s, tzinfo=tz)
A = (46.188095, 6.113098)                              # Petit-Lancy, Les Esserts (quai A)
J, QB, QD = (46.200687, 6.129467), (46.201018, 6.13003), (46.200297, 6.129444)   # Jonction: stop, quai B, quai D
def on_line(f): return (A[0] + (QB[0] - A[0]) * f, A[1] + (QB[1] - A[1]) * f)   # the tram's way, quai B at 1.0
def mix(p, q, f): return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
def st(id_, name, p): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": p[0], "y": p[1]}}
ESSERTS, PLACE, QUIDORT = st("8587418", "Petit-Lancy, Les Esserts", A), st("8587419", "Petit-Lancy, place", on_line(.35)), st("8587420", "Petit-Lancy, Quidort", on_line(.65))
JONCTION, MUSEE = st("8587062", "Genève, Jonction", J), st("8592868", "Genève, Musée d'ethnographie", (46.19795, 6.13641))
# timetable 08:58 → 09:05; live +6 (Jonction announced 09:11). Bus 2 09:11 +3 from quai D.
TRAM = [(ESSERTS, at(8, 58)), (PLACE, at(9, 0)), (QUIDORT, at(9, 1)), (JONCTION, at(9, 5))]
LATE = 6
def prog(kind, t, d): return {kind: fmt(t + dt.timedelta(minutes=d))} if d else {}
def end(s, t, kind, plat, d=0): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": prog(kind, t, d), "delay": d or None}
def connection():
    pl = [{"station": ESSERTS, "departure": fmt(TRAM[0][1])}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in TRAM[1:-1]] + [{"station": JONCTION, "arrival": fmt(TRAM[-1][1])}]
    tram = {"journey": {"category": "T", "number": "14", "to": "Meyrin-Gravière", "operator": "TPG", "passList": pl}, "walk": None,
            "departure": end(ESSERTS, TRAM[0][1], "departure", "A", LATE), "arrival": end(JONCTION, TRAM[-1][1], "arrival", "B", LATE)}
    walk = {"journey": None, "walk": {"duration": 60}, "departure": end(JONCTION, at(9, 5), "departure", ""), "arrival": end(JONCTION, at(9, 6), "arrival", "")}
    bus = {"journey": {"category": "B", "number": "2", "to": "Genève-Plage", "operator": "TPG",
                       "passList": [{"station": JONCTION, "departure": fmt(at(9, 11))}, {"station": MUSEE, "arrival": fmt(at(9, 14))}]}, "walk": None,
           "departure": end(JONCTION, at(9, 11), "departure", "D", 3), "arrival": end(MUSEE, at(9, 14), "arrival", "K", 3)}
    return {"sections": [tram, walk, bus]}
def entry(cat, num, to, here, t0, d, nxt, plat):
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": plat, "prognosis": prog("departure", t0, d), "delay": d},
            "passList": [{"station": here}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": prog("arrival", t, d)} for s, t in nxt]}
def board(stop_id):
    if stop_id == ESSERTS["id"]: return [entry("T", "14", "Meyrin-Gravière", ESSERTS, TRAM[0][1], LATE, TRAM[1:], "A")]
    if stop_id == JONCTION["id"]: return [entry("B", "2", "Genève-Plage", JONCTION, at(9, 11), 3, [(MUSEE, at(9, 14))], "D")]
    return []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [connection()] if q.get("from", [""])[0] == ESSERTS["id"] else []}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": board(q.get("id", [""])[0])}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
# the tram really: leaves 09:04, place 09:06 (15 s), Quidort 09:07 (15 s), Jonction quai B 09:09:00-09:09:20, then on
TRAMWAY = [(at(9, 4), 0, False), (at(9, 6), .35, True), (at(9, 6, 15), .35, False), (at(9, 7), .65, True), (at(9, 7, 15), .65, False),
           (at(9, 9), 1.0, True), (at(9, 9, 20), 1.0, False), (at(9, 10, 20), 1.15, True)]
def tram_at(t):
    if t <= TRAMWAY[0][0]: return 0, False
    for (t0, f0, s0), (t1, f1, _) in zip(TRAMWAY, TRAMWAY[1:]):
        if t0 <= t < t1: return (f0, True) if s0 else (f0 + (f1 - f0) * (t - t0).total_seconds() / (t1 - t0).total_seconds(), False)
    return TRAMWAY[-1][1], True
FEED = """([kind, secs]) => { const n = Math.round(secs * 1000 / 16);
  for (let i = 0; i < n; i++) { const t = (window.__ft = (window.__ft || 0) + 0.016); let z = 9.81;
    if (kind === 'walk') z += 2.5 * Math.sin(2 * Math.PI * 1.9 * t) + (Math.random() - 0.5) * 0.6;
    else if (kind === 'ride') z += 0.3 * Math.sin(2 * Math.PI * 0.4 * t) + (Math.random() - 0.5) * 0.5;
    else z += (Math.random() - 0.5) * 0.04;
    window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.2, y: 0.1, z }, interval: 16 })); } }"""
errors = []
def session(b, gps=True):
    kw = dict(permissions=["geolocation"], geolocation={"latitude": A[0], "longitude": A[1], "accuracy": 10}) if gps else {}
    ctx = b.new_context(viewport={"width": 390, "height": 1400}, locale="fr-CH", timezone_id="Europe/Zurich", **kw)
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(8, 50).timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "motionSensors": True}, "journey:from": STOP(ESSERTS), "journey:to": STOP(MUSEE)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    return ctx, pg
def now(pg): return dt.datetime.fromtimestamp(pg.evaluate("Date.now()") / 1000, tz)
def live(pg, ctx, until, rider, gps=True, step=5):
    """rider(t) → (position, motion kind); GPS and motion fed every `step` s"""
    k = 0
    while now(pg) < until:
        t = now(pg); p, kind = rider(t); k += 1
        if gps: ctx.set_geolocation({"latitude": p[0] + k * 1e-7, "longitude": p[1], "accuracy": 10})
        pg.evaluate(FEED, [kind, step]); pg.clock.run_for(step * 1000); pg.wait_for_timeout(60)
        while pg.is_visible("#alarmBanner"): pg.click("#abOk")
def tram_chip(pg): return pg.locator("#alarmList .trip .tl.ride").first.locator(".chip").inner_text().strip()
card = lambda pg: " ".join(pg.locator("#alarmList .alarm").first.inner_text().split())
def state(pg):
    c = card(pg)
    return "on board" if "À bord : Tram 14" in c else "next bus 2" if "Prochain : Bus 2" in c else c[:120]
def riding(walks=(), off=None, stay=None):
    """the rider in the tram, with steps at the times in `walks`; `off` = (start, end): off at quai B, walking to quai D;
    `stay`: off at quai B at that time, a step or two, then standing"""
    def rider(t):
        if off and t >= off[0]:
            f = min(1, (t - off[0]).total_seconds() / (off[1] - off[0]).total_seconds())
            return mix(QB, QD, f), "walk" if t < off[1] else "still"
        if stay and t >= stay: return QB, "walk" if t < stay + dt.timedelta(seconds=3) else "still"
        f, stopped = tram_at(t)
        if t < TRAMWAY[0][0]: return A, "still"
        kind = "walk" if any(s <= t < e for s, e in walks) else "still" if stopped else "ride"
        return on_line(f), kind
    return rider
def coarse(pg, ctx, gps=True):   # 08:50 → 09:03:30, waiting at Les Esserts
    while now(pg) < at(9, 3, 30):
        if gps: ctx.set_geolocation({"latitude": A[0], "longitude": A[1], "accuracy": 10})
        pg.evaluate(FEED, ["still", 4]); pg.clock.run_for(30000); pg.wait_for_timeout(60)
        while pg.is_visible("#alarmBanner"): pg.click("#abOk")
S = lambda h, m, s=0: at(h, m, s)
fails = []
def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond: fails.append(msg)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    # 1. the PO's case
    print("1. GPS + sensors: off at quai B, walking to quai D")
    ctx, pg = session(b); coarse(pg, ctx)
    rider = riding(walks=[(S(9, 5, 30), S(9, 5, 40)), (S(9, 8, 50), S(9, 8, 55))], off=(S(9, 9, 10), S(9, 9, 55)))
    live(pg, ctx, S(9, 5, 50), rider)
    check(tram_chip(pg) == "à bord" and state(pg) == "on board", f"09:05:50 steps in the tram between stops → on board ({tram_chip(pg)}, {state(pg)})")
    live(pg, ctx, S(9, 9, 10), rider)
    check(tram_chip(pg) == "à bord" and state(pg) == "on board", f"09:09:10 steps to the doors, tram in at quai B → on board ({tram_chip(pg)}, {state(pg)})")
    live(pg, ctx, S(9, 9, 40), rider)
    check(tram_chip(pg) == "fait" and state(pg) == "next bus 2", f"09:09:40 off, walking to quai D → done, next: bus 2 ({tram_chip(pg)}, {state(pg)})")
    pg.screenshot(path=str(OUT / "off-at-change.png"), full_page=True)
    ctx.close()

    # 2. staying on board
    print("2. GPS + sensors: staying on board past Jonction")
    ctx, pg = session(b); coarse(pg, ctx)
    rider = riding(walks=[(S(9, 8, 50), S(9, 8, 55)), (S(9, 9, 5), S(9, 9, 10))])
    live(pg, ctx, S(9, 10, 40), rider)
    check(tram_chip(pg) == "à bord" and state(pg) == "on board", f"09:10:40 the tram went on, rider aboard → on board ({tram_chip(pg)}, {state(pg)})")
    live(pg, ctx, S(9, 11, 40), rider)
    check(tram_chip(pg) == "fait", f"09:11:40 past the arrival announced → done by the times, as before ({tram_chip(pg)})")
    ctx.close()

    # 3. off and standing on the same platform
    print("3. GPS + sensors: off, standing at quai B")
    ctx, pg = session(b); coarse(pg, ctx)
    rider = riding(stay=S(9, 9, 10))
    live(pg, ctx, S(9, 9, 25), rider)
    check(tram_chip(pg) == "à bord", f"09:09:25 just off (15 s) → not yet ({tram_chip(pg)})")
    live(pg, ctx, S(9, 9, 50), rider)
    check(tram_chip(pg) == "fait" and state(pg) == "next bus 2", f"09:09:50 still at the stop 50 s → done ({tram_chip(pg)}, {state(pg)})")
    ctx.close()

    # 4. no GPS
    print("4. sensors only (no GPS)")
    ctx, pg = session(b, gps=False); coarse(pg, ctx, gps=False)
    rider = riding(walks=[(S(9, 7, 40), S(9, 7, 50))], off=(S(9, 9, 10), S(9, 9, 50)))
    live(pg, ctx, S(9, 8, 0), rider, gps=False)
    check(tram_chip(pg) == "à bord", f"09:08:00 10 s of steps in the tram → on board ({tram_chip(pg)})")
    live(pg, ctx, S(9, 9, 10), rider, gps=False)
    check(tram_chip(pg) == "à bord", f"09:09:10 → on board ({tram_chip(pg)})")
    live(pg, ctx, S(9, 9, 50), rider, gps=False)
    check(tram_chip(pg) == "fait" and state(pg) == "next bus 2", f"09:09:50 walking off 40 s → done ({tram_chip(pg)}, {state(pg)})")
    ctx.close(); b.close()
print("errors:", errors); assert not errors
assert not fails, fails
print("OK")
