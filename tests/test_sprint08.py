"""Sprint 8: journey details inside the result (US-28), line colours (US-29), intermediate stops (US-30),
get-off reminders (US-31), walks on a map (US-32), merged walks (BUG-03). The browser clock is frozen."""
import os, json, re, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-08-journey-details/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188100, 6.113100)
PONTROUGE = st("8587390", "Lancy, Pont-Rouge", 46.1902, 6.1272)
ACACIAS = st("8587385", "Genève, Acacias", 46.1946, 6.1343)
PLAINPALAIS = st("8587391", "Genève, Plainpalais", 46.1983, 6.1416)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
COUTANCE = st("8587392", "Genève, Coutance", 46.2070, 6.1425)
CORNAVIN = st("8587057", "Genève, gare Cornavin", 46.209733, 6.142437)
PREMONNARD = st("8592993", "Petit-Lancy, Pré-Monnard", 46.191000, 6.118000)
HOME = (46.189000, 6.115000)     # a point ~170 m from Les Esserts

def call(s, arr=None, dep=None, prog_dep=None):
    c = {"station": s, "arrival": fmt(at(arr)) if arr is not None else None, "departure": fmt(at(dep)) if dep is not None else None,
         "prognosis": {"departure": fmt(at(prog_dep)) if prog_dep is not None else None}}
    return c
def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, calls, a, b, ma, mb, plat, arr_plat):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls},
            "walk": None, "departure": end(a, ma, "departure", plat), "arrival": end(b, mb, "arrival", arr_plat)}
def walk(a, b, ma, mb):
    return {"journey": None, "walk": {"duration": (mb - ma) * 60}, "departure": end(a, ma, "departure"), "arrival": end(b, mb, "arrival")}

BUS21 = ride("B", "21", "Genève, Bel-Air", [call(ESSERTS, dep=9), call(PONTROUGE, 13, 13), call(ACACIAS, 17, 17), call(PLAINPALAIS, 21, 21), call(BELAIR, arr=25)],
             ESSERTS, BELAIR, 9, 25, "C", "D")
TRAM15 = ride("T", "15", "Genève, Nations", [call(BELAIR, dep=29), call(COUTANCE, 31, 31, prog_dep=32), call(CORNAVIN, arr=36)],
              BELAIR, CORNAVIN, 29, 36, "E", "")
TRAM14 = ride("T", "14", "Meyrin, Gravière", [call(ESSERTS, dep=14), call(PONTROUGE, 18, 18), call(BELAIR, 27, 27), call(CORNAVIN, arr=31)],
              ESSERTS, CORNAVIN, 14, 31, "B", "")
CONNECTIONS = {("8587418", "8587057"): [
    {"sections": [walk(ESSERTS, ESSERTS, 8, 9), BUS21, walk(BELAIR, BELAIR, 25, 28), TRAM15]},   # API walk at the start + a change
    {"sections": [TRAM14]}]}

def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/locations"):
        if "x" in q: body = {"stations": [dict(ESSERTS, distance=170), dict(PREMONNARD, distance=330)]}
        else:
            name = q["query"][0].lower()
            body = {"stations": [dict(s, icon="tram") for s in (ESSERTS, CORNAVIN) if any(w in s["name"].lower() for w in name.split())]}
    elif u.path.endswith("/connections"):
        body = {"connections": CONNECTIONS.get((q["from"][0], q["to"][0]), [])}
    else:
        body = {"station": ESSERTS, "stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def rgb(hex_):
    h = hex_.lstrip("#"); return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="en-US", timezone_id="Europe/Zurich",
                        geolocation={"latitude": HOME[0], "longitude": HOME[1], "accuracy": 10}, permissions=["geolocation"])
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate(f"""() => {{
      localStorage.setItem('tpp:journey:from', JSON.stringify({{ kind: 'point', coord: [{HOME[0]}, {HOME[1]}], near: null }}));
      localStorage.setItem('tpp:journey:to', JSON.stringify({{ kind: 'stop', id: '8587057', name: 'Genève, gare Cornavin', coord: [46.209733, 6.142437] }}));
      localStorage.setItem('tpp:tab', '"journey"'); }}""")
    pg.reload()
    pg.click("#searchJourney"); pg.wait_for_selector(".jr")
    assert pg.locator("#journeyDetail").count() == 0, "no detail card at the bottom any more"
    items = pg.locator("#journeyList li.jr-item")
    change = [i for i in range(items.count()) if "1 change" in items.nth(i).inner_text()][0]
    direct = 1 - change if items.count() == 2 else [i for i in range(items.count()) if i != change][0]

    # BUG-03: the walk to the stop and the walk returned by the service are one walk in the summary
    segs = items.nth(change).locator(".jr-segs").inner_text()
    assert not re.search(r"🚶[^›]*›\s*🚶", segs), segs
    print("summary     →", segs.replace("\n", " "))

    # US-28: details open under the tapped journey, one at a time, toggled by a second tap
    items.nth(change).locator(".jr").click()
    assert items.nth(change).locator(".jr-detail").count() == 1 and pg.locator(".jr-detail").count() == 1
    assert items.nth(change).locator(".jr").get_attribute("aria-expanded") == "true"
    items.nth(direct).locator(".jr").click()
    assert pg.locator(".jr-detail").count() == 1 and items.nth(direct).locator(".jr-detail").count() == 1
    items.nth(direct).locator(".jr").click()
    assert pg.locator(".jr-detail").count() == 0
    items.nth(change).locator(".jr").click()
    detail = items.nth(change).locator(".jr-detail")
    legs = detail.locator(".legs > li")
    kinds = [("walk" if "walk" in (legs.nth(i).get_attribute("class") or "") else "ride") for i in range(legs.count())]
    print("legs        →", kinds)
    assert kinds == ["walk", "ride", "walk", "ride"], kinds          # BUG-03: one walk before the bus
    first_walk = legs.nth(0).inner_text()
    assert "Walk 3 min" in first_walk or "Walk 4 min" in first_walk, first_walk   # ~2.6 min to the stop + 1 min from the service

    # US-29: each ride drawn in its TPG colour
    colors = pg.evaluate("window.LINE_COLORS.networks.TPG")
    for i, label in ((1, "21"), (3, "15")):
        border = legs.nth(i).evaluate("e => getComputedStyle(e).borderLeftColor")
        assert border == rgb(colors[label][0]), (label, border, colors[label][0])
    assert "dotted" in legs.nth(2).evaluate("e => getComputedStyle(e).borderLeftStyle")
    print("colours     → 21", colors["21"][0], "· 15", colors["15"][0])

    # US-30: intermediate stops unfold with their times; the stop before getting off is marked
    tog = legs.nth(1).locator(".via-toggle")
    assert tog.inner_text().startswith("4 stops") and legs.nth(1).locator(".via").is_hidden()
    tog.click()
    via = legs.nth(1).locator(".via")
    assert via.is_visible()
    vtext = via.inner_text()
    assert "07:43" in vtext and "Lancy, Pont-Rouge" in vtext and "Genève, Acacias" in vtext, vtext
    assert "get off at the next stop" in legs.nth(1).locator(".via li").last.inner_text()
    legs.nth(3).locator(".via-toggle").click()
    assert "08:02" in legs.nth(3).locator(".via").inner_text(), "live time of an intermediate stop"
    # still open, with the same stops unfolded, after the list is redrawn (priority change)
    pg.click("#prio button[data-prio='walk']"); pg.click("#prio button[data-prio='fast']")
    opened = pg.locator("#journeyList li.jr-item:has(.jr-detail)")
    assert opened.count() == 1 and opened.locator(".via:visible").count() == 2
    print("stops       →", vtext.replace("\n", " "))
    pg.screenshot(path=str(OUT / "sprint08-detail.png"), full_page=True)

    # US-32: the change at Bel-Air on the map, from platform D to platform E
    pg.clock.resume()
    legs = opened.locator(".legs > li")
    legs.nth(2).locator(".walk-map").click()
    pg.wait_for_selector(".wm.a"); pg.wait_for_selector(".wm.b")
    sub = pg.inner_text("#mapSub")
    assert sub == "Genève, Bel-Air (Platform D) → Genève, Bel-Air (Platform E)", sub
    href = pg.get_attribute("#walkThere", "href")
    assert "origin=46.204236,6.142057" in href and "destination=46.203912,6.143835" in href, href   # ATLAS positions of D and E
    assert pg.inner_text("#walkThere").strip() == "🚶 Directions"
    print("walk map    →", pg.inner_text("#mapTitle"), "|", sub, "|", pg.inner_text("#mapInfo"))
    pg.screenshot(path=str(OUT / "sprint08-walk-map.png"))
    pg.click("#mapClose")
    legs.nth(0).locator(".walk-map").click(); pg.wait_for_selector(".wm.b")
    assert pg.inner_text("#mapSub") == "Your start → Petit-Lancy, Les Esserts (Platform C)", pg.inner_text("#mapSub")
    pg.click("#mapClose")
    pg.clock.install(time=NOW.timestamp() + 60)

    # US-31: the switch is in Settings and on by default
    pg.click("#settingsBtn")
    assert pg.is_checked("#setAlight")
    pg.click("#settingsClose")

    # Set alarms from inside the open journey: get-off reminders planned for each ride
    opened.locator(".set-alarms").click()
    pg.wait_for_selector("#alarmList .alarm")
    plan = pg.inner_text("#alarmList [data-k=alights]")
    assert plan == "Get-off reminders: Genève, Bel-Air 07:51 · Genève, gare Cornavin 08:02", plan
    print("reminders   →", plan)

    # 07:51: the bus leaves Plainpalais, the stop before Bel-Air
    pg.clock.run_for(int((at(21) - NOW).total_seconds() * 1000) - 60000 + 6000)
    pg.wait_for_function("document.getElementById('abTitle').textContent.includes('get off')")
    body = pg.inner_text("#abBody")
    assert body == "Get off at Genève, Bel-Air and change to Tram 15 (Platform E) at 07:59.", body
    print("07:51       →", pg.inner_text("#abTitle"), "|", body)
    pg.click("#abOk")
    # Switched off: nothing rings at 08:02, and the alarm says so
    pg.click("#settingsBtn"); pg.uncheck("#setAlight"); pg.click("#settingsClose")
    assert "Get-off reminders are off" in pg.inner_text("#alarmList")
    pg.clock.run_for(11 * 60000)
    assert pg.is_hidden("#alarmBanner"), pg.inner_text("#alarmBanner")
    pg.click("#settingsBtn"); pg.check("#setAlight"); pg.click("#settingsClose")
    pg.clock.run_for(10000)
    assert pg.is_hidden("#alarmBanner"), "a reminder missed while switched off does not ring later"
    # Test button
    pg.click("#alarmList [data-act=test-alight]")
    assert "get off" in pg.inner_text("#abTitle")
    pg.click("#abOk")

    # French
    pg.click("#lang")
    assert "Plan" in pg.inner_text("#journeyList .walk-map >> nth=0")
    assert "descendez au prochain arrêt" in pg.inner_text("#journeyList")
    pg.click("#lang")

    # OJP answers carry the times of the intermediate stops too
    pg.add_script_tag(path=str(ROOT / "assets/ojp.js"))
    times = pg.evaluate("x => { const c = OJP_ADAPTER.toConnections(x).connections[0]; const r = c.sections.find(s => s.journey); "
                        "return r.journey.passList.map(p => [p.station.name, p.arrival, p.departure, p.prognosis.departure]); }",
                        (ROOT / "tests/fixtures/ojp-sprint07/app_tr_depart.xml").read_text())
    assert len(times) >= 3 and all(t[1] or t[2] for t in times), times
    print("OJP stops   →", times[1])
    b.close()

print("errors:", errors); assert not errors
print("OK")
