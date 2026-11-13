"""US-38: a followed journey shows every step live, detects a missed connection and offers alternatives (next run of
the same line, another route, finishing on foot). transport.opendata.ch is mocked with live boards that change during
the test; the clock is frozen.

Plan (asked at 07:30): Lancy, Communes-Réunies 07:40 bus 21 → Genève, Plainpalais 07:52, walk 1 min,
tram 12 07:58 (platform C) → Genève, Bel-Air 08:03, walk ~5 min to a point near Bel-Air."""
import os, json, re, datetime as dt
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
COMMUNES = st("8592887", "Lancy, Communes-Réunies", 46.174500, 6.121900)
ACACIAS = st("8587385", "Genève, Acacias", 46.194600, 6.134300)
PLAINPALAIS = st("8587391", "Genève, Plainpalais", 46.198300, 6.141600)
MOLARD = st("8587389", "Genève, Molard", 46.203500, 6.145500)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
DEST = (46.2047, 6.1470)

LIVE = {"bus_delay": 0, "tram_platform": "C"}

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def call(s, arr=None, dep=None): return {"station": s, "arrival": fmt(at(arr)) if arr is not None else None, "departure": fmt(at(dep)) if dep is not None else None}
def section(cat, num, to, calls, a, b, ma, mb, plat=""):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, ma, "departure", plat), "arrival": end(b, mb, "arrival")}
def walk(a, b, ma, mb): return {"journey": None, "walk": {"duration": (mb - ma) * 60}, "departure": end(a, ma, "departure"), "arrival": end(b, mb, "arrival")}

PLAN = {"sections": [
    section("B", "21", "Genève, Plainpalais", [call(COMMUNES, dep=10), call(ACACIAS, 16, 16), call(PLAINPALAIS, arr=22)], COMMUNES, PLAINPALAIS, 10, 22, "A"),
    walk(PLAINPALAIS, PLAINPALAIS, 22, 23),
    section("T", "12", "Genève, Bel-Air", [call(PLAINPALAIS, dep=28), call(MOLARD, 31, 31), call(BELAIR, arr=33)], PLAINPALAIS, BELAIR, 28, 33, "C")]}
REPLAN = {"sections": [section("B", "3", "Genève, Bel-Air", [call(PLAINPALAIS, dep=34), call(BELAIR, arr=39)], PLAINPALAIS, BELAIR, 34, 39, "F")]}

def board_entry(cat, num, to, s, m, delay, plat, nxt):
    """A departure of a live board: `nxt` = [(station, planned minute)], live arrivals = planned + delay."""
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": s, "departure": fmt(at(m)), "departureTimestamp": int(at(m).timestamp()),
                     "prognosis": {"departure": fmt(at(m + delay)), "platform": plat}, "platform": "C" if num == "12" else plat, "delay": delay},
            "passList": [{"station": s}] + [{"station": x, "arrival": fmt(at(mm)), "prognosis": {"arrival": fmt(at(mm + delay))}} for x, mm in nxt]}

def boards(stop_id):
    d = LIVE["bus_delay"]
    if stop_id == COMMUNES["id"]:
        return [board_entry("B", "21", "Genève, Plainpalais", COMMUNES, 5, 0, "A", [(ACACIAS, 11), (PLAINPALAIS, 17)]),   # an earlier run
                board_entry("B", "21", "Genève, Plainpalais", COMMUNES, 10, d, "A", [(ACACIAS, 16), (PLAINPALAIS, 22)])]
    if stop_id == ACACIAS["id"]:
        return [board_entry("B", "21", "Genève, Plainpalais", ACACIAS, 16, d, "", [(PLAINPALAIS, 22)])]
    if stop_id == PLAINPALAIS["id"]:
        return [board_entry("T", "12", "Genève, Bel-Air", PLAINPALAIS, 28, 0, LIVE["tram_platform"], [(MOLARD, 31), (BELAIR, 33)]),
                board_entry("B", "3", "Genève, Bel-Air", PLAINPALAIS, 34, 0, "F", [(BELAIR, 39)]),
                board_entry("T", "12", "Genève, Bel-Air", PLAINPALAIS, 36, 0, "C", [(MOLARD, 39), (BELAIR, 41)])]
    if stop_id == MOLARD["id"]:
        return [board_entry("T", "12", "Genève, Bel-Air", MOLARD, 31, 0, "", [(BELAIR, 33)]), board_entry("T", "12", "Genève, Bel-Air", MOLARD, 39, 0, "", [(BELAIR, 41)])]
    return []

def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        body = {"connections": [REPLAN] if q["from"][0] == PLAINPALAIS["id"] else [PLAN]}
    elif u.path.endswith("/locations"):
        body = {"stations": [dict(BELAIR, distance=300)]}
    else:
        body = {"station": {"id": q["id"][0]}, "stationboard": boards(q["id"][0])}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
def session(b):
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate(f"""() => {{
      localStorage.setItem('tpp:journey:from', JSON.stringify({{ kind: 'stop', id: '8592887', name: 'Lancy, Communes-Réunies', coord: [46.1745, 6.1219] }}));
      localStorage.setItem('tpp:journey:to', JSON.stringify({{ kind: 'point', coord: [{DEST[0]}, {DEST[1]}], near: null }}));
      localStorage.setItem('tpp:settings', JSON.stringify({{ footMaxMin: 0 }}));
      localStorage.setItem('tpp:tab', '"journey"'); }}""")
    pg.reload()
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
    assert pg.inner_text("#journeyList .set-alarms") == "▶ Follow this journey (alarms included)"
    pg.click("#journeyList .set-alarms")
    pg.wait_for_selector("#alarmList .trip")
    return ctx, pg

def refresh(pg):
    """One live refresh (every 60 s), departure alarms dismissed."""
    pg.clock.run_for(61000); pg.wait_for_timeout(300)
def dismiss(pg):
    while pg.is_visible("#alarmBanner") and pg.get_attribute("#alarmBanner", "data-kind") in ("ready", "leave"): pg.click("#abOk")
trip = lambda pg: pg.locator("#alarmList .trip").first

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx, pg = session(b)
    dismiss(pg)
    assert pg.inner_text("#alarmCard .section-title").lower() == "followed journeys", pg.inner_text("#alarmCard .section-title")
    legs = trip(pg).locator(".trip-legs > li")
    assert legs.count() == 4, legs.all_inner_texts()        # bus, walk, tram, walk: the whole journey
    assert "Next: Bus 21 at 07:40 from Lancy, Communes-Réunies (Platform A)" in trip(pg).inner_text(), trip(pg).inner_text()
    arrive0 = re.search(r"Arrive (\d\d:\d\d)", trip(pg).inner_text()).group(1)
    # Stops and time on board, unfoldable, as when planning
    tog = legs.nth(0).locator(".via-toggle")
    assert tog.inner_text().startswith("2 stops · 12 min"), tog.inner_text()
    tog.click()
    assert "07:46" in legs.nth(0).locator(".via").inner_text() and "Genève, Acacias" in legs.nth(0).locator(".via").inner_text()
    assert "get off at the next stop" in legs.nth(0).locator(".via li").last.inner_text()
    print("followed    →", trip(pg).locator(".trip-head").inner_text(), "|", trip(pg).locator(".trip-now").inner_text())

    # Live: the tram's platform changes → shown and rung once
    LIVE["tram_platform"] = "D"
    refresh(pg)
    assert pg.get_attribute("#alarmBanner", "data-kind") == "trip" and "Tram 12 now leaves from Platform D" in pg.inner_text("#abBody"), pg.inner_text("#alarmBanner")
    pg.click("#abOk")
    # the new platform is a button (tap → map), the old one in brackets (BUG-05)
    assert legs.nth(2).locator(".plat.changed .plat-v").inner_text() == "D" and "(was C)" in legs.nth(2).inner_text() \
        and legs.nth(2).locator(".changed").count() == 1, legs.nth(2).inner_text()
    refresh(pg); assert pg.is_hidden("#alarmBanner"), "the same platform change rings only once"

    # Live: bus 21 is 9 min late → arrives 08:01, +1 min walk: the 07:58 tram is missed
    LIVE["bus_delay"] = 9
    refresh(pg)
    dismiss(pg)
    assert pg.get_attribute("#alarmBanner", "data-kind") == "trip" and "Connection missed" in pg.inner_text("#abTitle"), pg.inner_text("#alarmBanner")
    pg.click("#abOk")
    # the unfolded stops stay open across live refreshes and show the live times
    assert legs.nth(0).locator(".via").is_visible() and "07:55" in legs.nth(0).locator(".via").inner_text(), legs.nth(0).inner_text()
    assert legs.nth(0).locator(".via-toggle").inner_text().startswith("2 stops · 12 min")
    print("stops       →", legs.nth(0).locator(".via-toggle").inner_text(), "|", legs.nth(0).locator(".via").inner_text().replace("\n", " "))
    warn = trip(pg).locator(".trip-warn").inner_text()
    assert "Connection missed at Genève, Plainpalais" in warn and "You arrive at 08:02, the Tram 12 leaves at 07:58." in warn, warn
    assert "07:40" in legs.nth(0).inner_text() and "07:49" in legs.nth(0).inner_text(), "planned time struck through, live time shown"
    assert "connection missed: choose an alternative" in trip(pg).locator(".trip-head").inner_text()
    alts = trip(pg).locator(".trip-alt")
    texts = alts.all_inner_texts()
    print("missed      →", warn.split("\n")[1], "|", [x.replace("\n", " · ") for x in texts])
    assert any(x.startswith("Tram 12 next run at 08:06") for x in texts), texts
    assert any(x.startswith("Other route: Bus 3 at 08:04") for x in texts), texts
    assert any(x.startswith("🚶 Finish on foot from Genève, Plainpalais") for x in texts), texts
    arrivals = [re.search(r"arrive (\d\d:\d\d)", x).group(1) for x in texts]
    assert arrivals == sorted(arrivals), arrivals                      # earliest first
    pg.screenshot(path=str(OUT / "trip-missed.png"), full_page=True)

    # Take the next tram: the rest of the journey follows it, no more warning, reminders updated
    alts.filter(has_text="Tram 12 next run").click()
    assert "Journey updated" in pg.inner_text("#toast") and pg.is_hidden("#toastUndo")
    assert trip(pg).locator(".trip-warn").count() == 0, trip(pg).inner_text()
    assert "08:06" in legs.nth(2).inner_text(), legs.nth(2).inner_text()
    plan = pg.inner_text("#alarmList [data-k=alights]")
    assert "Genève, Bel-Air 08:09" in plan, plan                     # leaves Molard at 08:09 on the next run
    arrive1 = re.search(r"Arrive (\d\d:\d\d)", trip(pg).inner_text()).group(1)
    assert arrive1 > arrive0, (arrive0, arrive1)
    refresh(pg)                                                        # live data does not undo the choice
    assert "08:06" in legs.nth(2).inner_text() and trip(pg).locator(".trip-warn").count() == 0
    print("next tram   → arrive", arrive0, "→", arrive1, "|", plan)
    pg.screenshot(path=str(OUT / "trip-updated.png"), full_page=True)

    # On board (07:52, after Acacias 07:55? no: bus 9 min late leaves 07:49, Acacias 07:55): next stop marked
    pg.clock.run_for(20 * 60000 - 4 * 61000); pg.wait_for_timeout(300)
    dismiss(pg)
    if pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pg.evaluate("document.querySelectorAll('#alarmList .via-toggle')[0].getAttribute('aria-expanded') === 'true' || document.querySelectorAll('#alarmList .via-toggle')[0].click()")
    first = trip(pg).locator(".trip-legs > li").nth(0)
    print("on board    →", first.locator(".chip").inner_text() if first.locator(".chip").count() else "-", "|", first.locator(".via").inner_text().replace("\n", " "))
    assert "on board" in first.locator(".chip").inner_text()
    assert first.locator(".via li.here").count() == 1 or first.locator(".via li.passed").count() == 1

    # Walks of the followed journey on the map
    pg.clock.resume()
    trip(pg).locator(".walk-map").last.click()
    pg.wait_for_selector(".wm.b"); assert "Walk" in pg.inner_text("#mapTitle"); pg.click("#mapClose")
    ctx.close()

    # Another session: same delay, finish on foot from the change stop instead
    LIVE.update(bus_delay=9, tram_platform="C")
    ctx, pg = session(b); dismiss(pg)
    refresh(pg); dismiss(pg)
    if pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip(pg).locator(".trip-alt", has_text="Finish on foot").click()
    legs = trip(pg).locator(".trip-legs > li")
    assert legs.count() == 2 and "to your destination" in legs.nth(1).inner_text(), legs.all_inner_texts()   # bus 21, then on foot
    plan = pg.inner_text("#alarmList [data-k=alights]")
    assert "Plainpalais" in plan and "Bel-Air" not in plan, plan
    print("on foot     →", trip(pg).locator(".trip-head").inner_text(), "|", plan)
    # French
    pg.select_option("#lang", "fr"); assert "trajets suivis" in pg.inner_text("#alarmCard").lower() and "Finir à pied" not in pg.inner_text("#alarmCard"); pg.select_option("#lang", "en")
    ctx.close()

    # US-39: a tight change (bus 5 min late: arrives 07:57, 1 min walk, tram at 07:58) — plain wording, comfortable options
    LIVE.update(bus_delay=5, tram_platform="C")
    ctx, pg = session(b); dismiss(pg)
    refresh(pg); dismiss(pg)
    pg.wait_for_function("document.querySelector('#alarmList .trip-warn') && document.querySelectorAll('#alarmList .trip-alt').length > 0")
    warn = trip(pg).locator(".trip-warn").inner_text()
    assert "Tight connection at Genève, Plainpalais" in warn, warn
    assert "1 min walk in the 1 min between your arrival (07:57) and the departure (07:58): no time to spare — the slightest delay and you miss it." in warn, warn
    opts = trip(pg).locator(".trip-alt").all_inner_texts()
    assert any(o.startswith("Earlier Bus 21 at 07:35") and "10 min margin at the change · leave 07:34" in o for o in opts), opts
    assert any(o.startswith("Tram 12 next run at 08:06") and "8 min margin" in o for o in opts), opts
    legs = trip(pg).locator(".trip-legs > li")
    assert "Change: 1 min walk, no time to spare" in legs.nth(2).inner_text(), legs.nth(2).inner_text()
    print("tight       →", warn.split("\n")[1], "|", [o.replace("\n", " · ") for o in opts])
    pg.screenshot(path=str(OUT / "trip-tight.png"), full_page=True)
    # take the earlier bus: departure alarms move with it, the change becomes comfortable, the wait is shown live
    trip(pg).locator(".trip-alt", has_text="Earlier Bus 21").click()
    assert trip(pg).locator(".trip-warn").count() == 0, trip(pg).inner_text()
    assert "07:35" in pg.locator("#alarmList .al-times").inner_text(), pg.locator("#alarmList .al-times").inner_text()
    assert "Change: 1 min walk, then 10 min wait" in legs.nth(2).inner_text(), legs.nth(2).inner_text()
    print("earlier bus →", pg.locator("#alarmList .al-times").inner_text().replace("\n", " "), "|", legs.nth(2).locator(".wait").inner_text())
    ctx.close()

    # Another route (back to the missed case)
    LIVE.update(bus_delay=9, tram_platform="C")
    ctx, pg = session(b); dismiss(pg)
    refresh(pg); dismiss(pg)
    if pg.is_visible("#alarmBanner"): pg.click("#abOk")
    trip(pg).locator(".trip-alt", has_text="Other route").click()
    legs = trip(pg).locator(".trip-legs > li")
    assert "Bus 3" in trip(pg).inner_text() or legs.filter(has_text="3").count(), trip(pg).inner_text()
    assert trip(pg).locator(".trip-warn").count() == 0
    print("other route →", trip(pg).locator(".trip-head").inner_text(), "|", [x.split("\n")[0] for x in legs.all_inner_texts()])
    ctx.close()
    b.close()

print("errors:", errors); assert not errors
print("OK")
