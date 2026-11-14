"""US-57: a journey whose change is missed at the current times is not suggested.

The PO's case (14.11.2026): bus 1 delayed by 8 min reaches the change after the train has left ("Correspondance :
manquée aux horaires actuels"); that journey must not be offered.
A: bus 1 +8 min → Bel-Air 07:48 live, bus 3 leaves 07:46: missed → hidden. B: the next one, fine → shown.
All missed: the app looks once more from just after them and shows what it finds; if still nothing, it says so."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); NOW = dt.datetime(2026, 11, 16, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: NOW + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAIN = st("8587391", "Genève, Plainpalais", 46.1983, 6.1416)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
def end(s, m, kind, plat, late=0):
    e = {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": late or None}
    if late: e["prognosis"] = {kind: fmt(at(m + late))}
    return e
def ride(num, to, a, b, m0, m1, p0, p1, late=0):
    calls = [{"station": a, "departure": fmt(at(m0))}, {"station": b, "arrival": fmt(at(m1))}]
    return {"journey": {"category": "B", "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, m0, "departure", p0, late), "arrival": end(b, m1, "arrival", p1, late)}
def walk(a, m0, m1): return {"journey": None, "walk": {"duration": (m1 - m0) * 60}, "departure": end(a, m0, "departure", ""), "arrival": end(a, m1, "arrival", "")}
def journey(m, late): return {"sections": [ride("1", "Genève, Bel-Air", PLAIN, BELAIR, m, m + 5, "A", "B", late), walk(BELAIR, m + 5, m + 7),
                                           ride("3", "Genève, gare Cornavin", BELAIR, CORN, m + 11, m + 17, "D", "H")]}
S = {"case": "one", "asked": []}
def api(route):
    u = urlparse(route.request.url)
    if u.path.endswith("/connections"):
        q = parse_qs(u.query); S["asked"].append(q.get("time", [""])[0])
        late_search = q.get("time", [""])[0] > "07:31"
        if S["case"] == "one":
            conns = [journey(5, 8), journey(20, 0)]                      # A missed (+8), B fine
        elif S["case"] == "retry":
            conns = [journey(36, 0)] if late_search else [journey(5, 8), journey(10, 8)]
        else:
            conns = [journey(5, 8)]                                      # always missed
        body = {"connections": conns}
    else:
        body = {"stations": [CORN]} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
errors = []
def session(b, case):
    S["case"] = case; S["asked"] = []
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    pg.evaluate("""s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }""",
                {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False}, "journey:from": STOP(PLAIN), "journey:to": STOP(CORN)})
    pg.reload(); pg.click("#searchJourney")
    pg.wait_for_function("document.querySelector('#journeyList .jr') || document.getElementById('journeyStatus').textContent.length > 20", timeout=10000)
    pg.wait_for_timeout(800)
    return ctx, pg
tops = lambda pg: [x.strip() for x in pg.locator("#journeyList .jr .jr-top b").all_inner_texts()] if pg.is_visible("#journeyResults") else []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx, pg = session(b, "one")
    assert tops(pg) == ["07:50 → 08:07"], tops(pg)                                     # only B (A: 07:35 +8, missed, missed)
    assert "manquée" not in pg.inner_text("#journeyList")
    ctx.close(); print("one missed  → hidden; the other journey shown")

    ctx, pg = session(b, "retry")
    assert tops(pg) == ["08:06 → 08:23"], (tops(pg), S["asked"])                        # found by the second search
    assert len(S["asked"]) >= 2 and max(S["asked"]) > "07:31", S["asked"]
    ctx.close(); print("all missed  → searched again from just after them; the journey found is shown")

    ctx, pg = session(b, "none")
    msg = pg.inner_text("#journeyStatus")
    assert pg.is_hidden("#journeyResults") and "correspondances des itinéraires trouvés sont manquées" in msg, msg
    pg.screenshot(path=str(OUT / "hide-missed.png"))
    ctx.close(); print("still none  → “Avec les retards actuels, les correspondances … sont manquées. Essayez un départ plus tard.”")
    b.close()
print("errors:", errors); assert not errors
print("OK")
