"""BUG-05: a walk ends on the platform of the next ride — the live one while the journey is followed — and platforms
can be tapped in the followed journey to see them on the map.

Plan (asked at 07:30): Genève, Plainpalais 07:40 tram 12 → Genève, Bel-Air 07:45 (arrives at platform B), walk 2 min,
bus 3 07:50 from Bel-Air platform D → Genève, gare Cornavin 07:56. While following, the bus is moved to platform G."""
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
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAINPALAIS = st("8587391", "Genève, Plainpalais", 46.198300, 6.141600)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORNAVIN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
LIVE = {"bus_platform": "D", "planned": "D"}

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def call(s, arr=None, dep=None): return {"station": s, "arrival": fmt(at(arr)) if arr is not None else None, "departure": fmt(at(dep)) if dep is not None else None}
def section(cat, num, to, calls, a, b, ma, mb, plat, arr_plat):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, ma, "departure", plat), "arrival": end(b, mb, "arrival", arr_plat)}
def plan(): return {"sections": [
    section("T", "12", "Genève, Bel-Air", [call(PLAINPALAIS, dep=10), call(BELAIR, arr=15)], PLAINPALAIS, BELAIR, 10, 15, "C", "B"),
    {"journey": None, "walk": {"duration": 120}, "departure": end(BELAIR, 15, "departure"), "arrival": end(BELAIR, 17, "arrival")},
    section("B", "3", "Genève, gare Cornavin", [call(BELAIR, dep=20), call(CORNAVIN, arr=26)], BELAIR, CORNAVIN, 20, 26, LIVE["planned"], "H")]}

def entry(cat, num, to, s, m, plat, nxt, planned=None):
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": s, "departure": fmt(at(m)), "departureTimestamp": int(at(m).timestamp()),
                     "prognosis": {"departure": fmt(at(m)), "platform": plat}, "platform": planned or plat, "delay": 0},
            "passList": [{"station": s}] + [{"station": x, "arrival": fmt(at(mm)), "prognosis": {"arrival": fmt(at(mm))}} for x, mm in nxt]}
def boards(stop_id):
    if stop_id == PLAINPALAIS["id"]: return [entry("T", "12", "Genève, Bel-Air", PLAINPALAIS, 10, "C", [(BELAIR, 15)])]
    if stop_id == BELAIR["id"]: return [entry("B", "3", "Genève, gare Cornavin", BELAIR, 20, LIVE["bus_platform"], [(CORNAVIN, 26)], planned=LIVE["planned"])]
    return []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [plan()]}
    elif u.path.endswith("/locations"): body = {"stations": [CORNAVIN]}
    else: body = {"station": {"id": q["id"][0]}, "stationboard": boards(q["id"][0])}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def walk_map_ends(pg):
    """Texts of the two end markers and the grey platforms around them, once the map is drawn."""
    pg.wait_for_selector("#mapSheet .wm.b")
    return pg.inner_text("#mapSheet .wm.a"), pg.inner_text("#mapSheet .wm.b"), pg.locator("#mapSheet .qm.other").all_inner_texts()
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    def start(b):
      ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich",
                          permissions=["geolocation"], geolocation={"latitude": 46.2046, "longitude": 6.1440})
      ctx.route("https://transport.opendata.ch/**", api)
      if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
      if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
      pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
      pg.clock.install(time=NOW.timestamp())
      pg.goto(PAGE)
      pg.evaluate("""() => {
        localStorage.setItem('tpp:journey:from', JSON.stringify({ kind: 'stop', id: '8587391', name: 'Genève, Plainpalais', coord: [46.1983, 6.1416] }));
        localStorage.setItem('tpp:journey:to', JSON.stringify({ kind: 'stop', id: '8587057', name: 'Genève, gare Cornavin', coord: [46.209652, 6.14233] }));
        localStorage.setItem('tpp:settings', JSON.stringify({ footMaxMin: 0 }));
        localStorage.setItem('tpp:tab', '"journey"'); }""")
      pg.reload()
      pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
      return ctx, pg
    ctx, pg = start(b)

    # Planning: the walk goes from the tram's arrival platform to the bus's platform
    detail = pg.locator("#journeyList .jr-detail").first
    assert [x.strip() for x in detail.locator(".plat .plat-v").all_inner_texts()] == ["C", "B", "D", "H"], detail.locator(".plat .plat-v").all_inner_texts()
    detail.locator(".walk-map").click()
    a, bb, others = walk_map_ends(pg)
    assert (a, bb) == ("B", "D"), (a, bb)
    assert others and not {"B", "D"} & set(others), others          # Bel-Air's other platforms, in grey
    sub = pg.inner_text("#mapSub")
    assert sub == "Genève, Bel-Air (Platform B) → Genève, Bel-Air (Platform D)", sub
    assert "not available" not in pg.inner_text("#mapInfo"), pg.inner_text("#mapInfo")
    pg.screenshot(path=str(OUT / "walk-platform-plan.png"))
    pg.click("#mapClose")
    print("planning    → walk B → D, other Bel-Air platforms shown; arrival platforms tappable (C B D H)")

    # Following: platforms are buttons, tapping one shows it on the map
    pg.click("#journeyList .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip = pg.locator("#alarmList .trip").first
    chips = trip.locator(".plat")
    assert [x.strip() for x in chips.locator(".plat-v").all_inner_texts()] == ["C", "B", "D", "H"], chips.all_inner_texts()
    chips.nth(2).click()
    pg.wait_for_selector("#mapSheet .qm.target")
    assert pg.inner_text("#mapTitle") == "Platform D" and pg.inner_text("#mapSheet .qm.target") == "D", (pg.inner_text("#mapTitle"),)
    assert pg.inner_text("#mapSub") == "Genève, Bel-Air"
    pg.click("#mapClose")
    walk_row = trip.locator(".tl.walk")
    assert "Genève, Bel-Air (Platform D)" in walk_row.inner_text(), walk_row.inner_text()
    print("following   → platforms tappable: Platform D on the map")

    # The bus moves to platform G: the chip, the walk and its map follow
    LIVE["bus_platform"] = "G"
    pg.clock.run_for(61000); pg.wait_for_timeout(400)
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip = pg.locator("#alarmList .trip").first
    changed = trip.locator(".plat.changed")
    assert changed.count() == 1 and changed.locator(".plat-v").inner_text() == "G", trip.inner_text()
    assert "Genève, Bel-Air (Platform G)" in trip.locator(".tl.walk").inner_text(), trip.locator(".tl.walk").inner_text()
    trip.locator(".walk-map").click()
    a, bb, others = walk_map_ends(pg)
    assert (a, bb) == ("B", "G"), (a, bb)
    assert pg.inner_text("#mapSub") == "Genève, Bel-Air (Platform B) → Genève, Bel-Air (Platform G)", pg.inner_text("#mapSub")
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('on foot at your pace')", timeout=5000)
    pg.screenshot(path=str(OUT / "walk-platform-live.png"))
    pg.click("#mapClose")
    changed.click()
    pg.wait_for_selector("#mapSheet .qm.target")
    assert pg.inner_text("#mapTitle") == "Platform G" and pg.inner_text("#mapSheet .qm.target") == "G"
    pg.click("#mapClose")
    print("live change → bus moved to G: chip, walk label and walk map end on G; position and distance shown")
    ctx.close()

    # BUG-06: the bus leaves from the very platform the tram arrives at: a change on the spot, not a walk
    LIVE.update(planned="B", bus_platform="B")
    ctx, pg = start(b)
    jr = pg.locator("#journeyList .jr").first
    assert jr.locator(".jw").count() == 0, jr.inner_text()             # no walk in the summary line
    detail = pg.locator("#journeyList .jr-detail").first
    assert detail.locator(".leg.walk").count() == 0, detail.inner_text()
    row = detail.locator(".leg.change")
    assert row.count() == 1 and "Same platform, no walking" in row.inner_text() and "5 min wait" in row.inner_text(), row.all_inner_texts()
    assert row.locator(".plat").count() == 0                          # the platform is on the rides above and below
    meta = pg.locator("#journeyList .jr-meta").first.inner_text()
    assert meta.startswith("1 change · no walking"), meta
    pg.screenshot(path=str(OUT / "same-platform-plan.png"))
    pg.click("#journeyList .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip = pg.locator("#alarmList .trip").first
    assert trip.locator(".tl.walk").count() == 0 and "Same platform, no walking" in trip.locator(".tl.change").inner_text(), trip.inner_text()
    assert "5 min wait" in trip.inner_text(), trip.inner_text()          # the change: all waiting, no walking
    # the bus moves to G: it is a walk again, with its map
    LIVE["bus_platform"] = "G"
    pg.clock.run_for(61000); pg.wait_for_timeout(400)
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip = pg.locator("#alarmList .trip").first
    w = trip.locator(".tl.walk")
    assert w.count() == 1 and "Platform changed: go to Genève, Bel-Air (Platform G)" in w.inner_text(), trip.inner_text()
    w.locator(".walk-map").click()
    a, bb, _ = walk_map_ends(pg)
    assert (a, bb) == ("B", "G"), (a, bb)
    pg.screenshot(path=str(OUT / "same-platform-moved.png"))
    print("same quay   → no walk, '5 min wait'; bus moved to G → 'Platform changed', walk map B → G")
    b.close()

print("errors:", errors); assert not errors
print("OK")
