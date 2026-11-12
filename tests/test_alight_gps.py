"""US-35: get-off reminders follow the live time of each ride (departure board of the stop before the get-off
stop) and, while the page is open, the rider's position. transport.opendata.ch is mocked; the clock is frozen.

Journey: Lancy, Communes-Réunies 07:46 → tram 15 → Genève, gare Cornavin 08:01; the stop before Cornavin is
Bel-Air, planned 07:58. Its live board says 08:01 (+3 min)."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)
ms = lambda m: int(m * 60000)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
COMMUNES = st("8592887", "Lancy, Communes-Réunies", 46.174500, 6.121900)
ACACIAS = st("8587385", "Genève, Acacias", 46.194600, 6.134300)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORNAVIN = st("8587057", "Genève, gare Cornavin", 46.209733, 6.142437)
HOME = (46.1700, 6.1150)
AT_BELAIR = (46.204800, 6.143000)                  # ~10 m from the Bel-Air stop
PAST_BELAIR = (46.206100, 6.142800)                # ~150 m further, towards Cornavin

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
TRAM = {"journey": {"category": "T", "number": "15", "to": "Genève, Nations", "operator": "TPG", "passList": [
            {"station": COMMUNES, "departure": fmt(at(16))},
            {"station": ACACIAS, "arrival": fmt(at(22)), "departure": fmt(at(22))},
            {"station": BELAIR, "arrival": fmt(at(28)), "departure": fmt(at(28))},
            {"station": CORNAVIN, "arrival": fmt(at(31))}]},
        "walk": None, "departure": end(COMMUNES, 16, "departure", "A"), "arrival": end(CORNAVIN, 31, "arrival")}
BELAIR_BOARD = {"station": BELAIR, "stationboard": [
    {"category": "T", "number": "15", "to": "Genève, Nations", "operator": "TPG",
     "stop": {"station": BELAIR, "departure": fmt(at(28)), "departureTimestamp": int(at(28).timestamp()),
              "prognosis": {"departure": fmt(at(31))}, "platform": "E", "delay": 3},
     "passList": [{"station": BELAIR}, {"station": CORNAVIN, "arrival": fmt(at(34))}]}]}
board_calls = []

def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [{"sections": [TRAM]}]}
    elif u.path.endswith("/stationboard"):
        board_calls.append(q["id"][0])
        body = BELAIR_BOARD if q["id"][0] == BELAIR["id"] else {"station": COMMUNES, "stationboard": []}
    else: body = {"stations": [COMMUNES]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
def session(b, gps):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="en-US", timezone_id="Europe/Zurich",
                        **({"geolocation": {"latitude": HOME[0], "longitude": HOME[1], "accuracy": 10}, "permissions": ["geolocation"]} if gps else {}))
    ctx.route("https://transport.opendata.ch/**", api)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate("""() => {
      localStorage.setItem('tpp:journey:from', JSON.stringify({ kind: 'stop', id: '8592887', name: 'Lancy, Communes-Réunies', coord: [46.1745, 6.1219] }));
      localStorage.setItem('tpp:journey:to', JSON.stringify({ kind: 'stop', id: '8587057', name: 'Genève, gare Cornavin', coord: [46.209733, 6.142437] }));
      localStorage.setItem('tpp:tab', '"journey"'); }""")
    pg.reload()
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click(); pg.click(".set-alarms")
    pg.wait_for_selector("#alarmList [data-k=alights]")
    return ctx, pg

def go(pg, until_min, where=None):
    """Advance the clock to NOW + until_min (departure alarms dismissed on the way), sending a fresh position
    every 10 s when `where` is given; stops early if a get-off reminder rings."""
    while True:
        if banner(pg) in ("ready", "leave"): pg.click("#abOk")
        if banner(pg) == "alight": break
        now = pg.evaluate("Date.now()")
        left = NOW.timestamp() * 1000 + ms(until_min) - now
        if left <= 0: break
        if where:
            pg.context.set_geolocation({"latitude": where[0] + (now % 7) * 1e-7, "longitude": where[1], "accuracy": 8})
            pg.wait_for_timeout(150)
        pg.clock.run_for(int(min(left, 10000)))

def banner(pg): return None if pg.is_hidden("#alarmBanner") else pg.get_attribute("#alarmBanner", "data-kind")

def move(pg, where):
    pg.context.set_geolocation({"latitude": where[0], "longitude": where[1], "accuracy": 8})
    pg.wait_for_timeout(400)          # the position reaches the page in real time
    pg.clock.run_for(2000)


def dismiss_departure_alarms(pg):
    if banner(pg) in ("ready", "leave"): pg.click("#abOk")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # 1. No position allowed: the live time of the stop before decides (08:01, not the planned 07:58)
    ctx, pg = session(b, gps=False)
    pg.clock.run_for(65000)                                        # one live refresh
    pg.wait_for_function("document.querySelector('#alarmList [data-k=alights]').textContent.includes('(live)')")
    plan = pg.inner_text("#alarmList [data-k=alights]")
    assert plan == "Get-off reminders: Genève, gare Cornavin 08:01 (live)", plan
    assert BELAIR["id"] in board_calls, "the stop before the get-off stop is followed live"
    assert "Position not allowed" in pg.inner_text("#alarmList"), pg.inner_text("#alarmList")
    for minute in (15.5, 20, 27.9):                                 # departure alarms ring on the way
        go(pg, minute); dismiss_departure_alarms(pg)
    go(pg, 30.8); dismiss_departure_alarms(pg)
    assert banner(pg) is None, "not at the planned 07:58"
    go(pg, 31.2)
    assert banner(pg) == "alight", banner(pg)
    print("live only   → planned 07:58, rang at", pg.evaluate("new Date().toTimeString().slice(0,5)"), "(live 08:01)")
    ctx.close()

    # 2. Position: rings as soon as the tram leaves Bel-Air, even before the live time says so
    ctx, pg = session(b, gps=True)
    go(pg, 14, AT_BELAIR); move(pg, PAST_BELAIR)
    assert banner(pg) in (None, "ready", "leave"), "near Bel-Air before boarding: no get-off reminder"
    go(pg, 16.5, HOME)
    go(pg, 29.5, AT_BELAIR)
    assert banner(pg) is None
    assert "Following your position" in pg.inner_text("#alarmList"), pg.inner_text("#alarmList")
    move(pg, PAST_BELAIR)
    assert banner(pg) == "alight", banner(pg)
    rang = pg.evaluate("new Date().toTimeString().slice(0,5)")
    pg.click("#abOk")
    assert "Genève, gare Cornavin 08:01 (live) ✓📍" in pg.inner_text("#alarmList [data-k=alights]"), pg.inner_text("#alarmList")
    print("position    → rang at", rang, "when leaving Bel-Air (live time 08:01)")
    ctx.close()

    # 3. Position holds the reminder back while the tram is still at Bel-Air after the live time
    ctx, pg = session(b, gps=True)
    go(pg, 16.5, HOME); dismiss_departure_alarms(pg)
    go(pg, 33, AT_BELAIR); dismiss_departure_alarms(pg)
    assert banner(pg) is None, "still at Bel-Air at 08:03: no reminder yet"
    move(pg, PAST_BELAIR)
    assert banner(pg) == "alight"
    print("held back   → still at Bel-Air at 08:03, rang when leaving at", pg.evaluate("new Date().toTimeString().slice(0,5)"))
    ctx.close()

    # 4. No fresh position (tunnel): the live time decides again
    ctx, pg = session(b, gps=True)
    go(pg, 16.5, HOME); dismiss_departure_alarms(pg)
    go(pg, 25, AT_BELAIR); dismiss_departure_alarms(pg)            # last fix at 07:55, then nothing
    go(pg, 31.2); dismiss_departure_alarms(pg)
    assert banner(pg) == "alight", banner(pg)
    print("no signal   → rang at", pg.evaluate("new Date().toTimeString().slice(0,5)"), "from the live time")
    ctx.close()
    b.close()

print("errors:", errors); assert not errors
print("OK")
