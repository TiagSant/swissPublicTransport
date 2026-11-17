"""BUG-18: getting off earlier (US-64): the stop with the least walking kept too, and the stop the streets make best.

The PO's case (17.11.2026, 18:16): Les Esserts → Rue de Saint-Jean 98. The API: tram 14 to Bel-Air, then bus 7.
The app offered only tram 14 to Palladium (the earliest arrival); Google tram 14 to Stand (less walking).
Now both are kept (earliest arrival, least walking); once the walks follow the streets, a beaten one goes.
Real data (probe 17.11 19:00, street walks): Palladium 7.8 min on foot, 1 min sooner; Stand 5.9 min: both offered.
Here the street lengths are made up to check the second rule (Palladium 1050 m: beaten by Stand).
Stop ids / positions real (Les Esserts, Jonction, Palladium, Stand, Bel-Air); "Mercier" approximate.
transport.opendata.ch and the street routing are mocked."""
import os, json, math, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, urlsplit, parse_qs, unquote
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
PALLADIUM = st("8592874", "Genève, Palladium", 46.20303, 6.13391)
STAND = st("8592906", "Genève, Stand", 46.2036, 6.14105)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20424, 6.14206)
MERCIER = st("8592867", "Genève, Mercier", 46.2058, 6.1394)
STOPS = [ESSERTS, JONCTION, PALLADIUM, STAND, BELAIR, MERCIER]
DEST = {"kind": "addr", "name": "Rue de Saint-Jean 98, Genève", "coord": [46.20628, 6.13829]}
C = lambda s: (s["coordinate"]["x"], s["coordinate"]["y"])
BASE = dt.datetime(2026, 11, 17, 18, 16, tzinfo=tz)
def at(m): return BASE + dt.timedelta(minutes=m)
def dist(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    calls = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, b, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(b, t1, "arrival", "")}
def connections():   # tram 14 18:19 (Jonction +7, Palladium +9, Stand +12) to Bel-Air +14, walk 1, bus 7 18:36 → Mercier 18:41
    return [{"sections": [ride("T", "14", "Meyrin-Gravière", ESSERTS, BELAIR, at(3), at(17), "A", "D", mid=[(JONCTION, at(10)), (PALLADIUM, at(12)), (STAND, at(15))]),
                          walk(BELAIR, BELAIR, at(17), at(18)), ride("B", "7", "Hôpital", BELAIR, MERCIER, at(20), at(25), "E", "B")]}]
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        body = {"connections": connections() if q.get("from") == [ESSERTS["id"]] and q.get("to") == [MERCIER["id"]] else []}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": []}
    elif u.path.endswith("/locations") and "x" in q:
        p = (float(q["x"][0]), float(q["y"][0]))
        body = {"stations": sorted([dict(s, distance=round(dist(p, C(s)))) for s in STOPS if dist(p, C(s)) < 600], key=lambda s: s["distance"])}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
def osrm(route):   # walking along the streets (made-up lengths: from Palladium much longer)
    a, b = unquote(urlsplit(route.request.url).path.rsplit("/", 1)[-1]).split(";")   # (urlparse would cut at ";")
    (lon1, lat1), (lon2, lat2) = [tuple(map(float, x.split(","))) for x in (a, b)]
    d = dist((lat1, lon1), (lat2, lon2)) * 1.25
    if dist((lat1, lon1), C(PALLADIUM)) < 80: d = 1050
    if dist((lat1, lon1), C(STAND)) < 80: d = 550
    body = {"routes": [{"distance": d, "geometry": {"coordinates": [[lon1, lat1], [lon2, lat2]]}}]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": list(C(s))}
norm = lambda s: " ".join(s.split())
errors = []
def session(b, settings, prio="fast"):
    ctx = b.new_context(viewport={"width": 390, "height": 1400}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", osrm)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=BASE.timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": settings, "prio": prio, "journey:from": STOP(ESSERTS), "journey:to": DEST}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(2500)
    return ctx, pg
cards = lambda pg: [norm(x) for x in pg.locator("#journeyList .jr").all_inner_texts()]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # 1. walks along the streets: Stand (550 m) kept, Palladium (1050 m, later) left out
    ctx, pg = session(b, {"footMaxMin": 15, "realWalk": True})
    cs = cards(pg)
    assert not any("Descente à Genève, Palladium" in c for c in cs), cs
    sc = [c for c in cs if "Descente à Genève, Stand" in c]
    assert len(sc) == 1 and cs[0] == sc[0], cs
    assert any("›" in c and "7" in c for c in cs), cs   # the API's journey (tram 14 › bus 7) stays
    pg.screenshot(path=str(OUT / "shortcut-best-stop.png"))
    print("streets     →", sc[0][:90])
    ctx.close()

    # 2. straight lines only (street walks off): Palladium 18:36:00, Stand 18:36:57 — the same minute shown, Stand
    #    walks less: Palladium left out
    ctx, pg = session(b, {"footMaxMin": 15, "realWalk": False})
    cs = [c for c in cards(pg) if "Descente à" in c]
    assert len(cs) == 1 and "Descente à Genève, Stand" in cs[0], cs
    print("straight    →", cs[0][:90])
    ctx.close()
    b.close()
print("errors:", errors); assert not errors
print("OK")
