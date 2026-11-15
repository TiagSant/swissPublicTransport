"""US-58: journeys the rider would see as the same are shown once — same route, times and walks, and the same
alternative offered (bus or on foot). Seen by the PO (15.11.2026): two identical "Départ à pied" cards.

Learned "finish on foot" from Plainpalais (3 times): every journey changing at Plainpalais ends on foot there.
A: bus 21 → Plainpalais, tram 12 07:58 → Bel-Air 08:03.   A': the same with tram 12 08:00 → 08:03.
B: the same with tram 15 07:59 → 08:03.
On foot, A, A' and B are the same route. A and A' also offer the same alternative ("take the Tram 12 instead",
arriving 08:03 at Bel-Air): one card. B offers the Tram 15: US-59 (PO, 15.11.2026) puts it in the same card, both
trams offered as the alternative; choosing the Tram 15 shows that journey by tram. Without the walk learned: A and
A' are the same tram 12 (same line, direction and arrival: BUG-13, one journey) and B: two cards."""
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
# Start on foot (the PO's case): from a point near Plainpalais, two buses 21 three minutes apart to the same tram 12
UNIMAIL = st("8592999", "Genève, Uni-Mail", 46.195300, 6.139800)
START = (46.1965, 6.1395)
def conn_start(m0, m1): return {"sections": [ride("B", "21", UNIMAIL, PLAIN, m0, m1), ride("T", "12", PLAIN, BELAIR, 28, 33)]}
# BUG-13 (PO, 15.11.2026): the same bus 21 boarded at Uni-Mail (07:40) or at the stop before, Uni-Mail Nord (07:38):
# each nearby stop's search returns it. One journey, not two (it showed as two buses 2 min apart).
UNINORD = st("8592998", "Genève, Uni-Mail Nord", 46.194200, 6.138900)
def conn_from(stop, m0): return {"sections": [ride("B", "21", stop, PLAIN, m0, 20), ride("T", "12", PLAIN, BELAIR, 28, 33)]}
S = {"start": False, "same": False}
def api(route):
    u = urlparse(route.request.url)
    q = route.request.url
    if S["same"]:
        conns = [conn_from(UNINORD, 8)] if f"from={UNINORD['id']}" in q else [conn_from(UNIMAIL, 10)]
    else:
        conns = [conn_start(10, 20), conn_start(13, 23)] if S["start"] else CONNS
    near = ([dict(UNIMAIL, distance=140), dict(UNINORD, distance=260)] if S["same"] else [dict(UNIMAIL, distance=140)]) \
        if (S["start"] or S["same"]) and "x=46.19" in q else [dict(BELAIR, distance=300)]
    body = {"connections": conns} if u.path.endswith("/connections") else {"stations": near} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
def cards(b, learned):
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    key = f"start:{START[0]:.3f},{START[1]:.3f}>{PLAIN['id']}" if (S["start"] or S["same"]) else f"{PLAIN['id']}>{DEST[0]:.3f},{DEST[1]:.3f}"
    store = {"tab": "journey", "lang": "en", "settings": {"realWalk": False},
             "journey:from": {"kind": "point", "coord": list(START), "near": None} if (S["start"] or S["same"]) else {"kind": "stop", "id": COMMUNES["id"], "name": COMMUNES["name"], "coord": [46.1745, 6.1219]},
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
    if learned and not S["start"] and not S["same"]:   # US-59: choose the Tram 15 → that journey by tram; the walk stays offered with the Tram 12
        items.nth(0).locator(".jr").click()
        items.nth(0).locator(".foot-toggle", has_text="Tram 15").click()
        pg.wait_for_timeout(300)
        segs = [" ".join(x.split()) for x in pg.locator("#journeyList .jr-item .jr-segs").all_inner_texts()]
        out.append(("after", segs))
    ctx.close()
    return out

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    shown = cards(b, True)
    after = shown.pop()[1]
    assert sorted(after) == ["21 › 15 › 🚶5′", "21 › 🚶13′"], after                    # Tram 15 chosen: its card; the walk stays
    assert len(shown) == 1, shown                                                    # US-59: one card for the same walk…
    alts = shown[0][1]
    assert alts.count("Take the Tram") == 2 and "Tram 12" in alts and "Tram 15" in alts, alts   # …each tram offered once
    print("on foot     → A and A' (same alternative) merged; with B: one card, Tram 12 and Tram 15 offered:", shown)
    shown = cards(b, False)
    assert len(shown) == 2, shown                       # BUG-13: A and A' are the same tram 12 (same arrival): one journey
    print("by tram     → A and A' (same tram 12, same arrival) one journey; B: two cards")
    S["start"] = True
    shown = cards(b, True)
    assert len(shown) == 1 and shown[0][1].count("Take the Bus 21 first instead") == 2, shown   # one card, both buses 21
    print("start       → walk to the tram 12: one card, the two buses 21 offered:", shown[0][1])
    S["start"], S["same"] = False, True
    shown = cards(b, True)
    assert len(shown) == 1 and shown[0][1].count("Take the Bus 21 first instead") == 1, shown        # one bus, offered once
    assert "leave 07:38" in shown[0][1] or "leave 07:3" in shown[0][1], shown
    shown = cards(b, False)
    assert len(shown) == 1, shown                                                                   # by bus: one card
    print("same bus    → boarded at either of two nearby stops: one journey, one alternative:", shown[0])
    b.close()
print("errors:", errors); assert not errors
print("OK")
