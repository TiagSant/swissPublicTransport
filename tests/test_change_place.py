"""BUG-12: the change place, found on real data across Switzerland (audit of 14.11.2026).

N (Neuchâtel): the API gives 4 min to walk from the bus (Poste, A) to the train (track "5AB": sectors of track 5);
   the bus goes on to Gare nord, 2.9 min from track 5 by the app's estimate — but the planned place is 2 min away by
   that same estimate. Nothing to gain: the plan stays. (It moved before: 2.9 < 4 − 1.) The track with sectors is
   found as track 5 (before: not found, the station's centre was used).
L (Lucerne): bus 1 to Banque (A), 1 min to bus 6 (C); both go on to Gare and stop on the same platform B there: stay
   on the 1, change at Gare without walking. Same arrival.
transport.opendata.ch is mocked; platforms are synthetic (window.QUAYS, ids 8599…)."""
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
def P(lat, lon): return [lat, lon]
O = st("8599000", "Ville, Ouest", 46.2900, 6.5000)
POSTE = st("8599001", "Ville, Poste", 46.3000, 6.5000)
NORD = st("8599002", "Ville, Gare nord", 46.3027, 6.5000)
GARE_CFF = st("8599010", "Ville", 46.3028, 6.5000)          # its centre: next to Gare nord, far from track 5
LOIN = st("8599030", "Loin", 46.6000, 6.9000)
O1 = st("8599100", "Lac, Ouest", 46.3000, 6.5100)
BANQUE = st("8599101", "Lac, Banque", 46.3100, 6.5100)
GARE = st("8599102", "Lac, Gare", 46.3120, 6.5120)
DEST = st("8599103", "Lac, Musée", 46.3200, 6.5200)
QUAYS = {"8599001": {"A": P(46.3000, 6.5000)}, "8599002": {"B": P(46.3027, 6.5000)}, "8599010": {"5": P(46.3011, 6.5000)},
         "8599101": {"A": P(46.3100, 6.5100), "C": P(46.3103, 6.5100)}, "8599102": {"B": P(46.3120, 6.5120)}}
S = {"base": None, "routes": 0, "case": "N"}
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    calls = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(a, t1, "arrival", "")}
def board_entry(cat, num, to, here, t0, nxt, no_coord=False, plat=""):
    strip = lambda s: {k: v for k, v in s.items() if k != "coordinate"} if no_coord else s
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "prognosis": {}, "platform": plat, "delay": 0},
            "passList": [{"station": here}] + [{"station": strip(s), "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": {}} for s, t in nxt]}
def at(m): return S["base"] + dt.timedelta(minutes=m)

def connections(frm, to):
    if S["case"] == "N":
        return [{"sections": [ride("B", "7", "Ville, Terminus", O, POSTE, at(0), at(10), "C", "A"), walk(POSTE, at(10), at(14)),
                              ride("IR", "15", "Loin", GARE_CFF, LOIN, at(20), at(50), "5AB", "1")]}]
    return [{"sections": [ride("B", "1", "Lac, Terminus", O1, BANQUE, at(0), at(10), "D", "A"), walk(BANQUE, at(10), at(11)),
                          ride("B", "6", "Lac, Musée", BANQUE, DEST, at(13), at(20), "C", "A", mid=[(GARE, at(15))])]}]
def board(stop_id):
    if stop_id == POSTE["id"]:
        return [board_entry("B", "7", "Ville, Terminus", POSTE, at(10), [(NORD, at(11))], plat="A")]
    if stop_id == NORD["id"]:
        return [board_entry("B", "7", "Ville, Terminus", NORD, at(11), [], plat="B")]
    if stop_id == BANQUE["id"]:
        return [board_entry("B", "1", "Lac, Terminus", BANQUE, at(10), [(GARE, at(12))], plat="A"),
                board_entry("B", "6", "Lac, Musée", BANQUE, at(13), [(GARE, at(15)), (DEST, at(20))], plat="C")]
    if stop_id == GARE["id"]:
        return [board_entry("B", "1", "Lac, Terminus", GARE, at(12), [], plat="B"),
                board_entry("B", "6", "Lac, Musée", GARE, at(15), [(DEST, at(20))], plat="B")]
    return []
def hav(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": connections(q["from"][0], q["to"][0])}
    elif u.path.endswith("/stationboard"): body = {"station": {"id": q["id"][0]}, "stationboard": board(q["id"][0])}
    elif "x" in q: body = {"stations": [dict(O, distance=100)]}
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
    ctx.add_init_script("window.QUAYS = " + json.dumps({"stops": QUAYS}) + ";")   # synthetic platforms (8599… ids)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=base.timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", dict({"tab": "journey", "lang": "fr"}, **store))
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    return ctx, pg

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    base = dt.datetime(2026, 11, 16, 8, 0, tzinfo=tz)
    import re as _re

    # ---- N: no better place by the same estimate → the plan stays
    ctx, pg = session(b, "N", base, {"settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(O), "journey:to": STOP(LOIN)})
    pg.wait_for_timeout(2500)
    pg.locator("#journeyList .jr").first.click(); det = pg.locator("#journeyList .jr-detail").first
    bus = " ".join(det.locator(".leg.ride").first.inner_text().split())
    assert "08:10 Ville, Poste" in bus and "Gare nord" not in " ".join(det.inner_text().split()), bus
    assert "Marche 4 min" in " ".join(det.locator(".leg.walk").first.inner_text().split())
    ctx.close()
    print("N  → kept: Poste (2 min to track 5 by the same estimate) is better than Gare nord (2.9); track 5AB found as track 5")

    # ---- L: both buses go on to Gare, same platform → change there without walking
    ctx, pg = session(b, "L", base, {"settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(O1), "journey:to": STOP(DEST)})
    pg.wait_for_function("[...document.querySelectorAll('#journeyList .jr-top b')].length", timeout=10000)
    pg.wait_for_timeout(2500)
    jr = pg.locator("#journeyList .jr").first
    assert jr.locator(".jr-top b").inner_text() == "08:00 → 08:20", jr.locator(".jr-top b").inner_text()   # same arrival
    jr.click(); det = pg.locator("#journeyList .jr-detail").first
    rides = [" ".join(det.locator(".leg.ride").nth(k).inner_text().split()) for k in range(2)]
    assert "08:12 Lac, Gare" in rides[0] and "08:15 Lac, Gare" in rides[1], rides
    assert not _re.search(r"\d[.,]\d+ min", det.inner_text())
    pg.screenshot(path=str(OUT / "board-later.png"))
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pl = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    rides = [l for l in pl if l["type"] == "ride"]
    assert rides[0]["toStop"]["name"] == "Lac, Gare" and rides[1]["from"]["name"] == "Lac, Gare" and rides[1]["platform"] == "B", rides
    walks = [l for l in pl if l["type"] == "walk"]
    assert all(round(w["min"]) == 0 for w in walks), walks
    ctx.close()
    print("L  → stay on bus 1 to Gare, bus 6 boarded there on the same platform (no walk); same arrival; followed as shown")
    b.close()
print("errors:", errors); assert not errors
print("OK")
