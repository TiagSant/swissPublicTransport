"""US-64: get off earlier and finish on foot — a journey of its own, as other apps suggest.

The PO's case (16.11.2026, 10:38): Musée d'ethnographie → Bovy-Lysberg. The API takes bus 2 to Bel-Air and a second
bus back to Bovy-Lysberg. Bus 2 passes Théâtre just before, about 100 m from Bovy-Lysberg: get off there and walk.
The journey with the change stays in the list; the rider's priority orders them.
transport.opendata.ch is mocked; stop ids and positions are the real ones."""
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
MUSEE = st("8592868", "Genève, Musée d'ethnographie", 46.19795, 6.13641)
CIRQUE = st("8592804", "Genève, Cirque", 46.20145, 6.13948)
THEATRE = st("8595022", "Genève, Théâtre", 46.20207, 6.14182)
BELAIR = st("8587387", "Genève, Bel-Air", 46.20424, 6.14206)
BOVY = st("8592794", "Genève, Bovy-Lysberg", 46.20238, 6.14294)
S = {"base": None}
def at(m): return S["base"] + dt.timedelta(minutes=m)
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    calls = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(a, t1, "arrival", "")}
def bus2(t0):   # bus 2 from Musée d'ethnographie to Bel-Air, through Cirque and Théâtre
    return ride("B", "2", "Genève-Plage", MUSEE, BELAIR, at(t0), at(t0 + 8), "J", "D", mid=[(CIRQUE, at(t0 + 3)), (THEATRE, at(t0 + 5))])
def connections():
    # the same bus 2 (10:39) with two buses after it, and the next bus 2 (10:44): two shortcuts, not three
    return [{"sections": [bus2(9), walk(BELAIR, at(17), at(19)), ride("B", "36", "Saint-Pierre", BELAIR, BOVY, at(21), at(23), "E", "U")]},
            {"sections": [bus2(9), walk(BELAIR, at(17), at(19)), ride("B", "36", "Saint-Pierre", BELAIR, BOVY, at(26), at(28), "E", "U")]},
            {"sections": [bus2(14), walk(BELAIR, at(22), at(24)), ride("B", "36", "Saint-Pierre", BELAIR, BOVY, at(26), at(28), "E", "U")]}]
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": connections()}
    elif u.path.endswith("/stationboard"): body = {"station": {"id": q["id"][0]}, "stationboard": []}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
norm = lambda s: " ".join(s.split())

errors = []
def session(b, settings, prio="fast"):
    S["base"] = dt.datetime(2026, 11, 16, 10, 30, tzinfo=tz)
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=S["base"].timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": settings, "prio": prio, "journey:from": STOP(MUSEE), "journey:to": STOP(BOVY)}
    pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(800)
    return ctx, pg
cards = lambda pg: [norm(x) for x in pg.locator("#journeyList .jr").all_inner_texts()]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ON = {"footMaxMin": 15, "realWalk": False}

    # 1. fastest first: bus 2 to Théâtre, then on foot, without the second bus
    ctx, pg = session(b, ON)
    cs = cards(pg)
    assert cs[0].startswith("10:39 → 10:45") and "Descente à Genève, Théâtre, puis à pied" in cs[0], cs
    assert sum("Descente à Genève, Théâtre" in c for c in cs) == 2, cs          # 10:39 once (not once per second bus) and 10:44
    assert any(c.startswith("10:39 → 10:53") for c in cs), cs                   # the journey with the change stays
    assert "Fin à pied ?" not in cs[0], cs[0]                                    # one walk tag on the card
    pg.locator("#journeyList .jr").first.click()
    det = pg.locator("#journeyList .jr-detail").first
    rides = det.locator(".leg.ride")
    assert rides.count() == 1, norm(det.inner_text())
    r = norm(rides.first.inner_text())
    assert "10:44 Genève, Théâtre" in r and "Bel-Air" not in r, r
    w = norm(det.locator(".leg.walk").last.inner_text())
    assert "jusqu’à destination" in w or "destination" in w, w
    pg.screenshot(path=str(OUT / "shortcut-on-foot.png"))
    print("fastest     →", cs[0])

    # followed as shown: get off at Théâtre, then the walk
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pl = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    kinds = [l["type"] for l in pl]
    assert kinds == ["ride", "walk"], kinds
    assert pl[0]["toStop"]["name"] == "Genève, Théâtre" and [v["name"] for v in pl[0]["via"]] == ["Genève, Cirque"], pl[0]
    assert pl[1]["edge"] == "egress", pl[1]
    trip = norm(pg.locator("#alarmList .trip").first.inner_text())
    assert "Théâtre" in trip and "36" not in trip, trip
    ctx.close()
    print("followed    → off at Théâtre, then on foot; no second bus")

    # 2. least walking first: the shortcut is still listed
    ctx, pg = session(b, ON, prio="walk")
    cs = cards(pg)
    assert any("Descente à Genève, Théâtre" in c for c in cs), cs
    ctx.close()
    print("least walk  → shortcut still listed")

    # 3. finishing on foot turned off (Settings: 0 min): no shortcut, as before
    ctx, pg = session(b, {"footMaxMin": 0, "realWalk": False})
    cs = cards(pg)
    assert not any("Descente" in c for c in cs) and cs[0].startswith("10:39 → 10:53"), cs
    ctx.close()
    print("setting off → journeys as found")
    b.close()
print("errors:", errors); assert not errors
print("OK")
