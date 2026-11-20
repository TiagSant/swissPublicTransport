"""BUG-14: the journey followed has the better change place, as shown in the list.

The PO's case (16.11.2026, 11:26): Musée d'ethnographie → Les Esserts. The official data (OJP) gets off bus 2 at
Sainte-Clotilde and walks 4 min to tram 14 at Jonction (quai A). The bus goes on to Jonction (quai C, 35 m from A):
the planner finds it a few seconds after the list is shown, but "Follow" tapped meanwhile followed the API's journey,
and nothing improved it afterwards.
(1) "Follow" waits for the check, then follows the journey with the change at Jonction.
(2) A journey followed without the check (data unavailable then) gets it on the way, once the data is there.
transport.opendata.ch is mocked; stop ids, positions and quays are the real ones (assets/quays.js)."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
MUSEE = st("8592868", "Genève, Musée d'ethnographie", 46.19795, 6.13641)
CLOTILDE = st("8592908", "Genève, Sainte-Clotilde", 46.199879, 6.132626)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
CLAIREVUE = st("8592980", "Petit-Lancy, Claire-Vue", 46.1930, 6.1240)
QUIDORT = st("8592905", "Petit-Lancy, Quidort", 46.1915, 6.1205)
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
S = {"base": None, "hold": False, "held": [], "fail": False}
def at(m): return S["base"] + dt.timedelta(minutes=m)
def end(s, t, kind, plat): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, mid=()):
    calls = [{"station": a, "departure": fmt(t0)}] + [{"station": s, "arrival": fmt(t), "departure": fmt(t)} for s, t in mid] + [{"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, t0, "departure", p0), "arrival": end(b, t1, "arrival", p1)}
def walk(a, b, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(b, t1, "arrival", "")}
def connections():   # bus 2 11:27 → Sainte-Clotilde 11:29, walk 4 min, tram 14 Jonction 11:35 (quai A) → Les Esserts 11:41
    return [{"sections": [ride("B", "2", "Bernex, Cressy", MUSEE, CLOTILDE, at(12), at(14), "J", "G"),
                          walk(CLOTILDE, JONCTION, at(14), at(18)),
                          ride("T", "14", "Bernex-Vailly", JONCTION, ESSERTS, at(20), at(26), "A", "B", mid=[(QUIDORT, at(23))])]}]
def entry(cat, num, to, here, t0, nxt, plat):
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "prognosis": {}, "platform": plat, "delay": 0},
            "passList": [{"station": here}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": {}} for s, t in nxt]}
def board(stop_id):
    if stop_id == MUSEE["id"]: return [entry("B", "2", "Bernex, Cressy", MUSEE, at(12), [(CLOTILDE, at(14)), (JONCTION, at(16)), (CLAIREVUE, at(19))], "J")]
    if stop_id == CLOTILDE["id"]: return [entry("B", "2", "Bernex, Cressy", CLOTILDE, at(14), [(JONCTION, at(16)), (CLAIREVUE, at(19))], "G")]
    if stop_id == JONCTION["id"]: return [entry("B", "2", "Bernex, Cressy", JONCTION, at(16), [(CLAIREVUE, at(19))], "C"),
                                          entry("T", "14", "Bernex-Vailly", JONCTION, at(20), [(QUIDORT, at(23)), (ESSERTS, at(26))], "A")]
    return []
def answer(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": connections()}
    elif u.path.endswith("/stationboard"): body = {"station": {"id": q["id"][0]}, "stationboard": board(q["id"][0])}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
def api(route):
    if "/stationboard" in route.request.url:
        if S["fail"]: return route.fulfill(status=503, body="", headers={"Access-Control-Allow-Origin": "*"})
        if S["hold"]: return S["held"].append(route)
    answer(route)
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
norm = lambda s: " ".join(s.split())

errors = []
def session(b):
    S["base"] = dt.datetime(2026, 11, 16, 11, 15, tzinfo=tz)
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=S["base"].timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "alightReminder": False},
             "journey:from": STOP(MUSEE), "journey:to": STOP(ESSERTS)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    return ctx, pg
plan = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
def dismiss(pg):
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    # 1. "Follow" tapped before the change was checked: it waits, then follows the change at Jonction
    S.update(hold=True, held=[], fail=False)
    ctx, pg = session(b)
    pg.locator("#journeyList .jr").first.click()
    pg.click("#journeyList .jr-detail .set-alarms")
    pg.wait_for_timeout(300)
    assert pg.locator("#journeyList .set-alarms[disabled]").count() == 1 and not pg.is_visible("#alarmList .trip"), "should wait"
    S["hold"] = False
    for _ in range(100):
        while S["held"]: answer(S["held"].pop(0))
        if pg.is_visible("#alarmList .trip"): break
        pg.wait_for_timeout(100)
    pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    pl = plan(pg)
    r0 = pl[0]
    assert r0["toStop"]["name"] == "Genève, Jonction", (r0["toStop"], pl)
    walks = [l for l in pl if l["type"] == "walk"]
    assert len(walks) == 1 and round(walks[0]["min"]) == 1, walks
    trip = norm(pg.locator("#alarmList .trip").first.inner_text())
    assert "Sainte-Clotilde" not in trip.split("Jonction")[-1] and "Marche 4 min" not in trip, trip
    pg.screenshot(path=str(OUT / "follow-best-change.png"))
    ctx.close()
    print("1 follow    → waited for the check: off bus 2 at Jonction (1 min to the tram), not Sainte-Clotilde + 4 min")

    # 2. followed without the check (boards unavailable), improved on the way once they answer
    S.update(hold=False, held=[], fail=True)
    ctx, pg = session(b)
    pg.locator("#journeyList .jr").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)
    assert plan(pg)[0]["toStop"]["name"] == "Genève, Sainte-Clotilde", plan(pg)[0]
    S["fail"] = False
    pg.clock.run_for(65000); pg.wait_for_timeout(1500)
    pl = plan(pg)
    assert pl[0]["toStop"]["name"] == "Genève, Jonction", pl[0]["toStop"]
    al = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].alights")
    assert al[0]["stopId"] == JONCTION["id"], al
    walks = [l for l in pl if l["type"] == "walk"]
    assert len(walks) == 1 and round(walks[0]["min"]) == 1, walks
    # checked once: a later refresh changes nothing
    pg.clock.run_for(65000); pg.wait_for_timeout(800)
    assert plan(pg) == pl
    ctx.close()
    print("2 on the way→ followed as the API gave it, moved to Jonction at the next refresh; get-off reminder moved too")
    b.close()
print("errors:", errors); assert not errors
print("OK")
