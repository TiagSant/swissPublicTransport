"""US-65: walk to a stop a later ride passes and board it there — a journey of its own.

The PO's case (16.11.2026): rue De-Candolle 6 → Les Esserts. The API walks to Place de Neuve, takes tram 12 to
Bel-Air, then tram 14. Walking, Stand (a stop tram 14 passes after Bel-Air) is about as close, and the tram leaves
there 2 min later: walk to Stand, no tram 12. The US-36 offer (walk to Bel-Air) stays on the API's journey.
transport.opendata.ch is mocked; stop ids and positions are real."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
HOME = [46.19995, 6.14455]   # rue De-Candolle 6 (approx.)
NEUVE = st("8592885", "Genève, Place de Neuve", 46.20069, 6.1433)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20424, 6.14206)
STAND = st("8592906", "Genève, Stand", 46.2036, 6.14105)
PALLADIUM = st("8592874", "Genève, Palladium", 46.20303, 6.13391)
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
def tram14(t0, a=BELAIR):   # tram 14 from Bel-Air: Stand +2, Palladium +4, Jonction +6, Les Esserts +12
    mid = [(STAND, at(t0 + 2)), (PALLADIUM, at(t0 + 4)), (JONCTION, at(t0 + 6))]
    return ride("T", "14", "Bernex-Vailly", a, ESSERTS, at(t0), at(t0 + 12), "D", "B", mid=mid)
def connections():   # from Place de Neuve (the app walks there from the address): tram 12 to Bel-Air, then tram 14
    return [{"sections": [ride("T", "12", "Moillesulaz", NEUVE, BELAIR, at(4), at(7), "B", "C"),
                          walk(BELAIR, BELAIR, at(7), at(8)), tram14(11)]}]
def near(s, d): return dict(s, distance=d)
def api(route):
    u = urlparse(route.request.url)
    if u.path.endswith("/connections"): body = {"connections": connections() if "8592885" in u.query.split("&to=")[0] else []}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": []}
    else: body = {"stations": [near(NEUVE, 130), near(STAND, 480), near(BELAIR, 510)]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
ADDR = {"kind": "addr", "name": "Rue De-Candolle 6, Genève", "coord": HOME}
norm = lambda s: " ".join(s.split())

errors = []
def session(b, settings):
    S["base"] = dt.datetime(2026, 11, 16, 18, 45, tzinfo=tz)
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    ctx.route("https://nominatim.openstreetmap.org/**", lambda r: r.fulfill(status=200, content_type="application/json", body="[]", headers={"Access-Control-Allow-Origin": "*"}))
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=S["base"].timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": settings, "prio": "fast", "journey:from": ADDR, "journey:to": STOP(ESSERTS)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(800)
    return ctx, pg
cards = lambda pg: [norm(x) for x in pg.locator("#journeyList .jr").all_inner_texts()]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ON = {"footMaxMin": 15, "realWalk": False, "alightReminder": False}

    # 1. the journey on foot to Stand is listed, leaving later; the API's journey keeps its US-36 offer (Bel-Air)
    ctx, pg = session(b, ON)
    cs = cards(pg)
    sc = [c for c in cs if "À pied jusqu’à Genève, Stand" in c]
    assert len(sc) == 1, cs
    assert "Direct" in sc[0] and "19:08" in sc[0], sc[0]
    api_card = next(c for c in cs if "12" in c.split("19:08")[-1] or "›" in c)
    assert "À pied jusqu’à" not in api_card, api_card
    n = cs.index(sc[0])
    pg.locator("#journeyList .jr").nth(n).click()
    det = pg.locator("#journeyList .jr-detail").first
    rides = det.locator(".leg.ride")
    assert rides.count() == 1, norm(det.inner_text())
    r = norm(rides.first.inner_text())
    assert "18:58 Genève, Stand" in r and "Bel-Air" not in r, r
    w = norm(det.locator(".leg.walk").first.inner_text())
    assert "Stand" in w, w
    pg.screenshot(path=str(OUT / "shortcut-start.png"))
    print("list        →", sc[0])

    # followed: leave for Stand, tram 14 from there
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    a = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
    assert a["first"]["stopId"] == STAND["id"] and a["first"]["label"] == "14", a["first"]
    assert [l["type"] for l in a["plan"]] == ["walk", "ride"], a["plan"]
    ctx.close()
    print("followed    → walk to Stand, tram 14 from there")

    # 2. finishing / starting on foot turned off: journeys as found
    ctx, pg = session(b, {"footMaxMin": 0, "realWalk": False})
    assert not any("À pied jusqu’à" in c for c in cards(pg)), cards(pg)
    ctx.close()
    print("setting off → journeys as found")
    b.close()
print("errors:", errors); assert not errors
print("OK")
