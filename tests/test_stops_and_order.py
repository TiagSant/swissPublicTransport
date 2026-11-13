"""BUG-09: (1) a followed ride's intermediate stops keep credible times and grey out as they are passed (by time,
and by position when known); (2) the journey list keeps its order while later work changes times.

(1) Tram 17 Uni-Mail planned 16:28, 5 min late when the journey is followed (as in the PO's screenshot); stops
    Acacias +2, Industrielle +4, Pictet-Thellusson +6, arrival Lancy-Pont-Rouge +7 (planned). The board refresh
    gives no live times for the stops: their times = planned + 5, not + 10.
(2) Two journeys to an address; the walk from the first one's stop turns out long along the streets."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, urlsplit, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
UNIMAIL = st("8592858", "Genève, Uni-Mail", 46.1953, 6.1398)
ACACIAS = st("8592802", "Genève, Acacias", 46.1925, 6.1365)
INDUS = st("8592855", "Genève, Industrielle", 46.1905, 6.1330)
PICTET = st("8592871", "Carouge GE, Pictet-Thellusson", 46.1885, 6.1300)
LPR = st("8516155", "Lancy-Pont-Rouge, gare", 46.1867, 6.1257)
X = st("8587901", "Genève, Stop X", 46.2010, 6.1450)
Y = st("8587902", "Genève, Stop Y", 46.2000, 6.1470)
DEST = (46.2005, 6.1460)
S = {}
def at(m): return S["base"] + dt.timedelta(minutes=m)
def end(s, m, kind, plat, live=None):
    e = {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
    if live is not None: e["prognosis"] = {kind: fmt(at(m + live))}; e["delay"] = live
    return e
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if S["case"] == 1:
        if u.path.endswith("/connections"):
            calls = [{"station": UNIMAIL, "departure": fmt(at(8)), "prognosis": {"departure": fmt(at(13))}}] + \
                    [{"station": s, "arrival": fmt(at(m)), "arrivalTimestamp": int(at(m).timestamp()), "prognosis": {"arrival": fmt(at(m + 5))}} for s, m in ((ACACIAS, 10), (INDUS, 12), (PICTET, 14))] + \
                    [{"station": LPR, "arrival": fmt(at(15)), "prognosis": {"arrival": fmt(at(20))}}]
            body = {"connections": [{"sections": [{"journey": {"category": "T", "number": "17", "to": "Lancy-Pont-Rouge, gare", "operator": "TPG", "passList": calls},
                                                   "walk": None, "departure": end(UNIMAIL, 8, "departure", "O", 5), "arrival": end(LPR, 15, "arrival", "A", 5)}]}]}
        elif u.path.endswith("/stationboard") and q["id"][0] == UNIMAIL["id"]:
            t0 = at(8)
            body = {"stationboard": [{"category": "T", "number": "17", "to": "Lancy-Pont-Rouge, gare", "operator": "TPG",
                     "stop": {"station": UNIMAIL, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": "O", "delay": 5,
                              "prognosis": {"departure": fmt(t0 + dt.timedelta(minutes=5))}},
                     # no live times for the stops, as with official data
                     "passList": [{"station": UNIMAIL}] + [{"station": s, "arrival": fmt(at(m)), "prognosis": {}} for s, m in ((ACACIAS, 10), (INDUS, 12), (PICTET, 14))] +
                                 [{"station": LPR, "arrival": fmt(at(15)), "prognosis": {"arrival": fmt(at(20))}}]}]}
        else: body = {"stations": [LPR], "stationboard": []}
    else:
        if u.path.endswith("/connections"):
            to = X if q["to"][0] == X["id"] else Y
            m1 = 20 if to is X else 21
            calls = [{"station": UNIMAIL, "departure": fmt(at(10))}, {"station": to, "arrival": fmt(at(m1))}]
            body = {"connections": [{"sections": [{"journey": {"category": "B", "number": "1" if to is X else "3", "to": to["name"], "operator": "TPG", "passList": calls},
                                                   "walk": None, "departure": end(UNIMAIL, 10, "departure", "A"), "arrival": end(to, m1, "arrival", "")}]}]}
        elif "x" in q: body = {"stations": [dict(X, distance=120), dict(Y, distance=100)]}
        else: body = {"stations": [], "stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
held = []
def osrm(route): held.append(route)
def release():
    for r in held:
        a = urlsplit(r.request.url).path.rsplit("/", 1)[-1].split(";")[0].split(",")
        d = 1500 if abs(float(a[1]) - X["coordinate"]["x"]) < 1e-4 else 150     # from Stop X: a long way round
        r.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                  body=json.dumps({"code": "Ok", "routes": [{"distance": d, "duration": d, "geometry": {"type": "LineString", "coordinates": [[0, 0], [0, 0]]}}]}))
    held.clear()
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    def session(case, base, store, geo=None):
        S.update(case=case, base=base)
        ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich", permissions=["geolocation"],
                            geolocation=geo or {"latitude": 46.30, "longitude": 6.30})
        ctx.route("https://transport.opendata.ch/**", api); ctx.route("https://routing.openstreetmap.de/**", osrm)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.clock.install(time=base.timestamp()); pg.goto(PAGE)
        pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", dict({"tab": "journey", "lang": "fr"}, **store))
        pg.reload()
        return ctx, pg

    # ---- (1) stop times and passed stops
    ctx, pg = session(1, dt.datetime(2026, 11, 13, 16, 20, tzinfo=tz), {"settings": {"footMaxMin": 0, "realWalk": False, "alightReminder": False},
                      "journey:from": STOP(UNIMAIL), "journey:to": STOP(LPR)})
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.locator("#journeyList .jr").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    def dismiss():
        while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    dismiss()
    pg.clock.run_for(int((at(15) - S["base"]).total_seconds() * 1000)); pg.wait_for_timeout(500); dismiss()   # 16:35, on board, after a refresh
    trip = pg.locator("#alarmList .trip").first
    trip.locator(".via-toggle").first.click()
    times = pg.locator("#alarmList .trip .via li time").all_inner_texts()
    assert times == ["16:35", "16:37", "16:39"], times             # planned + 5, not + 10
    passed = pg.locator("#alarmList .trip .via li.passed").count()
    assert passed == 1, passed                                      # Acacias 16:35 passed at 16:35:xx
    pg.clock.run_for(4 * 60000); pg.wait_for_timeout(400); dismiss()   # 16:39
    assert pg.locator("#alarmList .trip .via li.passed").count() == 3
    print("stops       → times planned + delay (16:35 16:37 16:39), greyed as passed")
    ctx.close()
    # by position: at Industrielle at 16:35 while the times say only Acacias is passed (the position is followed
    # for the get-off reminders, on by default)
    ctx, pg = session(1, dt.datetime(2026, 11, 13, 16, 20, tzinfo=tz), {"settings": {"footMaxMin": 0, "realWalk": False},
                      "journey:from": STOP(UNIMAIL), "journey:to": STOP(LPR)})
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.locator("#journeyList .jr").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss()
    pg.clock.run_for(int((at(15) - S["base"]).total_seconds() * 1000)); pg.wait_for_timeout(300); dismiss()
    ctx.set_geolocation({"latitude": INDUS["coordinate"]["x"], "longitude": INDUS["coordinate"]["y"]})
    pg.clock.run_for(6000); pg.wait_for_timeout(1500); pg.clock.run_for(6000); pg.wait_for_timeout(1500); dismiss()
    pg.locator("#alarmList .trip .via-toggle").first.click()
    assert pg.locator("#alarmList .trip .via li.passed").count() == 2, pg.locator("#alarmList .trip .via").inner_html()
    pg.screenshot(path=str(OUT / "stops-passed.png"))
    print("position    → at Industrielle: Acacias and Industrielle greyed")
    ctx.close()

    # ---- (2) the list keeps its order when later work changes times
    ctx, pg = session(2, dt.datetime(2026, 11, 13, 10, 0, tzinfo=tz), {"settings": {"footMaxMin": 0},
                      "journey:from": STOP(UNIMAIL), "journey:to": {"kind": "point", "coord": list(DEST), "near": None}})
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    first = lambda: pg.locator("#journeyList .jr .jr-segs").first.inner_text()
    assert "1" in first() and pg.locator("#journeyList .jr").count() == 2
    pg.locator("#journeyList .jr").first.click()                    # open the bus 1 journey (to Stop X)
    before = pg.locator("#journeyList .jr-top b").first.inner_text()
    release(); pg.wait_for_timeout(800); release(); pg.wait_for_timeout(800)
    after = pg.locator("#journeyList .jr-top b").first.inner_text()
    assert before != after, (before, after)                         # its times changed (long walk from Stop X)…
    assert pg.locator("#journeyList .jr").first.get_attribute("aria-expanded") == "true" and pg.locator("#journeyList .jr-detail").count() == 1
    assert "→ Genève, Stop X" in pg.locator("#journeyList .jr-detail").inner_text()   # …and it stays first, open
    # another priority sorts again: least walking → the bus 3 journey (short walk from Stop Y) first
    pg.click("#prio button[data-prio=walk]"); pg.wait_for_timeout(300)
    assert "3" in first() and "1" not in first().split("›")[0], first()
    print(f"order       → the open journey stays in place while its times change ({before} → {after}); another priority sorts again")
    ctx.close()
    b.close()
print("errors:", errors); assert not errors
print("OK")
