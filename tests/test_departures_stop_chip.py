"""US-48 on the Departures tab: a departure without a platform gets the "Stop" button, which opens the map at the
stop's position; departures with a platform keep their platform button."""
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
HERE = {"id": "8587391", "name": "Genève, Plainpalais", "coordinate": {"type": "WGS84", "x": 46.1983, "y": 6.1416}}
def dep(num, m, plat):
    t0 = at(m)
    return {"category": "B", "number": num, "to": "Somewhere", "operator": "TPG",
            "stop": {"station": HERE, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": plat,
                     "prognosis": {"departure": fmt(t0)}, "delay": 0}, "passList": [{"station": HERE}]}
def api(route):
    u = urlparse(route.request.url)
    body = {"station": HERE, "stationboard": [dep("1", 3, ""), dep("35", 5, "C")]} if u.path.endswith("/stationboard") else {"stations": [HERE]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": 46.1990, "longitude": 6.1420})
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    pg.evaluate("localStorage.setItem('tpp:lang', JSON.stringify('fr'))"); pg.reload()
    pg.fill("#q", "Plainpalais"); pg.wait_for_selector("#results button[data-id]"); pg.locator("#results button[data-id]").first.click()
    pg.wait_for_selector(".dep")
    rows = pg.locator(".dep")
    assert rows.nth(0).locator(".plat.stop").count() == 1 and " ".join(rows.nth(0).locator(".plat").inner_text().split()) == "Arrêt"
    assert " ".join(rows.nth(1).locator(".plat").inner_text().split()) == "Quai C" and rows.nth(1).locator(".plat.stop").count() == 0
    rows.nth(0).locator(".plat.stop").click()
    pg.wait_for_selector("#mapSheet .qm.stop-pin")
    assert pg.inner_text("#mapTitle") == "Genève, Plainpalais" and pg.inner_text("#mapSub") == "Pas de quai indiqué : position de l’arrêt"
    assert "46.1983,6.1416" in pg.get_attribute("#walkThere", "href")
    assert not pg.locator(".dep.open").count(), "the button must not unfold the row"
    pg.screenshot(path=str(OUT / "departures-stop-chip.png"))
    pg.click("#mapClose")
    rows.nth(1).locator(".plat").click(); pg.wait_for_selector("#mapSheet:not([hidden])")
    assert pg.inner_text("#mapTitle") == "Quai C"
    print("departures  → 'Arrêt' button without platform opens the stop's position; 'Quai C' unchanged")
    b.close()
print("errors:", errors); assert not errors
print("OK")
