"""US-44 (leaving early, by position), US-45 (a stopover of a chosen length), US-46 (a round trip).

transport.opendata.ch is mocked; the clock starts at 07:30.
- Part 1 Genève, Plainpalais → Genève, Bel-Air: bus 1 at 07:35, 07:40, 07:50 (5 min ride).
- Part 2 Genève, Bel-Air → Genève, gare Cornavin: bus 3 at 08:10, 08:20, 08:30, 08:40 (6 min ride).
- Back Genève, Bel-Air → Genève, Plainpalais (round trip): bus 1 at 08:50, 09:00, 09:10."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 13, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAIN = st("8587391", "Genève, Plainpalais", 46.198300, 6.141600)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
HOME = (46.1960, 6.1380)   # about 360 m from Plainpalais
LIVE = {"delay1": 0}

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def conn(cat, num, to, a, b, m0, m1):
    calls = [{"station": a, "departure": fmt(at(m0))}, {"station": b, "arrival": fmt(at(m1))}]
    return {"sections": [{"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
                          "departure": end(a, m0, "departure", "A"), "arrival": end(b, m1, "arrival", "B")}]}
ROUTES = {
    (PLAIN["id"], BELAIR["id"]): [conn("B", "1", "Genève, Bel-Air", PLAIN, BELAIR, m, m + 5) for m in (5, 10, 20)],
    (BELAIR["id"], CORN["id"]): [conn("B", "3", "Genève, gare Cornavin", BELAIR, CORN, m, m + 6) for m in (40, 50, 60, 70)],
    (BELAIR["id"], PLAIN["id"]): [conn("B", "1", "Genève, Plainpalais", BELAIR, PLAIN, m, m + 5) for m in (80, 90, 100)],
}
def board(stop_id):
    if stop_id != PLAIN["id"]: return []
    out = []
    for m in (5, 10, 20):
        d = LIVE["delay1"] if m == 10 else 0
        t0 = at(m)
        out.append({"category": "B", "number": "1", "to": "Genève, Bel-Air", "operator": "TPG",
                    "stop": {"station": PLAIN, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()),
                             "prognosis": {"departure": fmt(t0 + dt.timedelta(minutes=d)), "platform": "A"}, "platform": "A", "delay": d},
                    "passList": [{"station": PLAIN}, {"station": BELAIR, "arrival": fmt(at(m + 5)), "prognosis": {"arrival": fmt(at(m + 5 + d))}}]})
    return out
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": ROUTES.get((q["from"][0], q["to"][0]), [])}
    elif u.path.endswith("/locations"): body = {"stations": [dict(PLAIN, distance=360)]}
    else: body = {"station": {"id": q["id"][0]}, "stationboard": board(q["id"][0])}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
def session(b, store, geo=None):
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation=geo or {"latitude": HOME[0], "longitude": HOME[1]})
    ctx.route("https://transport.opendata.ch/**", api)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload()
    return ctx, pg
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
BASE = {"tab": "journey", "settings": {"footMaxMin": 0, "prepMin": 10, "marginMin": 1, "alightReminder": False}, "journey:from": STOP(PLAIN), "journey:to": STOP(CORN)}
def dismiss(pg):
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
def refresh(pg, ms=61000):
    pg.clock.run_for(ms); pg.wait_for_timeout(400); dismiss(pg)
trip = lambda pg: pg.locator("#alarmList .trip").first
plan = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # ---- Stop search: all of Switzerland, no checkbox
    ctx, pg = session(b, {"tab": "departures"})
    assert pg.locator("#allCH").count() == 0
    ctx.close()
    print("search      → no 'all of Switzerland' checkbox")

    # ---- US-45: a 30-min stopover at Bel-Air on the way to Cornavin
    ctx, pg = session(b, BASE)
    assert pg.is_hidden("#viaBox") and pg.is_visible("#addVia")
    pg.click("#addVia"); assert pg.is_visible("#viaBox")
    pg.click("#searchJourney"); assert "Choose the stopover" in pg.inner_text("#journeyStatus")
    pg.evaluate("""p => { localStorage.setItem('tpp:journey:via', JSON.stringify(p)); }""", STOP(BELAIR))
    pg.reload(); assert pg.is_visible("#viaBox") and pg.input_value("#viaQ") == "Genève, Bel-Air"
    pg.fill("#viaStay", "30"); pg.dispatch_event("#viaStay", "change")
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    jr = pg.locator("#journeyList .jr").first
    top = jr.locator(".jr-top b").inner_text()
    assert top == "07:35 → 08:16", top          # bus 1 07:35 → 07:40, 30 min there → bus 3 08:10 → 08:16
    assert "⏸ 30′" in jr.locator(".jr-segs").inner_text(), jr.locator(".jr-segs").inner_text()
    assert jr.locator(".jr-meta").inner_text().startswith("Stopover · no walking"), jr.locator(".jr-meta").inner_text()
    tops = pg.locator("#journeyList .jr .jr-top b").all_inner_texts()
    assert tops[:3] == ["07:35 → 08:16", "07:40 → 08:26", "07:50 → 08:36"], tops   # each first part with the bus it can catch
    jr.click()
    det = pg.locator("#journeyList .jr-detail").first
    stay = det.locator(".leg.stay")
    assert stay.count() == 1 and "Stopover at Genève, Bel-Air · 30 min" in stay.inner_text() and "Arrive 07:40 · leave 08:10" in stay.inner_text(), stay.inner_text()
    assert "Genève, Plainpalais → Genève, Bel-Air → Genève, gare Cornavin" in det.inner_text()
    pg.screenshot(path=str(OUT / "trip-stopover-plan.png"))
    print("stopover    → 07:35 → 08:16 with ⏸ 30′ at Bel-Air; each first part paired with the bus it can catch")

    # follow it: the stay is in the trip, the alternatives stay within their part
    pg.click("#journeyList .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    tr = trip(pg)
    assert tr.locator(".tl.stay").count() == 1 and "Stopover at Genève, Bel-Air · 30 min" in tr.locator(".tl.stay").inner_text()
    assert tr.locator(".warn, .trip-warn").count() == 0, tr.inner_text()            # 30 min at Bel-Air is not a tight change
    # leaving now → options for part 2 from now
    tr.locator("[data-act=stay-now]").click()
    pg.wait_for_selector("#alarmList .tl.stay .trip-alt")
    opts = pg.locator("#alarmList .tl.stay .trip-alt").all_inner_texts()
    assert opts and opts[0].startswith("Bus 3 at 08:10"), opts
    # stay 15 min longer → from 08:25
    trip(pg).locator("[data-act=stay-more]").click()
    pg.wait_for_function("[...document.querySelectorAll('#alarmList .tl.stay .trip-alt')].length && document.querySelector('#alarmList .tl.stay .trip-alt').textContent.startsWith('Bus 3 at 08:30')")
    pg.locator("#alarmList .tl.stay .trip-alt").first.click()
    pl = plan(pg); rides = [l for l in pl if l["type"] == "ride"]
    assert [l["type"] for l in pl] == ["ride", "stay", "ride"], [l["type"] for l in pl]
    assert rides[1]["dep"] == int(at(60).timestamp() * 1000) and pl[1]["until"] == int(at(60).timestamp() * 1000), pl
    assert "Arrive 08:36" in trip(pg).inner_text().split("\n")[0], trip(pg).inner_text()   # new arrival
    print("follow      → stay in the trip; 'leaving now' / '+15 min' → part 2 options; bus 3 08:30 chosen")
    # end of the stay rings
    pg.clock.run_for(int((at(60) - NOW).total_seconds() * 1000) - 0); pg.wait_for_timeout(400)
    assert pg.is_visible("#alarmBanner") and "End of your stopover" in pg.inner_text("#alarmBanner"), pg.inner_text("#alarmBanner")
    assert "Bus 3 at 08:30 from Genève, Bel-Air" in pg.inner_text("#alarmBanner")
    pg.screenshot(path=str(OUT / "trip-stopover-end.png"))
    ctx.close()
    print("stay end    → 'End of your stopover: leave now for Bus 3 at 08:30'")

    # ---- a delay shortens the stay by 5 min or more → part 2 a little later, keeping the 30 min
    s2 = dict(BASE, **{"journey:via": STOP(BELAIR), "journey:viaOn": True, "journey:viaStay": 30})
    ctx, pg = session(b, s2)
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").nth(1).click()           # bus 1 07:40 → 07:45, bus 3 08:20
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    LIVE["delay1"] = 9
    refresh(pg)
    pg.wait_for_selector("#alarmList .tl.stay .trip-alt")
    txt = trip(pg).locator(".tl.stay").inner_text()
    assert "Your stopover is shorter (26 min instead of 30)" in txt and "Bus 3 at 08:30" in txt, txt
    LIVE["delay1"] = 0
    ctx.close()
    print("delay       → stay 26 min instead of 30: later part 2 offered (bus 3 08:30)")

    # ---- position: leaving the stopover early
    ctx, pg = session(b, s2, geo={"latitude": 46.2047, "longitude": 6.1431})
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.click("#journeyList .jr >> nth=0"); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    pg.clock.run_for(int((at(11) - NOW).total_seconds() * 1000)); dismiss(pg)   # 07:41: at Bel-Air
    pg.wait_for_timeout(1500); pg.clock.run_for(6000); pg.wait_for_timeout(1500)
    assert pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].staySeen"), "not seen at the stay"
    ctx.set_geolocation({"latitude": 46.2095, "longitude": 6.1420})                # 550 m away, 08:10 - 25 min
    pg.clock.run_for(6000); pg.wait_for_timeout(2000)
    pg.wait_for_selector("#alarmList .tl.stay .trip-alt", timeout=10000)
    assert "You left Genève, Bel-Air early" in trip(pg).locator(".tl.stay").inner_text(), trip(pg).locator(".tl.stay").inner_text()
    ctx.close()
    print("position    → left the stopover early: earlier part 2 offered")

    # ---- US-46: round trip, 60 min there
    s3 = dict(BASE, **{"journey:to": STOP(BELAIR), "journey:roundTrip": True, "journey:returnStay": 60})
    ctx, pg = session(b, s3)
    assert pg.is_checked("#roundTrip") and pg.is_visible("#returnStayBox") and pg.input_value("#returnStay") == "60"
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    jr = pg.locator("#journeyList .jr").first
    assert jr.locator(".jr-top b").inner_text() == "07:35 → 08:55", jr.locator(".jr-top b").inner_text()   # back on the 08:50
    assert "⇄ 60′" in jr.locator(".jr-segs").inner_text()
    assert jr.locator(".jr-meta").inner_text().startswith("Round trip"), jr.locator(".jr-meta").inner_text()
    jr.click()
    det = pg.locator("#journeyList .jr-detail").first
    assert "Time at Genève, Bel-Air · 60 min, then back" in det.locator(".leg.stay").inner_text()
    assert "Genève, Plainpalais → Genève, Bel-Air → Genève, Plainpalais" in det.inner_text()
    pg.screenshot(path=str(OUT / "trip-round.png"))
    # several followed journeys one after the other: both kept, in time order
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    pg.evaluate("localStorage.setItem('tpp:journey:roundTrip', 'false')"); pg.reload()
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").nth(2).click(); pg.click("#journeyList .jr-detail .set-alarms"); dismiss(pg)
    assert pg.locator("#alarmList .alarm").count() == 2
    deps = pg.locator("#alarmList .alarm b[data-k=dep]").all_inner_texts()
    assert deps == sorted(deps), deps
    ctx.close()
    print("round trip  → 07:35 → 08:55, ⇄ 60′ at Bel-Air; two followed journeys kept in time order")

    # ---- US-44: leaving home early, then at the stop early → alarms cancelled, earlier bus offered
    s4 = dict(BASE, **{"journey:from": {"kind": "point", "coord": list(HOME), "near": None}, "journey:to": STOP(BELAIR)})
    ctx, pg = session(b, s4)
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    js = pg.locator("#journeyList .jr .jr-top b").all_inner_texts()
    k = next(i for i, x in enumerate(js) if x.startswith("07:4") and "07:55" in x)   # leave ~07:4x for the bus at 07:50
    pg.locator("#journeyList .jr").nth(k).click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    assert pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].fired.ready") is None
    pg.clock.run_for(60000); pg.wait_for_timeout(300); dismiss(pg)                       # 07:31
    ctx.set_geolocation({"latitude": 46.1983, "longitude": 6.1416})                     # at Plainpalais
    pg.clock.run_for(6000); pg.wait_for_timeout(2000)
    a = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
    assert a.get("early") and a["early"].get("silenced") and a["fired"].get("ready") and a["fired"].get("leave"), a.get("early")
    assert "You left early" in trip(pg).inner_text() and "You are at Genève, Plainpalais" in trip(pg).inner_text(), trip(pg).inner_text()
    refresh(pg)
    pg.wait_for_selector("#alarmList .early .trip-alt", timeout=10000)
    opt = pg.locator("#alarmList .early .trip-alt").first.inner_text()
    assert opt.startswith("Bus 1 at 07:35") and "arrive 07:40" in opt, opt
    pg.screenshot(path=str(OUT / "trip-early.png"))
    pg.locator("#alarmList .early .trip-alt").first.click()
    r = [l for l in plan(pg) if l["type"] == "ride"][0]
    assert r["dep"] == int(at(5).timestamp() * 1000), r
    a = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
    assert a["first"]["sched"] == int(at(5).timestamp() * 1000) and a["fired"].get("ready") and a["fired"].get("leave")
    pg.clock.run_for(60000); pg.wait_for_timeout(300)
    assert not (pg.is_visible("#alarmBanner") and pg.get_attribute("#alarmBanner", "data-kind") in ("ready", "leave")), pg.inner_text("#alarmBanner")
    ctx.close()
    print("early       → at the stop early: Get ready / Leave cancelled, bus 1 07:35 offered and taken, no ring")
    b.close()

print("errors:", errors); assert not errors
print("OK")
