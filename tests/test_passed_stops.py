"""BUG-19: the stops a followed ride has passed — no stop just left shown "to come" again.

PO (17.11.2026): "sometimes the stops passed show again as to come, just after leaving the stop". Before, they were
worked out afresh at each display: by time (a delay reported a minute later moved them forward again) or within 60 m
of a stop (lost once 60 m past it). Now: the GPS placed along the line wins when fresh; a stop once passed stays so.
Tram 14 Les Esserts 08:30 → Place 08:32 → Quidort 08:34 → Jonction 08:37, late without its delay reported at first.
1. 08:32:30: the time says Place is passed, the GPS 100 m before it: Place still to come (the GPS wins).
2. 08:33:30: the GPS 90 m past Place (beyond the old 60 m), +3 min now reported (Place "08:35"): Place passed.
3. 08:34:00: a poor fix 70 m back before Place: Place stays passed (memory).
4. without GPS: by time, as before.
Stop ids / positions: Les Esserts, Quidort, Jonction real; "Petit-Lancy, place" approximate. transport.opendata.ch mocked."""
import os, json, math, datetime as dt
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
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
PLACE = st("8592896", "Petit-Lancy, place", 46.1912, 6.1172)
QUIDORT = st("8592905", "Petit-Lancy, Quidort", 46.1945, 6.1215)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
C = lambda s: (s["coordinate"]["x"], s["coordinate"]["y"])
def at(h, m, s=0): return dt.datetime(2026, 11, 17, h, m, s, tzinfo=tz)
BASE = at(8, 28)
S = {"delay": 0}
def prog(kind, t, d): return {kind: fmt(t + dt.timedelta(minutes=d))} if d else {}
def calls(d): return [(PLACE, at(8, 32)), (QUIDORT, at(8, 34)), (JONCTION, at(8, 37))]
def connection():
    pl = [{"station": ESSERTS, "departure": fmt(at(8, 30))}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in calls(0)[:-1]] + [{"station": JONCTION, "arrival": fmt(at(8, 37))}]
    return {"sections": [{"journey": {"category": "T", "number": "14", "to": "Meyrin-Gravière", "operator": "TPG", "passList": pl}, "walk": None,
                          "departure": {"station": ESSERTS, "departure": fmt(at(8, 30)), "departureTimestamp": int(at(8, 30).timestamp()), "platform": "A", "prognosis": {}, "delay": None},
                          "arrival": {"station": JONCTION, "arrival": fmt(at(8, 37)), "arrivalTimestamp": int(at(8, 37).timestamp()), "platform": "", "prognosis": {}, "delay": None}}]}
def board():
    d = S["delay"]
    return [{"category": "T", "number": "14", "to": "Meyrin-Gravière", "operator": "TPG",
             "stop": {"station": ESSERTS, "departure": fmt(at(8, 30)), "departureTimestamp": int(at(8, 30).timestamp()), "platform": "A", "prognosis": prog("departure", at(8, 30), d), "delay": d},
             "passList": [{"station": ESSERTS}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": prog("arrival", t, d)} for s, t in calls(d)]}]
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [connection()]}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": board() if q.get("id") == [ESSERTS["id"]] else []}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": list(C(s))}
def toward(a, b, metres):   # a point `metres` from a toward b (negative: before a)
    d = math.dist(a, b) * 111195   # rough, fine for a direction
    f = metres / d
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
errors = []
def session(b, gps):
    kw = {"permissions": ["geolocation"], "geolocation": {"latitude": C(ESSERTS)[0], "longitude": C(ESSERTS)[1], "accuracy": 10}} if gps else {}
    ctx = b.new_context(viewport={"width": 390, "height": 1000}, locale="fr-CH", timezone_id="Europe/Zurich", **kw)
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=BASE.timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "motionSensors": False}, "journey:from": STOP(ESSERTS), "journey:to": STOP(JONCTION)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    return ctx, pg
def go(pg, ctx, until, pos=None):   # to `until`, the position (if any) given 5 s before, as a phone would keep sending it
    now = pg.evaluate("Date.now()") / 1000
    pg.clock.run_for(int((until.timestamp() - 5 - now) * 1000)); pg.wait_for_timeout(200)
    if pos: ctx.set_geolocation({"latitude": pos[0], "longitude": pos[1], "accuracy": 10})
    pg.clock.run_for(5000); pg.wait_for_timeout(300)
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pg.clock.run_for(20000); pg.wait_for_timeout(300)   # the card redrawn
def stops(pg):   # [(name, passed?)] of the ride's intermediate stops
    return pg.evaluate("""() => [...document.querySelectorAll('#alarmList .trip .via li')].map(li => [li.querySelector('span').innerText.split(' ·')[0], li.classList.contains('passed')])""")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx, pg = session(b, gps=True)
    P, E, Q = C(PLACE), C(ESSERTS), C(QUIDORT)
    # 1. time says Place passed, the tram (late, not reported) 100 m before it
    go(pg, ctx, at(8, 32, 30), toward(P, E, 100))
    s1 = stops(pg)
    assert s1[0] == ["Petit-Lancy, place", False], s1
    print("1 GPS before Place, time past  →", s1)
    # 2. 90 m past Place; +3 min now reported (Place 08:35)
    S["delay"] = 3
    go(pg, ctx, at(8, 33, 30), toward(P, Q, 90))
    s2 = stops(pg)
    assert s2[0] == ["Petit-Lancy, place", True] and s2[1] == ["Petit-Lancy, Quidort", False], s2
    print("2 90 m past Place, delay +3    →", s2)
    # 3. a poor fix 70 m back: stays passed
    go(pg, ctx, at(8, 34, 0), toward(P, E, 70))
    s3 = stops(pg)
    assert s3[0] == ["Petit-Lancy, place", True], s3
    print("3 fix 70 m back                →", s3)
    ctx.close()

    # 4. without GPS: by time (Place 08:32 passed at 08:32:30, Quidort to come)
    S["delay"] = 0
    ctx, pg = session(b, gps=False)
    go(pg, ctx, at(8, 32, 30))
    s4 = stops(pg)
    assert s4[0] == ["Petit-Lancy, place", True] and s4[1] == ["Petit-Lancy, Quidort", False], s4
    print("4 no GPS, by time              →", s4)
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
