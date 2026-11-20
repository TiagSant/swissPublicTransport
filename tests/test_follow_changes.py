"""US-63: the followed journey keeps up with what the rider actually does (the PO's case, 16.11.2026).

Planned: from home, tram 14 09:12 Les Esserts → Jonction 09:19, bus 2 09:22 → Musée d'ethnographie 09:25, walk.
1. At the stop early (alarms silenced), the rider boards the 09:07 tram: once the position is on its line, the
   journey follows the 09:07 (times, stops) and says so.
2. At Jonction at 09:14, the buses just left: "Finish on foot from Genève, Jonction" is offered (no later than the
   plan); taking it ends the journey on foot, the bus 2 is dropped.
3. "Other ways from here": journeys from the position, and on foot all the way."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); DAY = dt.datetime(2026, 11, 16, 9, 0, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: DAY + dt.timedelta(minutes=m)
hm = lambda ms: dt.datetime.fromtimestamp(ms / 1000, tz).strftime("%H:%M")
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
PLACE = st("8587420", "Petit-Lancy, place", 46.190500, 6.118500)
QUID = st("8587421", "Petit-Lancy, Quidort", 46.194500, 6.124000)
JON = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
MUSEE = st("8587063", "Genève, Musée d'ethnographie", 46.198600, 6.135000)
HOME = (46.1868, 6.1125); DEST = (46.198300, 6.135600)
def end(s, m, kind, plat=""): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def call(s, m, first=False, last=False):
    c = {"station": s}
    if not first: c["arrival"] = fmt(at(m))
    if not last: c["departure"] = fmt(at(m))
    return c
def tram(m): return [(ESS, m), (PLACE, m + 2), (QUID, m + 4), (JON, m + 7)]
def ride(cat, num, to, stops, p0, p1):
    pl = [call(s, m, k == 0, k == len(stops) - 1) for k, (s, m) in enumerate(stops)]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl}, "walk": None,
            "departure": end(stops[0][0], stops[0][1], "departure", p0), "arrival": end(stops[-1][0], stops[-1][1], "arrival", p1)}
PLANNED = {"sections": [ride("T", "14", "Meyrin, Gravière", tram(12), "A", "B"),
                        {"journey": None, "walk": {"duration": 60}, "departure": end(JON, 19, "departure"), "arrival": end(JON, 20, "arrival")},
                        ride("B", "2", "Genève-Plage", [(JON, 22), (MUSEE, 25)], "D", "K")]}
def entry(cat, num, to, stops, plat):
    s0, m0 = stops[0]
    return {"stop": {"station": s0, "departure": fmt(at(m0)), "departureTimestamp": int(at(m0).timestamp()), "platform": plat, "prognosis": {}, "delay": 0},
            "category": cat, "number": num, "to": to, "operator": "TPG", "passList": [call(s, m, k == 0) for k, (s, m) in enumerate(stops)]}
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        frm, to = q["from"][0], q["to"][0]
        conns = [] if to != MUSEE["id"] else [PLANNED] if frm == ESS["id"] else [{"sections": [ride("B", "19", "Vernier, village", [(JON, 21), (MUSEE, 24)], "C", "K")]}] if frm == JON["id"] else []
        body = {"connections": conns}
    elif u.path.endswith("/stationboard"):
        sid = q.get("id", [""])[0]
        board = [entry("T", "14", "Meyrin, Gravière", tram(m), "A") for m in (2, 7, 12, 17)] if sid == ESS["id"] else \
                [entry("B", "2", "Genève-Plage", [(JON, 22), (MUSEE, 25)], "D"), entry("B", "19", "Vernier, village", [(JON, 21), (MUSEE, 24)], "C")] if sid == JON["id"] else []
        body = {"station": {"id": sid}, "stationboard": board}
    else:
        x, y = (float(q["x"][0]), float(q["y"][0])) if "x" in q else (0, 0)
        near = [dict(MUSEE, distance=60)] if y > 6.133 else [dict(JON, distance=40)] if x > 46.199 else [dict(ESS, distance=200)]
        body = {"stations": near}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
def dismiss(pg):
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
def be(pg, where, until_m):
    while pg.evaluate("Date.now()") < at(until_m).timestamp() * 1000:
        pg.context.set_geolocation({"latitude": where[0] + (pg.evaluate("Date.now()") % 7) * 1e-7, "longitude": where[1], "accuracy": 8}); pg.wait_for_timeout(150)
        pg.clock.run_for(int(min(15000, at(until_m).timestamp() * 1000 - pg.evaluate("Date.now()")))); dismiss(pg)
trip = lambda pg: " ".join(pg.locator("#alarmList .trip").first.inner_text().split())
plan = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 1300}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": HOME[0], "longitude": HOME[1], "accuracy": 8})
    ctx.route("https://transport.opendata.ch/**", api); ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(0).timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }",
                {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 15, "realWalk": False, "prepMin": 5, "marginMin": 1, "alightReminder": False},
                 "journey:from": {"kind": "stop", "id": ESS["id"], "name": ESS["name"], "coord": [ESS["coordinate"]["x"], ESS["coordinate"]["y"]]},
                 "journey:to": {"kind": "point", "coord": list(DEST), "near": None}})
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(800)
    pg.locator("#journeyList .jr", has_text="09:12").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip"); dismiss(pg)

    # 1. at the stop early, then on the 09:07
    be(pg, (ESS["coordinate"]["x"], ESS["coordinate"]["y"]), 6)        # at the stop from 09:00 (the 09:02 is not theirs: it is the 09:07)
    assert "Vous êtes à Petit-Lancy, Les Esserts" in trip(pg), trip(pg)
    be(pg, (ESS["coordinate"]["x"], ESS["coordinate"]["y"]), 7.3)
    be(pg, (PLACE["coordinate"]["x"] + 0.0003, PLACE["coordinate"]["y"]), 9.5)
    r0 = next(l for l in plan(pg) if l["type"] == "ride")
    assert hm(r0["dep"]) == "09:07" and hm(r0["arr"]) == "09:14", (hm(r0["dep"]), hm(r0["arr"]))
    tx = trip(pg)
    assert "09:07 Petit-Lancy, Les Esserts" in tx and "09:14 Genève, Jonction" in tx, tx
    print("1 earlier   → on the line before 09:12: following the 09:07 (arrival Jonction 09:14)")

    # 2. at Jonction at 09:14:30, waiting: finish on foot offered
    be(pg, (JON["coordinate"]["x"], JON["coordinate"]["y"]), 14.5)
    offer = pg.locator("#alarmList [data-act=foot-offer]")
    assert offer.count() == 1, trip(pg)
    otext = " ".join(offer.inner_text().split())
    assert "Finir à pied depuis Genève, Jonction" in otext and "arrivée 09:2" in otext, otext
    pg.screenshot(path=str(OUT / "follow-foot-offer.png"))

    # 3. other ways from here
    pg.click("#alarmList [data-act=here]")
    pg.wait_for_function("""() => [...document.querySelectorAll('#alarmList .early .trip-alt')]
        .some(e => e.innerText.includes('jusqu’au bout'))""", timeout=10000)   # the answer, not the foot offer already shown
    ways = [" ".join(x.split()) for x in pg.locator("#alarmList .early .trip-alt").all_inner_texts()]
    assert any("À pied jusqu’au bout" in w for w in ways) and any("Bus 19 à 09:21" in w for w in ways), ways
    print("3 from here → ", ways)

    offer.click(); pg.wait_for_timeout(400)
    pl = plan(pg)
    assert [l["type"] for l in pl][-1] == "walk" and sum(l["type"] == "ride" for l in pl) == 1, [l["type"] for l in pl]
    assert "Bus 2" not in trip(pg) and "Genève-Plage" not in trip(pg), trip(pg)
    print("2 on foot   → “", otext, "” taken: the bus 2 dropped, the journey ends on foot")
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
