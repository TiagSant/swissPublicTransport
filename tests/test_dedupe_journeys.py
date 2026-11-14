"""US-58: journeys the rider would see as the same are shown once — same route, times and walks, and the same
alternative offered (bus or on foot). Seen by the PO (15.11.2026): two identical "Départ à pied" cards.

Learned "finish on foot" from Plainpalais (3 times): every journey changing at Plainpalais ends on foot there.
A: bus 21 → Plainpalais, tram 12 07:58 → Bel-Air 08:03.   A': the same with tram 12 08:00 → 08:03.
B: the same with tram 15 07:59 → 08:03.
On foot, A, A' and B are the same route. A and A' also offer the same alternative ("take the Tram 12 instead",
arriving 08:03 at Bel-Air): one card. B offers the Tram 15: kept. Without the walk learned, the three differ: three cards."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); NOW = dt.datetime(2026, 11, 16, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: NOW + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
COMMUNES = st("8592887", "Lancy, Communes-Réunies", 46.174500, 6.121900)
PLAIN = st("8587391", "Genève, Plainpalais", 46.198300, 6.141600)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
DEST = (46.2047, 6.1470)
def end(s, m, kind): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": "", "prognosis": {}, "delay": None}
def ride(cat, num, a, b, ma, mb): return {"journey": {"category": cat, "number": num, "to": b["name"], "operator": "TPG",
    "passList": [{"station": a, "departure": fmt(at(ma))}, {"station": b, "arrival": fmt(at(mb))}]}, "walk": None,
    "departure": end(a, ma, "departure"), "arrival": end(b, mb, "arrival")}
def conn(cat, num, m0): return {"sections": [ride("B", "21", COMMUNES, PLAIN, 10, 22), ride(cat, num, PLAIN, BELAIR, m0, 33)]}
CONNS = [conn("T", "12", 28), conn("T", "12", 30), conn("T", "15", 29)]
def api(route):
    u = urlparse(route.request.url)
    body = {"connections": CONNS} if u.path.endswith("/connections") else {"stations": [dict(BELAIR, distance=300)]} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
def cards(b, learned):
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    key = f"{PLAIN['id']}>{DEST[0]:.3f},{DEST[1]:.3f}"
    store = {"tab": "journey", "lang": "en", "settings": {"realWalk": False},
             "journey:from": {"kind": "stop", "id": COMMUNES["id"], "name": COMMUNES["name"], "coord": [46.1745, 6.1219]},
             "journey:to": {"kind": "point", "coord": list(DEST), "near": None}}
    if learned: store["foot"] = {key: {"foot": 3, "bus": 0, "shown": 0, "t": 0}}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(1500)
    items = pg.locator("#journeyList .jr-item")
    out = []
    for k in range(items.count()):
        items.nth(k).locator(".jr").click()
        alt = items.nth(k).locator(".foot-toggle").all_inner_texts()
        out.append((" ".join(items.nth(k).locator(".jr-top b").inner_text().split()), " ".join(" ".join(alt).split())))
        items.nth(k).locator(".jr").click()
    pg.screenshot(path=str(OUT / f"dedupe-{'foot' if learned else 'bus'}.png"))
    ctx.close()
    return out

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    shown = cards(b, True)
    assert len(shown) == 2, shown
    assert len({c[0] for c in shown}) == 1, shown                                   # the same route on foot…
    assert any("Tram 12" in c[1] for c in shown) and any("Tram 15" in c[1] for c in shown), shown   # …with different alternatives
    print("on foot     → A and A' (same alternative: Tram 12) shown once; B (Tram 15) kept:", shown)
    shown = cards(b, False)
    assert len(shown) == 3, shown
    print("by tram     → three different journeys, three cards")
    b.close()
print("errors:", errors); assert not errors
print("OK")
