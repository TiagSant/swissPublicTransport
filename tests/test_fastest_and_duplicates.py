"""BUG-20 / BUG-21: "fastest" is the shortest journey; the same vehicles are one card.

Example, Domicile → near Rue de Saint-Jean: "the fastest is not: it is the longest, it only leaves
soonest — the fastest is the one that lasts the least"; and two identical cards "tram 14, get off at Palladium, then
on foot", one of them coming from a journey with a bus first, shown on foot ("Départ à pied", learned).
- A: from stop X, bus 22 22:15 → Mercier 22:45 (33 min with the walk to X);
- J1: from Confignon, croisée, tram 14 22:38 → Bel-Air, bus 7 → Mercier; its get-off-earlier journey (US-64): Palladium;
- J2: from stop X, bus 22 22:30 → Confignon, croisée, the same tram 14, bus 7; its get-off-earlier journey, shown starting
  on foot (learned: walked to Confignon, croisée 3 times) — the same as J1's.
Expected (priority "fastest"): the shortest first and tagged "Le plus rapide"; each journey once (without the fix:
"Stand, then on foot" and "tram 14 › bus 7" twice each, the second "Départ à pied").
Stop ids / positions real (Confignon, croisée, Jonction, Palladium, Stand, Bel-Air); X, Mercier, bus 22, the addresses made
up. transport.opendata.ch mocked; walks in straight lines."""
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
def at(h, m): return dt.datetime(2026, 11, 17, h, m, tzinfo=tz)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
CROISEE = st("8587386", "Confignon, croisée", 46.178810, 6.089810)
X = st("9100001", "Confignon, Arrêt X", 46.1773, 6.0925)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
PALLADIUM = st("8592874", "Genève, Palladium", 46.20303, 6.13391)
STAND = st("8592906", "Genève, Stand", 46.2036, 6.14105)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20424, 6.14206)
MERCIER = st("8592867", "Genève, Mercier", 46.2058, 6.1394)
STOPS = [CROISEE, X, JONCTION, PALLADIUM, STAND, BELAIR, MERCIER]
HOME = {"kind": "addr", "name": "Domicile (test)", "coord": [46.1769, 6.0898]}
DEST = {"kind": "addr", "name": "Rue de Saint-Jean (test)", "coord": [46.2055, 6.1405]}
C = lambda s: (s["coordinate"]["x"], s["coordinate"]["y"])
def dist(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    pl = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, b, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(b, t1, "arrival", "")}
TRAM = lambda: ride("T", "14", "Meyrin-Gravière", CROISEE, BELAIR, at(22, 38), at(22, 52), "A", "D", mid=[(JONCTION, at(22, 45)), (PALLADIUM, at(22, 47)), (STAND, at(22, 50))])
BUS7 = lambda: ride("B", "7", "Hôpital", BELAIR, MERCIER, at(22, 55), at(23, 0), "E", "B")
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        f, to = q.get("from", [""])[0], q.get("to", [""])[0]
        body = []
        if to == MERCIER["id"] and f == CROISEE["id"]: body = [{"sections": [TRAM(), walk(BELAIR, BELAIR, at(22, 52), at(22, 53)), BUS7()]}]
        if to == MERCIER["id"] and f == X["id"]: body = [
            {"sections": [ride("B", "22", "Jonction", X, MERCIER, at(22, 15), at(22, 45), "B", "")]},
            {"sections": [ride("B", "22", "Jonction", X, CROISEE, at(22, 30), at(22, 33), "B", "B"), walk(CROISEE, CROISEE, at(22, 33), at(22, 34)),
                          TRAM(), walk(BELAIR, BELAIR, at(22, 52), at(22, 53)), BUS7()]}]
        body = {"connections": body}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": []}
    elif u.path.endswith("/locations") and "x" in q:
        p = (float(q["x"][0]), float(q["y"][0]))
        near = [s for s in ([CROISEE, X] if dist(p, HOME["coord"]) < 50 else [MERCIER] if dist(p, DEST["coord"]) < 50 else STOPS)]
        body = {"stations": sorted([dict(s, distance=round(dist(p, C(s)))) for s in near], key=lambda s: s["distance"])}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
norm = lambda s: " ".join(s.split())
errors = []
def session(b, prio, foot=None):
    ctx = b.new_context(viewport={"width": 390, "height": 1600}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(22, 10).timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 15, "realWalk": False}, "prio": prio, "journey:from": HOME, "journey:to": DEST}
    if foot: store["foot"] = foot
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(1500)
    return ctx, pg
cards = lambda pg: [norm(x) for x in pg.locator("#journeyList .jr").all_inner_texts()]
dur = lambda c: int(c.split(" min")[0].split()[-1])

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    # learn "on foot to Confignon, croisée instead of bus 22" (3 times): the key the app records for that offer
    ctx, pg = session(b, "fast")
    keys = [k for k in json.loads(pg.evaluate("localStorage.getItem('tpp:foot')") or "{}") if k.startswith("start:")]
    ctx.close()
    assert keys, "no start-on-foot offer recorded"
    learned = {k: {"foot": 3, "bus": 0, "shown": 3, "t": 0} for k in keys}

    ctx, pg = session(b, "fast", learned)
    cs = cards(pg)
    pg.screenshot(path=str(OUT / "fastest-duplicates.png"), full_page=True)
    ctx.close()
    off = [c.split("Descente à ")[1].split(",")[1].strip() for c in cs if "Descente à" in c]
    assert off and len(off) == len(set(off)), cs                            # BUG-21: one card per stop got off at
    assert len([c for c in cs if "› 7 ›" in c]) == 1, cs                   #         and the tram + bus 7 once
    assert "Le plus rapide" in cs[0] and dur(cs[0]) == min(dur(c) for c in cs), cs   # BUG-20: the shortest, first
    a = [c for c in cs if c.startswith("22:12") or c.startswith("22:11")]
    assert a and "Le plus rapide" not in a[0], cs                          # A: leaves soonest, not the fastest
    for c in cs: print("  ", c[:110])
    b.close()
print("errors:", errors); assert not errors
print("OK")
