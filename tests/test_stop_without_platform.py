"""US-48: a stop whose platform the API does not give, but whose position it gives, is shown like a platform:
a generic "Stop" button that opens the map at the stop, and walks end (or start) at the stop's position.

Journey (07:30): bus 1 Plainpalais (no platform) 07:35 → Bel-Air 07:40 (no platform), walk 2 min, bus 3 Bel-Air
platform D 07:48 → Cornavin 07:54 (platform H)."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich"); NOW = dt.datetime(2026, 11, 13, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: NOW + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAIN = st("8587391", "Genève, Plainpalais", 46.1983, 6.1416)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
def end(s, m, kind, plat): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(num, to, a, b, m0, m1, p0, p1):
    calls = [{"station": a, "departure": fmt(at(m0))}, {"station": b, "arrival": fmt(at(m1))}]
    return {"journey": {"category": "B", "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, m0, "departure", p0), "arrival": end(b, m1, "arrival", p1)}
CONN = {"sections": [ride("1", "Genève, Bel-Air", PLAIN, BELAIR, 5, 10, "", ""),
                     {"journey": None, "walk": {"duration": 120}, "departure": end(BELAIR, 10, "departure", ""), "arrival": end(BELAIR, 12, "arrival", "")},
                     ride("3", "Genève, gare Cornavin", BELAIR, CORN, 18, 24, "D", "H")]}
def api(route):
    u = urlparse(route.request.url)
    body = {"connections": [CONN]} if u.path.endswith("/connections") else {"stations": [CORN]} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": 46.1990, "longitude": 6.1420})
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    pg.evaluate("""s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }""",
                {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0}, "journey:from": STOP(PLAIN), "journey:to": STOP(CORN)})
    pg.reload(); pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()

    det = pg.locator("#journeyList .jr-detail").first
    chips = det.locator(".leg.ride .plat")
    assert [" ".join(c.split()) for c in chips.all_inner_texts()] == ["Arrêt", "Arrêt", "Quai D", "Quai H"], chips.all_inner_texts()
    assert det.locator(".plat.stop").count() == 2
    # the stop button: the map at the stop's position
    det.locator(".plat.stop").first.click()
    pg.wait_for_selector("#mapSheet .qm.stop-pin")
    assert pg.inner_text("#mapTitle") == "Genève, Plainpalais" and pg.inner_text("#mapSub") == "Pas de quai indiqué : position de l’arrêt"
    assert pg.is_visible("#walkThere") and "46.1983,6.1416" in pg.get_attribute("#walkThere", "href")
    assert "Aucun quai" not in pg.inner_text("#mapInfo"), pg.inner_text("#mapInfo")
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('m')")
    pg.screenshot(path=str(OUT / "stop-without-platform-map.png"))
    pg.click("#mapClose")
    print("planning    → 'Arrêt' buttons where the API gives no platform; map at the stop, walk there")

    # the walk from a stop without platform to platform D: starts at the stop's position (pin), ends on D
    det.locator(".walk-map").first.click()
    pg.wait_for_selector("#mapSheet .wm.b")
    assert pg.locator("#mapSheet .wm.a[data-stop]").count() == 1 and pg.inner_text("#mapSheet .wm.b") == "D"
    assert pg.inner_text("#mapSub") == "Genève, Bel-Air → Genève, Bel-Air (Quai D)", pg.inner_text("#mapSub")
    pg.wait_for_timeout(800)
    box = pg.locator("#mapSheet .wm.a").bounding_box(); mbox = pg.locator("#map").bounding_box()
    others = pg.locator("#mapSheet .qm.other").all_inner_texts()
    assert len(others) == len(set(others)), others                       # each platform of the stop once
    assert box and mbox and mbox["y"] <= box["y"] <= mbox["y"] + mbox["height"], (box, mbox)   # in view
    pg.screenshot(path=str(OUT / "stop-without-platform-walk.png"))
    pg.click("#mapClose")
    print("walk        → from the stop's position (pin) to platform D")

    # following: same buttons, same map
    pg.click("#journeyList .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip = pg.locator("#alarmList .trip").first
    assert trip.locator(".plat.stop").count() == 2, trip.inner_text()
    trip.locator(".plat.stop").nth(1).click()
    pg.wait_for_selector("#mapSheet .qm.stop-pin")
    assert pg.inner_text("#mapTitle") == "Genève, Bel-Air"
    assert pg.locator("#mapSheet .qm:not(.stop-pin)").count() > 0      # Bel-Air's platforms around, for reference
    pg.click("#mapClose")
    print("following   → 'Arrêt' buttons, map at the stop with its platforms around")
    b.close()
print("errors:", errors); assert not errors
print("OK")
