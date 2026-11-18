"""BUG-22: an alternative chosen for a missed change keeps the walk between the two platforms.

The PO (18.11.2026, 09:08): tram 14 late, the change at Jonction missed; he chose bus 2 instead — the followed journey
showed tram 14 to Jonction (quai B) then bus 2 from quai D, with no walk between (only "6 min waiting").
An alternative found from the change stop starts with its vehicle: spliced into the plan, the walk from the platform
where the rider gets off to the one it leaves from is now added, as when planning.
Stop ids / positions / quays real (Les Esserts, Jonction, Musée d'ethnographie). transport.opendata.ch mocked."""
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
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
def at(h, m): return dt.datetime(2026, 11, 18, h, m, tzinfo=tz)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
MUSEE = st("8592868", "Genève, Musée d'ethnographie", 46.19795, 6.13641)
def prog(kind, t, d): return {kind: fmt(t + dt.timedelta(minutes=d))} if d else {}
def end(s, t, kind, plat, d=0): return {"station": s, kind: fmt(t), kind + "Timestamp": int(t.timestamp()), "platform": plat, "prognosis": prog(kind, t, d), "delay": d or None}
def ride(cat, num, to, a, b, t0, t1, p0, p1, d=0):
    pl = [{"station": a, "departure": fmt(t0)}, {"station": b, "arrival": fmt(t1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl}, "walk": None,
            "departure": end(a, t0, "departure", p0, d), "arrival": end(b, t1, "arrival", p1, d)}
def walk(a, b, t0, t1): return {"journey": None, "walk": {"duration": int((t1 - t0).total_seconds())}, "departure": end(a, t0, "departure", ""), "arrival": end(b, t1, "arrival", "")}
S = {"late": 0}
def entry(cat, num, to, here, t0, d, nxt, plat):
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": plat, "prognosis": prog("departure", t0, d), "delay": d},
            "passList": [{"station": here}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": prog("arrival", t, d)} for s, t in nxt]}
def board(stop_id):
    if stop_id == ESSERTS["id"]: return [entry("T", "14", "Meyrin-Gravière", ESSERTS, at(8, 58), S["late"], [(JONCTION, at(9, 5))], "A")]
    if stop_id == JONCTION["id"]: return [entry("B", "19", "Vernier", JONCTION, at(9, 7), 0, [(MUSEE, at(9, 10))], "D"),
                                          entry("B", "2", "Genève-Plage", JONCTION, at(9, 11), 4, [(MUSEE, at(9, 14))], "D"),
                                          entry("B", "19", "Vernier", JONCTION, at(9, 22), 0, [(MUSEE, at(9, 25))], "D")]
    return []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        f = q.get("from", [""])[0]
        if f == ESSERTS["id"]: body = [{"sections": [ride("T", "14", "Meyrin-Gravière", ESSERTS, JONCTION, at(8, 58), at(9, 5), "A", "B"),
                                                     walk(JONCTION, JONCTION, at(9, 5), at(9, 6)), ride("B", "19", "Vernier", JONCTION, MUSEE, at(9, 7), at(9, 10), "D", "K")]}]
        elif f == JONCTION["id"]: body = [{"sections": [ride("B", "2", "Genève-Plage", JONCTION, MUSEE, at(9, 11), at(9, 14), "D", "K", d=4)]}]
        else: body = []
        body = {"connections": body}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": board(q.get("id", [""])[0])}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
norm = lambda s: " ".join(s.split())
errors = []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 1400}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(8, 50).timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False, "motionSensors": False}, "journey:from": STOP(ESSERTS), "journey:to": STOP(MUSEE)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    plan0 = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    assert [l["type"] for l in plan0] == ["ride", "walk", "ride"], [l["type"] for l in plan0]
    # tram 14 4 min late: the change to bus 19 (09:07) is missed
    S["late"] = 4
    for _ in range(8):
        pg.clock.run_for(60000); pg.wait_for_timeout(300)
        while pg.is_visible("#alarmBanner"): pg.click("#abOk")
        if pg.locator("#alarmList [data-act=alt]").count(): break
    alts = [norm(x) for x in pg.locator("#alarmList [data-act=alt]").all_inner_texts()]
    n = next(i for i, x in enumerate(alts) if "Bus 2" in x)
    print("alternatives →", alts)
    pg.locator("#alarmList [data-act=alt]").nth(n).click(); pg.wait_for_timeout(300)
    plan = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")
    kinds = [(l["type"], l.get("label") or (l.get("start") or {}).get("platform", "") + ">" + (l.get("end") or {}).get("platform", "")) for l in plan]
    assert [k for k, _ in kinds] == ["ride", "walk", "ride"] and plan[2]["label"] == "2", kinds
    w = plan[1]
    assert w["start"]["platform"] == "B" and w["end"]["platform"] == "D" and w["min"] >= 1, w
    trip = norm(pg.locator("#alarmList .trip").first.inner_text())
    assert "Marche" in trip.split("Genève, Jonction")[1], trip
    pg.screenshot(path=str(OUT / "alternative-change-walk.png"), full_page=True)
    print("plan after   →", kinds, f"walk {w['min']:.1f} min")
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
