"""BUG-11: get off earlier, at a stop the first vehicle passes before the planned one, when it is closer to the next one.

The PO's case (14.11.2026): tram 14 to Meyrin from Les Esserts, the API gets off at Lyon (quai N), one stop after
Gare Cornavin, and walks 4 min back to the train at Genève voie 5. The 14 stops at Gare Cornavin (quai H, under the
tracks) just before: get off there, about 1 min from the train. Same train, same arrival.
Real stop order of the 14 (OJP, recorded): ... Coutance → gare Cornavin → Lyon → Poterie ...
transport.opendata.ch is mocked; quay positions are the real ATLAS ones (assets/quays.js)."""
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
# real ids and positions (transport.opendata.ch stops, ATLAS quays)
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20412, 6.14272)
COUTANCE = st("8592812", "Genève, Coutance", 46.20761, 6.14229)
CORNAVIN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
LYON = st("8592850", "Genève, Lyon", 46.210033, 6.137844)
POTERIE = st("8592889", "Genève, Poterie", 46.2115, 6.1355)
GENEVE = st("8501008", "Genève", 46.210208, 6.142437)
LAUSANNE = st("8501120", "Lausanne", 46.516795, 6.629087)
S = {"base": None, "routes": 0, "case": "cut"}
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
    if S["case"] == "cut":   # 07:30 tram 14 → Lyon 07:43 (via Cornavin 07:42), walk 4 min, IR Genève 07:55 voie 5
        return [{"sections": [ride("T", "14", "Meyrin-Gravière", ESSERTS, LYON, at(30), at(43), "B", "N",
                                   mid=[(BELAIR, at(38)), (COUTANCE, at(40)), (CORNAVIN, at(42))]),
                              walk(LYON, at(43), at(47)),
                              ride("IR", "90", "Brig", GENEVE, LAUSANNE, at(55), at(90), "5", "3")]}]
    # control: the earlier stops are all farther from the train than the planned one
    return [{"sections": [ride("T", "14", "Meyrin-Gravière", ESSERTS, CORNAVIN, at(30), at(42), "B", "H", mid=[(BELAIR, at(38)), (COUTANCE, at(40))]),
                          walk(CORNAVIN, at(42), at(46)),
                          ride("IR", "90", "Brig", GENEVE, LAUSANNE, at(55), at(90), "5", "3")]}]
def board(stop_id):
    if stop_id == CORNAVIN["id"]:   # the 14 to Meyrin at Gare Cornavin: quai H (the board of the stop itself)
        return [board_entry("T", "14", "Meyrin-Gravière", CORNAVIN, at(42), [(LYON, at(43)), (POTERIE, at(45))], plat="H"),
                board_entry("T", "14", "Bernex-Vailly", CORNAVIN, at(42), [(COUTANCE, at(43))], plat="I")]
    if stop_id == LYON["id"]:
        return [board_entry("T", "14", "Meyrin-Gravière", LYON, at(43), [(POTERIE, at(45))], plat="N")]
    return []
def hav(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": connections(q["from"][0], q["to"][0])}
    elif u.path.endswith("/stationboard"): body = {"station": {"id": q["id"][0]}, "stationboard": board(q["id"][0])}
    elif "x" in q: body = {"stations": [dict(ESSERTS, distance=100)]}
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
    store = {"settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(ESSERTS), "journey:to": STOP(LAUSANNE)}
    base = dt.datetime(2026, 11, 14, 7, 0, tzinfo=tz)

    ctx, pg = session(b, "cut", base, store)
    pg.wait_for_function("[...document.querySelectorAll('#journeyList .jr .jw')].length && ![...document.querySelectorAll('#journeyList .jr .jw')].some(e => e.textContent.includes('4'))", timeout=10000)
    jr = pg.locator("#journeyList .jr").first
    top = jr.locator(".jr-top b").inner_text()
    assert top == "07:30 → 08:30", top                    # same train, same arrival
    jr.click(); det = pg.locator("#journeyList .jr-detail").first
    txt = " ".join(det.inner_text().split())
    tram = " ".join(det.locator(".leg.ride").first.inner_text().split())
    assert "07:42 Genève, gare Cornavin Quai H" in tram, tram
    assert "Lyon" not in txt, txt                                                    # neither offered nor mentioned
    w = " ".join(det.locator(".leg.walk").first.inner_text().split())
    assert "Marche 1 min —" in w and "jusqu’à Genève" in w, w
    import re as _re
    assert not _re.search(r"\d[.,]\d+ min", txt), txt
    pg.screenshot(path=str(OUT / "get-off-earlier.png"))
    # followed as shown
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pl = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    assert pl[0]["toStop"]["name"] == "Genève, gare Cornavin" and pl[1]["type"] == "walk" and round(pl[1]["min"]) == 1, pl[:2]
    assert [v["name"] for v in pl[0]["via"]] == ["Genève, Bel-Air", "Genève, Coutance"], pl[0]["via"]
    ctx.close()
    print("earlier     → off the 14 at Gare Cornavin (quai H, 07:42) instead of Lyon + 4 min back; Lyon not mentioned; followed as shown")

    # control: the planned stop is already the closest one: nothing changes, no extra board read
    S["boards"] = []
    ctx, pg = session(b, "keep", base, store)
    pg.wait_for_timeout(1500)
    pg.locator("#journeyList .jr").first.click(); det = pg.locator("#journeyList .jr-detail").first
    tram = " ".join(det.locator(".leg.ride").first.inner_text().split())
    assert "07:42 Genève, gare Cornavin" in tram and "Coutance" not in " ".join(det.locator(".leg.walk").first.inner_text().split()), tram
    ctx.close()
    print("control     → planned stop already closest: kept")
    b.close()
print("errors:", errors); assert not errors
print("OK")
