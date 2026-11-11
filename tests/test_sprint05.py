"""Sprint 5 / US-13: locate a platform on a map and walk to it.

Uses the real assets/quays.js (ATLAS) for Genève, Bel-Air. Leaflet and map tiles are served locally
when LEAFLET_DIR points to Leaflet's dist folder (npm pack leaflet@1.9.4); otherwise they load from the CDN.
"""
import os, json, math, re, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-05-platforms/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR = os.environ.get("LEAFLET_DIR")
TILE = os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
STATION = {"id": "8587387", "name": "Genève, Bel-Air", "coordinate": {"type": "WGS84", "x": 46.204728, "y": 6.143048}}
ME = (46.2045, 6.1420)

def dep(cat, num, to, mins, plat):
    t = now + dt.timedelta(minutes=mins)
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "passList": [{"station": STATION}, {"station": {"id": "1" + num, "name": "Next"}}],
            "stop": {"station": STATION, "departure": fmt(t), "departureTimestamp": int(t.timestamp()), "platform": plat,
                     "prognosis": {"departure": fmt(t)}, "delay": 0}}
board = {"station": STATION, "stationboard": [dep("T", "12", "Thônex, Moillesulaz", 3, "F"), dep("B", "3", "Gardiol", 5, "Q")]}
locs = {"stations": [{"id": STATION["id"], "name": STATION["name"], "coordinate": STATION["coordinate"], "icon": "tram"}]}

def api(route):
    body = board if "/stationboard" in route.request.url else locs
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
def cdn(route):
    name = route.request.url.rsplit("/", 1)[-1]
    route.fulfill(path=str(Path(LEAFLET_DIR) / name), content_type="text/css" if name.endswith(".css") else "application/javascript")
def tiles(route):
    route.fulfill(path=TILE, content_type="image/png")

def haversine(a, b):
    r = math.pi / 180; h = math.sin((b[0]-a[0])*r/2)**2 + math.cos(a[0]*r)*math.cos(b[0]*r)*math.sin((b[1]-a[1])*r/2)**2
    return 2 * 6371000 * math.asin(math.sqrt(h))

src = (ROOT / "assets/quays.js").read_text(encoding="utf-8")
QUAYS = json.loads(src.split("window.QUAYS = ", 1)[1].rstrip().rstrip(";"))["stops"][STATION["id"]]
F = QUAYS["F"]

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    def page(locale):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale=locale,
                            geolocation={"latitude": ME[0], "longitude": ME[1], "accuracy": 15}, permissions=["geolocation"])
        ctx.route("https://transport.opendata.ch/**", api)
        if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", cdn)
        if TILE: ctx.route("https://tile.openstreetmap.org/**", tiles)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(PAGE); pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
        pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")
        return ctx, pg

    ctx, pg = page("en-US")
    # 1. The official letter stays visible, as a link
    link = pg.locator(".dep[data-dir^='tram|12>'] .quay-link")
    assert link.inner_text() == "📍 Platform F", link.inner_text()
    link.click()
    pg.wait_for_selector(".qm.target")
    assert pg.locator(".dep[aria-expanded='true']").count() == 0          # the row did not expand
    assert pg.locator("#mapTitle").inner_text() == "Platform F" and pg.locator("#mapSub").inner_text() == "Genève, Bel-Air"
    print("1 platform link opens the map")

    # 2. Every platform of the stop, target highlighted, internal codes ("05") hidden
    labels = sorted(e.inner_text() for e in pg.locator(".qm").all())
    assert pg.locator(".qm.target").inner_text() == "F"
    assert all(re.fullmatch(r"[A-Z]", l) for l in labels), labels
    print("2 platforms on the map:", labels)

    # 3. Rider position, distance and walking directions to the platform
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('min on foot')")
    info = pg.locator("#mapInfo").inner_text()
    d = haversine(ME, F); expected = f"{round(d / 10) * 10} m away"
    assert info.startswith(expected), (info, expected)
    href = pg.locator("#walkThere").get_attribute("href")
    assert href == f"https://www.google.com/maps/dir/?api=1&destination={F[0]},{F[1]}&travelmode=walking", href
    assert pg.locator(".leaflet-interactive").count() >= 2                # accuracy circle + position dot
    print("3", info, "|", href)
    pg.wait_for_timeout(800)   # let the "show both" zoom animation finish
    inside = pg.evaluate("""() => { const m = document.getElementById('map').getBoundingClientRect();
        const dots = [...document.querySelectorAll('path.leaflet-interactive')].map(e => e.getBoundingClientRect());
        const t = document.querySelector('.qm.target').getBoundingClientRect();
        const ok = r => r.left >= m.left && r.right <= m.right && r.top >= m.top && r.bottom <= m.bottom;
        return { dot: dots.some(ok), target: ok(t) }; }""")
    assert inside == {"dot": True, "target": True}, inside
    print("3 both the rider and the platform are in view")
    pg.screenshot(path=str(OUT / "s5_platform_map.png"))

    # 4. Close, then a platform missing from ATLAS falls back to the stop
    pg.click("#mapClose"); assert pg.locator("#mapSheet").is_hidden()
    pg.locator(".dep[data-dir^='bus|3>'] .quay-link").click()
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('Exact position not available')")
    assert pg.locator(".qm.target").count() == 0
    c = STATION["coordinate"]
    assert pg.locator("#walkThere").get_attribute("href").endswith(f"destination={c['x']},{c['y']}&travelmode=walking")
    print("4 unknown platform → stop fallback")

    # 5. Map button: all platforms, no target
    pg.click("#mapClose"); pg.click("#mapBtn"); pg.wait_for_selector(".qm")
    assert pg.locator("#mapTitle").inner_text() == "All platforms" and pg.locator(".qm.target").count() == 0
    assert pg.locator(".qm").count() == len(labels)
    print("5 stop map with", pg.locator(".qm").count(), "platforms")
    ctx.close()

    # 6. French
    ctx, pg = page("fr-CH")
    pg.locator(".dep[data-dir^='tram|12>'] .quay-link").click(); pg.wait_for_selector(".qm.target")
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('min à pied')")
    assert pg.locator("#mapTitle").inner_text() == "Quai F" and "Y aller à pied" in pg.locator("#walkThere").inner_text()
    print("6 FR:", pg.locator("#mapInfo").inner_text())
    ctx.close(); b.close()
print("errors:", errors); assert not errors
