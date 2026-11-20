"""US-61: a cancelled vehicle — not suggested when planning, replaced in one tap when following.

The PO's case (16.11.2026): tram 14 to Meyrin at 07:43 from Petit-Lancy, Les Esserts disappeared from the live
departures (07:39, then 07:47) while the journey search still offered it for a few minutes.
Planning (07:26): the 07:43 is left out; the 07:47 and the bus 22 are shown.
Following (planned the evening before with the 07:43): once it is gone from the departures, the journey says so and
offers what replaces it — not the 07:43, still listed by the journey search — and the alarms move with the choice."""
import os, re, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototype/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); DAY = dt.datetime(2026, 11, 16, 7, 0, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: DAY + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
JON = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
def end(s, m, kind, plat=""): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, m0, m1, plat):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG",
                        "passList": [{"station": ESS, "departure": fmt(at(m0))}, {"station": JON, "arrival": fmt(at(m1))}]},
            "walk": None, "departure": end(ESS, m0, "departure", plat), "arrival": end(JON, m1, "arrival")}
T1443 = ride("T", "14", "Meyrin, Gravière", 43, 50, "A"); T1447 = ride("T", "14", "Meyrin, Gravière", 47, 54, "A"); B22 = ride("B", "22", "Genève, Jardin Botanique", 40, 52, "C")
def entry(cat, num, to, m, plat, nxt):
    return {"stop": {"station": ESS, "departure": fmt(at(m)), "departureTimestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {"departure": fmt(at(m))}, "delay": 0},
            "category": cat, "number": num, "to": to, "operator": "TPG",
            "passList": [{"station": ESS, "departure": fmt(at(m))}] + ([{"station": JON, "arrival": fmt(at(m + 7))}] if nxt else [{"station": st("8587000", "Onex", 46.18, 6.10), "arrival": fmt(at(m + 4))}])}
S = {"gone": False}
def board():
    runs = [entry("T", "14", "Meyrin, Gravière", m, "A", True) for m in (33, 39, 43, 47, 52, 57, 62, 67)]
    runs += [entry("T", "14", "Bernex, Vailly", m, "B", False) for m in (31, 37, 45, 51, 58, 66)] + [entry("B", "22", "Genève, Jardin Botanique", 40, "C", True)]
    if S["gone"]: runs = [r for r in runs if not (r["number"] == "14" and r["stop"]["departure"] == fmt(at(43)) and "Meyrin" in r["to"])]
    return sorted(runs, key=lambda r: r["stop"]["departureTimestamp"])
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        body = {"connections": [{"sections": [c]} for c in (B22, T1443, T1447)]}      # the search still lists the 07:43
    elif u.path.endswith("/stationboard"):
        body = {"station": ESS, "stationboard": board() if q.get("id", [""])[0] == ESS["id"] else []}
    else:
        body = {"stations": [ESS]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
errors = []
def page(b, minute):
    ctx = b.new_context(viewport={"width": 390, "height": 1100}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api); ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=at(minute).timestamp()); pg.goto(PAGE)
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }",
                {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(ESS), "journey:to": STOP(JON)})
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(1500)
    return ctx, pg
tops = lambda pg: [" ".join(x.split()) for x in pg.locator("#journeyList .jr .jr-top b").all_inner_texts()]

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    # ---- planning, the 07:43 already gone from the departures
    S["gone"] = True
    ctx, pg = page(b, 26)
    shown = tops(pg)
    assert "07:43 → 07:50" not in shown and "07:47 → 07:54" in shown and "07:40 → 07:52" in shown, shown
    ctx.close(); print("planning    → the 07:43 (gone from the live departures) is not suggested:", shown)

    # ---- following: planned with the 07:43 while it was there, then it disappears
    S["gone"] = False
    ctx, pg = page(b, 26)
    pg.locator("#journeyList .jr", has_text="07:43 → 07:50").first.click()
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    S["gone"] = True
    pg.clock.run_for(70000); pg.wait_for_timeout(1500)
    while pg.is_visible("#alarmBanner"):
        title = pg.inner_text("#abTitle"); pg.click("#abOk")
    trip = " ".join(pg.locator("#alarmList .trip").first.inner_text().split())
    assert "Tram 14 de 07:43 : supprimé ?" in trip and "Il n’apparaît plus dans les départs en direct de Petit-Lancy, Les Esserts." in trip, trip
    opts = [" ".join(x.split()) for x in pg.locator("#alarmList .trip-warn .trip-alt").all_inner_texts()]
    assert opts and not any("07:43" in o for o in opts), opts                         # the 07:43 is not offered back
    assert any("Tram 14 à 07:47" in o and "(4 min plus tard)" in o for o in opts) and any("Bus 22 à 07:40" in o for o in opts), opts
    pg.screenshot(path=str(OUT / "cancelled-follow.png"))
    print("following   → “Tram 14 de 07:43 : supprimé ?” with:", opts)
    pg.locator("#alarmList .trip-alt", has_text="Tram 14 à 07:47").click(); pg.wait_for_timeout(500)
    a = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
    r0 = next(l for l in a["plan"] if l["type"] == "ride")
    assert dt.datetime.fromtimestamp(r0["dep"] / 1000, tz).strftime("%H:%M") == "07:47" and not r0.get("missing"), r0
    assert dt.datetime.fromtimestamp(a["first"]["sched"] / 1000, tz).strftime("%H:%M") == "07:47", a["first"]
    trip = " ".join(pg.locator("#alarmList .trip").first.inner_text().split())
    assert "supprimé ?" not in trip and "07:47" in trip, trip
    ctx.close(); print("chosen      → the followed journey takes the 07:47; its alarms follow it")
    b.close()
print("errors:", errors); assert not errors
print("OK")
