"""PO 23.11.2026: the warning of a missed connection is sent once its alternatives are found, with the best one, so
that opening the app shows them at once. If the search takes more than 20 s the warning goes anyway ("Looking for
alternatives…") and the alternatives fill the followed journey when they come; it is not sent twice.
The same rule holds for a cancelled vehicle and a late start (test_cancelled_run, test_late_start check their texts).

Same plan and live boards as test_followed_journey: bus 21 9 min late → the 07:58 tram 12 at Plainpalais is missed.
The route search from Plainpalais (another route) is held back to see when the warning comes."""
import os, json, re, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
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

HELD = []   # replies about the change stop (its departures, routes from it), held back to time the warning
HOLD = {"on": False, "board": True}
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if HOLD["on"] and u.path.endswith("/connections") and q["from"][0] == PLAINPALAIS["id"]:
        HELD.append((route, {"connections": [REPLAN]})); return
    if HOLD["on"] and HOLD["board"] and u.path.endswith("/stationboard") and q["id"][0] == PLAINPALAIS["id"]:
        HELD.append((route, {"station": {"id": q["id"][0]}, "stationboard": boards(q["id"][0])})); return
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
    pg.click("#journeyList .set-alarms")
    pg.wait_for_selector("#alarmList .trip")
    return ctx, pg

def dismiss(pg):
    while pg.is_visible("#alarmBanner") and pg.get_attribute("#alarmBanner", "data-kind") in ("ready", "leave"): pg.click("#abOk")
trip = lambda pg: pg.locator("#alarmList .trip").first
warned = lambda pg: pg.is_visible("#alarmBanner") and pg.get_attribute("#alarmBanner", "data-kind") == "trip"
def release():
    while HELD:
        route, body = HELD.pop(0)
        try: route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
        except Exception: pass   # already given up by the page (its 10 s timeout)
def settle(pg, ms=600):
    for _ in range(6): pg.wait_for_timeout(ms // 6); release()
def held_now(pg):
    for _ in range(50):
        if HELD: return True
        pg.wait_for_timeout(100)
    return False

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # A. alternatives found quickly: no warning while they are looked for, then one warning naming the best
    LIVE.update(bus_delay=0); HOLD.update(on=False, board=True); HELD.clear()
    ctx, pg = session(b); dismiss(pg)
    LIVE["bus_delay"] = 9; HOLD["on"] = True
    pg.clock.run_for(61000)
    assert held_now(pg), "the change stop's departures were asked"
    dismiss(pg)
    assert not warned(pg), "no warning while the alternatives are looked for: " + pg.inner_text("#alarmBanner")
    release()                                   # its departures (next run of the tram)...
    assert held_now(pg), "then the routes from it"
    assert not warned(pg), "no warning while the alternatives are looked for: " + pg.inner_text("#alarmBanner")
    HOLD["on"] = False; release()               # ...and the routes from it: now the warning
    pg.wait_for_function("() => { const b = document.getElementById('alarmBanner'); return !b.hidden && b.dataset.kind === 'trip'; }")
    title, body = pg.inner_text("#abTitle"), pg.inner_text("#abBody")
    assert "Connection missed" in title, title
    assert body == ("At Genève, Plainpalais: Tram 12 leaves at 07:58, you arrive at 08:02. "
                    "Best: Other route: Bus 3 at 08:04, arrive 08:13. Other choices in the app."), body
    pg.click("#abOk")
    pg.wait_for_selector("#alarmList .trip .trip-alt")
    alts = trip(pg).locator(".trip-alt").all_inner_texts()
    assert "Looking for alternatives" not in trip(pg).inner_text() and alts[0].startswith("Other route: Bus 3 at 08:04"), alts
    print("found       →", body, "|", [x.replace("\n", " · ") for x in alts])
    pg.clock.run_for(61000); settle(pg)
    assert not warned(pg), "warned once only"
    HOLD["on"] = False; release(); ctx.close()

    # B. a route search that does not answer for more than 20 s (a slow server: the page's own 10 s timeout is
    #    switched off here): the warning goes after 20 s anyway, the alternatives come after it, no second warning
    LIVE.update(bus_delay=0); HOLD.update(on=False, board=False); HELD.clear()
    ctx, pg = session(b); dismiss(pg)
    pg.evaluate("() => { AbortController.prototype.abort = function () {}; }")
    LIVE["bus_delay"] = 9; HOLD["on"] = True
    pg.clock.run_for(61000)
    assert held_now(pg)
    dismiss(pg)
    pg.clock.run_for(15000); pg.wait_for_timeout(400)
    assert not warned(pg), "not before 20 s: " + pg.inner_text("#alarmBanner")
    pg.clock.run_for(6000)
    pg.wait_for_function("() => { const b = document.getElementById('alarmBanner'); return !b.hidden && b.dataset.kind === 'trip'; }")
    body = pg.inner_text("#abBody")
    assert body == "At Genève, Plainpalais: Tram 12 leaves at 07:58, you arrive at 08:02. Looking for alternatives…", body
    pg.click("#abOk")
    HOLD["on"] = False; release()
    pg.wait_for_selector("#alarmList .trip .trip-alt")
    alts = trip(pg).locator(".trip-alt").all_inner_texts()
    assert "Looking for alternatives" not in trip(pg).inner_text() and alts[0].startswith("Other route: Bus 3 at 08:04"), alts
    pg.clock.run_for(61000); settle(pg)
    assert not warned(pg), "warned once only: " + pg.inner_text("#alarmBanner")
    print("no answer   →", body, "| then", [x.replace("\n", " · ") for x in alts])
    HOLD["on"] = False; release(); ctx.close()
    b.close()

print("errors:", errors)
assert not errors
print("OK")
