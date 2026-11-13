"""US-50 stay on to the change's stop, US-51 finish on foot from a later stop, US-52 walking along the streets.

transport.opendata.ch and the OSRM foot server (routing.openstreetmap.de) are mocked.
A (16:50): bus 19 Musée d'ethnographie 16:57 → Sainte-Clotilde 16:59, walk 4 min (API), tram 14 Jonction 17:05.
   The 19 goes on to Jonction (17:00): stay on → 1 min change instead of 4 min walk.
B (10:00): bus 1 Plainpalais 10:05 → Place du Cirque 10:10, bus 2 Cirque 10:14 → Musée 10:20, then walk to an address
   next to École-de-Médecine. The 1 goes on to École-de-Médecine (10:11): stay on, then 1 min on foot."""
import os, json, math, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, urlsplit, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
# real ids and positions (transport.opendata.ch, 13.11.2026)
MUSEE = st("8592868", "Genève, Musée d'ethnographie", 46.197808, 6.136266)
STECLO = st("8592908", "Genève, Sainte-Clotilde", 46.19981, 6.132825)
JONCTION = st("8587062", "Genève, Jonction", 46.200787, 6.12969)
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
VOIRIE = st("8587014", "Genève, Voirie", 46.20300, 6.12800)
PLAIN = st("8587391", "Genève, Plainpalais", 46.19830, 6.14160)
CIRQUE = st("8587015", "Genève, Place du Cirque", 46.20040, 6.14080)
ECOLE = st("8587016", "Genève, École-de-Médecine", 46.19760, 6.13880)
GARE = st("8587017", "Genève, Rond-Point de Plainpalais", 46.19500, 6.13800)
DEST = (46.19735, 6.13900)   # 30 m from École-de-Médecine, about 390 m from Place du Cirque, 100 m from Musée
S = {"base": None, "routes": 0}

def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1):
    calls = [{"station": a, "departure": fmt(t0)}, {"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(a, t1, "arrival", "")}
def board_entry(cat, num, to, here, t0, nxt, no_coord=False):
    strip = lambda s: {k: v for k, v in s.items() if k != "coordinate"} if no_coord else s
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "prognosis": {}, "platform": "", "delay": 0},
            "passList": [{"station": here}] + [{"station": strip(s), "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": {}} for s, t in nxt]}
def at(m): return S["base"] + dt.timedelta(minutes=m)

def connections(frm, to):
    if S["case"] == "A":
        return [{"sections": [ride("B", "19", "Onex, cité", MUSEE, STECLO, at(7), at(9), "J", "G"), walk(STECLO, at(9), at(13)),
                              ride("T", "14", "Bernex, Vailly", JONCTION, ESSERTS, at(15), at(20), "A", "B")]}]
    return [{"sections": [ride("B", "1", "Genève, Rond-Point de Plainpalais", PLAIN, CIRQUE, at(5), at(10), "A", "C"), walk(CIRQUE, at(10), at(12)),
                          ride("B", "2", "Genève, Musée d'ethnographie", CIRQUE, MUSEE, at(14), at(20), "D", "J")]}]
def board(stop_id):
    if S["case"] == "A" and stop_id == STECLO["id"]:
        # as on the real board: Jonction 1 min after Sainte-Clotilde; here without positions (light official-data board)
        return [board_entry("B", "19", "Onex, cité", STECLO, at(9), [(JONCTION, at(10)), (VOIRIE, at(13))], no_coord=True),
                board_entry("B", "19", "Vernier-Village", STECLO, at(9), [(MUSEE, at(11))])]          # other direction, same minute
    if S["case"] == "B" and stop_id == CIRQUE["id"]:
        return [board_entry("B", "1", "Genève, Rond-Point de Plainpalais", CIRQUE, at(10), [(ECOLE, at(11)), (GARE, at(13))])]
    return []
def hav(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": connections(q["from"][0], q["to"][0])}
    elif u.path.endswith("/stationboard"): body = {"station": {"id": q["id"][0]}, "stationboard": board(q["id"][0])}
    elif "x" in q: body = {"stations": [dict(MUSEE, distance=100)]}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
def osrm(route):
    S["routes"] += 1
    pts = urlsplit(route.request.url).path.rsplit("/", 1)[-1].split(";")
    (lo1, la1), (lo2, la2) = [tuple(map(float, p.split(","))) for p in pts]
    d = hav((la1, lo1), (la2, lo2)) * 1.6   # the streets: 1.6 × the straight line here
    geo = [[lo1, la1], [lo1, (la1 + la2) / 2], [lo2, la2]]
    route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                  body=json.dumps({"code": "Ok", "routes": [{"distance": d, "duration": d / 1.3, "geometry": {"type": "LineString", "coordinates": geo}}]}))
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}

errors = []
def session(b, case, base, store, routing=True):
    S.update(case=case, base=base, routes=0)
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": 46.20, "longitude": 6.14})
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", osrm if routing else (lambda r: r.abort()))
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=base.timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", dict({"tab": "journey", "lang": "fr"}, **store))
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    return ctx, pg

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # ---- A: stay on the 19 to Jonction
    ctx, pg = session(b, "A", dt.datetime(2026, 11, 13, 16, 50, tzinfo=tz),
                      {"settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(MUSEE), "journey:to": STOP(ESSERTS)})
    pg.wait_for_function("document.querySelector('#journeyList .jr .jw') && ![...document.querySelectorAll('#journeyList .jr .jw')].some(e => e.textContent.includes('4'))", timeout=10000)
    jr = pg.locator("#journeyList .jr").first
    meta = jr.locator(".jr-meta").inner_text()
    assert "1 min de marche" in meta and "4 min d’attente" in meta, meta
    jr.click(); det = pg.locator("#journeyList .jr-detail").first
    r19 = det.locator(".leg.ride").first
    assert "17:00 Genève, Jonction" in " ".join(r19.inner_text().split()), r19.inner_text()
    assert "2 arrêts" in r19.inner_text(), r19.inner_text()            # Sainte-Clotilde now passed on board
    assert "Marche 1 min — jusqu’à Genève, Jonction" in " ".join(det.locator(".leg.walk").first.inner_text().split()), det.locator(".leg.walk").first.inner_text()
    pg.screenshot(path=str(OUT / "stay-on-plan.png"))
    # nothing to gain at Sainte-Clotilde: no way back to it is offered (PO)
    assert det.locator(".stay-on, .stay-on-toggle").count() == 0 and "Sainte-Clotilde" not in det.inner_text()   # neither offered nor mentioned
    # followed as shown
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pl = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    assert pl[0]["toStop"]["name"] == "Genève, Jonction" and pl[1]["type"] == "walk" and round(pl[1]["min"]) == 1, pl[:2]
    assert S["routes"] == 0, "street routes are off in this session"
    ctx.close()
    print("change      → stay on the 19 to Jonction (real ids, board without positions): 1 min instead of 4; the planned stop not offered; followed as shown; the 19 to Vernier ignored")

    # ---- B: stay on the 1 to École-de-Médecine, then on foot; streets for the walks
    ctx, pg = session(b, "B", dt.datetime(2026, 11, 13, 10, 0, tzinfo=tz),
                      {"settings": {"footMaxMin": 15}, "journey:from": STOP(PLAIN), "journey:to": {"kind": "point", "coord": list(DEST), "near": None}})
    pg.wait_for_selector("#journeyList .jr .tag.foot", timeout=10000)
    pg.locator("#journeyList .jr").first.click()
    offer = pg.locator("#journeyList .jr-detail .foot-toggle[data-side=end]").first
    pg.wait_for_function("document.querySelector('#journeyList .jr-detail .foot-toggle[data-side=end]') && document.querySelector('#journeyList .jr-detail .foot-toggle[data-side=end]').textContent.includes('École-de-Médecine')", timeout=10000)
    txt = " ".join(offer.inner_text().split())
    assert "Rester dans le Bus 1 jusqu’à Genève, École-de-Médecine, puis à pied" in txt and "plus tôt" in txt, txt
    offer.click()
    jr = pg.locator("#journeyList .jr").first
    top = jr.locator(".jr-top b").inner_text()
    assert top.startswith("10:05 → 10:1") and int(top[-2:]) <= 13, top           # instead of 10:2x with the 2
    det = pg.locator("#journeyList .jr-detail").first
    assert det.locator(".leg.ride").count() == 1 and "Genève, École-de-Médecine" in det.locator(".leg.ride").inner_text()
    assert "Prendre plutôt le Bus 2" in det.inner_text()                           # the bus stays as an alternative
    pg.screenshot(path=str(OUT / "stay-on-foot.png"))
    print(f"foot        → stay on the 1 to École-de-Médecine, then on foot: {top}; the 2 offered instead")
    # the walk at the end follows the streets: the map draws the route, the distance is the street one
    assert S["routes"] > 0
    det.locator(".leg.walk .walk-map").last.click()
    pg.wait_for_selector("#mapSheet path.walk-route", timeout=10000)
    assert "par les rues" in pg.inner_text("#mapInfo"), pg.inner_text("#mapInfo")
    pg.screenshot(path=str(OUT / "walk-route.png"))
    pg.click("#mapClose")
    print(f"streets     → {S['routes']} route requests; walk map draws the street route, 'par les rues'")
    ctx.close()

    # ---- the straight line without the routing server (offline / off): nothing breaks
    ctx, pg = session(b, "B", dt.datetime(2026, 11, 13, 10, 0, tzinfo=tz),
                      {"settings": {"footMaxMin": 15}, "journey:from": STOP(PLAIN), "journey:to": {"kind": "point", "coord": list(DEST), "near": None}}, routing=False)
    pg.locator("#journeyList .jr").first.click()
    pg.locator("#journeyList .jr-detail .leg.walk .walk-map").last.click(); pg.wait_for_selector("#mapSheet .wm.b")
    pg.wait_for_timeout(500)
    assert pg.locator("#mapSheet path.walk-route").count() == 0 and "à pied" in pg.inner_text("#mapInfo")
    ctx.close()
    print("offline     → straight line kept")
    b.close()
print("errors:", errors); assert not errors
print("OK")
