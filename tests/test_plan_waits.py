"""US-47: walking and waiting at each change are shown when planning, before a journey is chosen.

Two journeys (asked at 07:30), Plainpalais → Cornavin, changing at Bel-Air:
- A: bus 1 07:35 → Bel-Air 07:40 (platform B), walk 2 min, bus 3 07:48 from platform D: 2 min walk, then 6 min wait.
- B: bus 1 07:45 → Bel-Air 07:50 (platform B), bus 3 07:51 from platform B: same platform, 1 min wait (tight)."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); NOW = dt.datetime(2026, 11, 13, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: NOW + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
PLAIN = st("8587391", "Genève, Plainpalais", 46.1983, 6.1416)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
CORN = st("8587057", "Genève, gare Cornavin", 46.209652, 6.14233)
def end(s, m, kind, plat): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(num, to, a, b, m0, m1, p0, p1):
    calls = [{"station": a, "departure": fmt(at(m0))}, {"station": b, "arrival": fmt(at(m1))}]
    return {"journey": {"category": "B", "number": num, "to": to, "operator": "TPG", "passList": calls}, "walk": None,
            "departure": end(a, m0, "departure", p0), "arrival": end(b, m1, "arrival", p1)}
def walk(a, m0, m1): return {"journey": None, "walk": {"duration": (m1 - m0) * 60}, "departure": end(a, m0, "departure", ""), "arrival": end(a, m1, "arrival", "")}
CONNS = [
    {"sections": [ride("1", "Genève, Bel-Air", PLAIN, BELAIR, 5, 10, "A", "B"), walk(BELAIR, 10, 12), ride("3", "Genève, gare Cornavin", BELAIR, CORN, 18, 24, "D", "H")]},
    {"sections": [ride("1", "Genève, Bel-Air", PLAIN, BELAIR, 15, 20, "A", "B"), walk(BELAIR, 20, 21), ride("3", "Genève, gare Cornavin", BELAIR, CORN, 21, 27, "B", "H")]},
]
def api(route):
    u = urlparse(route.request.url)
    body = {"connections": CONNS} if u.path.endswith("/connections") else {"stations": [CORN]} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    for lang, words in (("en-US", ("6 min waiting", "Change: 2 min walk, then 6 min wait", "1 min waiting", "Same platform, no walking · 1 min wait")),
                        ("fr-CH", ("6 min d’attente", "Correspondance : 2 min de marche, puis 6 min d’attente", "1 min d’attente", "Même quai, pas de marche · 1 min d’attente"))):
        ctx = b.new_context(viewport={"width": 390, "height": 900}, locale=lang, timezone_id="Europe/Zurich")
        ctx.route("https://transport.opendata.ch/**", api)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
        pg.evaluate("""s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }""",
                    {"tab": "journey", "lang": lang[:2], "settings": {"footMaxMin": 0}, "journey:from": STOP(PLAIN), "journey:to": STOP(CORN)})
        pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
        jr = pg.locator("#journeyList .jr")
        m0, m1 = jr.nth(0).locator(".jr-meta").inner_text(), jr.nth(1).locator(".jr-meta").inner_text()
        assert words[0] in m0 and jr.nth(0).locator(".wait-total.changed").count() == 0, m0
        assert words[2] in m1 and jr.nth(1).locator(".wait-total.changed").count() == 1, m1     # tight: in orange
        jr.nth(0).click()
        w = pg.locator("#journeyList .jr-detail .leg.ride .wait")
        assert w.count() == 1 and w.inner_text() == "⏱ " + words[1], w.all_inner_texts()
        assert w.evaluate("e => e.closest('.leg.ride').querySelector('.leg-to').textContent").endswith("Cornavin")   # on the bus taken after the change
        pg.screenshot(path=str(OUT / f"plan-waits-{lang[:2]}.png"))
        jr.nth(0).click(); jr.nth(1).click()
        det = pg.locator("#journeyList .jr-detail").first
        assert words[3] in det.locator(".leg.change").inner_text(), det.locator(".leg.change").inner_text()
        tight = det.locator(".leg.ride .wait.changed")
        assert tight.count() == 1 and "1" in tight.inner_text(), det.inner_text()      # tight: said on the bus too
        print(f"{lang[:2]}          → summary '{words[0]}' / '{words[2]}' (tight, orange); detail '{words[1]}'")
        ctx.close()
    b.close()
print("errors:", errors); assert not errors
print("OK")
