"""US-36: finish on foot. The last ride is compared with walking from where it would be taken; offered for short
walks only, learned per place, and the bus always stays one tap away. transport.opendata.ch is mocked; the clock
is frozen.

Journey: Lancy, Communes-Réunies → bus 21 → Plainpalais (arr. +22) → tram 12 (+28) → Bel-Air (+33) → walk ~5 min
to a point 300 m from Bel-Air. Walking from Plainpalais instead: ~770 m straight, ~12.5 min → a few minutes sooner."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
COMMUNES = st("8592887", "Lancy, Communes-Réunies", 46.174500, 6.121900)
PLAINPALAIS = st("8587391", "Genève, Plainpalais", 46.198300, 6.141600)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
DEST = (46.2047, 6.1470)                     # ~300 m east of Bel-Air
START = (46.1965, 6.1395)                    # ~250 m from Plainpalais
UNIMAIL = st("8592999", "Genève, Uni-Mail", 46.195300, 6.139800)   # ~140 m from START

FAST_TRAM = {"on": False}     # tram 12 leaving at once: walking becomes slower than the bus
def connection(base, origin=COMMUNES):
    at = lambda m: base + dt.timedelta(minutes=m)
    def end(s, m, kind): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": "", "prognosis": {}, "delay": None}
    def ride(cat, num, a, b, ma, mb): return {"journey": {"category": cat, "number": num, "to": b["name"], "operator": "TPG",
        "passList": [{"station": a, "departure": fmt(at(ma))}, {"station": b, "arrival": fmt(at(mb))}]}, "walk": None,
        "departure": end(a, ma, "departure"), "arrival": end(b, mb, "arrival")}
    return {"sections": [ride("B", "21", origin, PLAINPALAIS, 10, 22), ride("T", "12", PLAINPALAIS, BELAIR, *((23, 26) if FAST_TRAM["on"] else (28, 33)))]}

def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        asked = dt.datetime.strptime(q["date"][0] + " " + q["time"][0], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        body = {"connections": [connection(asked, UNIMAIL if q["from"][0] == UNIMAIL["id"] else COMMUNES)]}
    elif u.path.endswith("/locations"):
        near_start = "x" in q and abs(float(q["x"][0]) - START[0]) < 0.002
        body = {"stations": [dict(UNIMAIL, distance=140)] if near_start else [dict(BELAIR, distance=300)]}
    else:
        body = {"station": BELAIR, "stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="en-US", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate(f"""() => {{
      localStorage.setItem('tpp:journey:from', JSON.stringify({{ kind: 'stop', id: '8592887', name: 'Lancy, Communes-Réunies', coord: [46.1745, 6.1219] }}));
      localStorage.setItem('tpp:journey:to', JSON.stringify({{ kind: 'point', coord: [{DEST[0]}, {DEST[1]}], near: null }}));
      localStorage.setItem('tpp:tab', '"journey"'); }}""")
    pg.reload()
    item = lambda: pg.locator("#journeyList li.jr-item").first
    def search():
        pg.evaluate("document.getElementById('journeyList').innerHTML = ''")
        pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
        if item().locator(".jr-detail").count() == 0: item().locator(".jr").click()
    def legs(): return [("walk" if "walk" in c else "ride") for c in item().locator(".legs > li.leg").evaluate_all("els => els.map(e => e.className)")]

    # Offered under the last ride, green because walking is faster than waiting for the tram
    search()
    assert "🚶 Faster on foot" in item().locator(".jr-meta").first.inner_text()
    offer = item().locator(".foot-toggle")
    text = offer.inner_text()
    import re
    m = re.search(r"arrive (\d\d:\d\d) · (\d+) min sooner — faster than waiting for the Tram 12", text)
    assert text.startswith("🚶 Finish on foot from Genève, Plainpalais") and m, text
    gain = int(m.group(2))
    # the difference matches the times on screen
    to_min = lambda hm: int(hm[:2]) * 60 + int(hm[3:])
    assert to_min(item().locator(".jr-top b").inner_text().split("→")[1].strip()) - to_min(m.group(1)) == gain
    assert "better" in offer.get_attribute("class")
    assert legs() == ["ride", "ride", "walk"], legs()
    bus_arrival = item().locator(".jr-top b").inner_text()
    print("offer       →", text.replace("\n", " | "), "| bus:", bus_arrival)
    pg.screenshot(path=str(OUT / "foot-offer.png"), full_page=True)

    # One tap: the tram is replaced by the walk; the bus stays one tap away
    offer.click()
    assert legs() == ["ride", "walk"], legs()
    assert "🚶 On foot at the end" in item().locator(".jr-meta").first.inner_text()
    assert "12" not in item().locator(".jr-segs").inner_text().replace("🚶12", "")
    alt = item().locator(".foot-toggle").inner_text()
    assert alt.startswith("🚌 Take the Tram 12 instead") and f"{gain} min later" in alt, alt
    assert item().locator(".leg.walk .walk-map").count() == 1, "the walk can be seen on the map"
    print("on foot     →", item().locator(".jr-top b").inner_text(), "|", alt.replace("\n", " | "))
    pg.screenshot(path=str(OUT / "foot-chosen.png"), full_page=True)
    item().locator(".foot-toggle").click()
    assert legs() == ["ride", "ride", "walk"] and item().locator(".jr-top b").inner_text() == bus_arrival

    # Alarms on the walking variant: only the bus 21 has a get-off reminder
    item().locator(".foot-toggle").click()
    item().locator(".set-alarms").click()
    plan = pg.inner_text("#alarmList [data-k=alights]")
    assert plan.startswith("Get-off reminders: Genève, Plainpalais") and "Bel-Air" not in plan, plan
    if pg.is_visible("#alarmBanner"): pg.click("#abOk")
    pg.click("#alarmList [data-act=cancel]")
    pg.clock.run_for(6000)
    if pg.is_visible("#alarmBanner"): pg.click("#abOk")

    # Learned: on foot 3 times here → the next search shows the walk first, with the bus as an alternative
    pg.evaluate("localStorage.removeItem('tpp:foot')")
    for _ in range(3):
        search(); assert item().locator(".foot-toggle").get_attribute("data-foot") == "1"; item().locator(".foot-toggle").click()
    search()
    assert legs() == ["ride", "walk"], "on foot by default after 3 choices"
    alt = item().locator(".foot-toggle").inner_text()
    assert "You often finish on foot here." in alt and alt.startswith("🚌 Take the Tram 12 instead"), alt
    # a tired day: the bus, one tap away
    item().locator(".foot-toggle").click()
    assert legs() == ["ride", "ride", "walk"]
    search()
    assert legs() == ["ride", "walk"], "still on foot first (3 on foot, 1 by bus)"
    print("learned     → on foot first, bus kept:", alt.split("\n")[0])

    # Not for longer walks: limit 10 min in Settings → no offer
    pg.click("#settingsBtn"); pg.fill("#setFootMax", "10"); pg.dispatch_event("#setFootMax", "change"); pg.click("#settingsClose")
    search()
    assert item().locator(".foot-toggle").count() == 0 and legs() == ["ride", "ride", "walk"]
    pg.click("#settingsBtn"); pg.fill("#setFootMax", "15"); pg.dispatch_event("#setFootMax", "change"); pg.click("#settingsClose")

    # Never chosen: offered 6 times (searches more than 10 min apart), then no longer offered
    pg.evaluate("localStorage.removeItem('tpp:foot')")
    for n in range(6):
        search(); assert item().locator(".foot-toggle").count() == 1, n
        pg.clock.run_for(11 * 60000)
    search()
    assert item().locator(".foot-toggle").count() == 0, "no longer offered after being ignored 6 times"
    print("ignored     → no longer offered after 6 searches")

    # Start on foot: from a point near Plainpalais, walk there instead of taking bus 21 first; same arrival, leave later
    pg.evaluate("localStorage.removeItem('tpp:foot')")
    pg.evaluate(f"localStorage.setItem('tpp:journey:from', JSON.stringify({{ kind: 'point', coord: [{START[0]}, {START[1]}], near: null }}))")
    pg.reload()
    search()
    rows = item().locator(".foot-toggle")
    assert rows.count() == 2, rows.all_inner_texts()
    start_row = item().locator(".foot-toggle[data-side=start]").inner_text()
    assert start_row.startswith("🚶 Start on foot to Genève, Plainpalais") and re.search(r"leave \d+ min later — no wait for the Bus 21", start_row), start_row
    assert "Leave later on foot" in item().locator(".jr-meta").first.inner_text() or "Faster on foot" in item().locator(".jr-meta").first.inner_text()
    arrival = item().locator(".jr-top b").inner_text().split("→")[1].strip()
    item().locator(".foot-toggle[data-side=start]").click()
    assert legs() == ["walk", "ride", "walk"], legs()
    assert item().locator(".jr-top b").inner_text().split("→")[1].strip() == arrival, "same arrival"
    assert "On foot at the start" in item().locator(".jr-meta").first.inner_text()
    assert item().locator(".foot-toggle").count() == 1, "one end on foot at a time"
    back = item().locator(".foot-toggle").inner_text()
    assert back.startswith("🚌 Take the Bus 21 first instead") and re.search(r"leave \d+ min earlier", back), back
    print("start       →", start_row.replace("\n", " | "), "|", item().locator(".jr-top b").inner_text())
    pg.screenshot(path=str(OUT / "foot-start.png"), full_page=True)
    item().locator(".foot-toggle").click()
    assert legs() == ["walk", "ride", "ride", "walk"], legs()

    # Walking slower than the bus: the walk says "later", the bus "sooner", matching the times shown
    FAST_TRAM["on"] = True
    pg.evaluate("localStorage.removeItem('tpp:foot')"); search()
    offer = item().locator(".foot-toggle[data-side=end]").inner_text()
    m = re.search(r"arrive (\d\d:\d\d) · (\d+) min later$", offer)
    assert m and "better" not in item().locator(".foot-toggle[data-side=end]").get_attribute("class"), offer
    bus_arr = item().locator(".jr-top b").inner_text().split("→")[1].strip()
    assert to_min(m.group(1)) - to_min(bus_arr) == int(m.group(2)), (offer, bus_arr)
    item().locator(".foot-toggle[data-side=end]").click()
    back = item().locator(".foot-toggle").inner_text()
    assert back.endswith(f"arrive {bus_arr} · {m.group(2)} min sooner"), back
    print("slower walk →", offer.split("\n")[1], "|", back.split("\n")[1])
    FAST_TRAM["on"] = False
    # French
    pg.evaluate("localStorage.removeItem('tpp:foot')"); search()
    pg.select_option("#lang", "fr")
    assert "Finir à pied depuis Genève, Plainpalais" in item().locator(".foot-toggle[data-side=end]").inner_text()
    assert "Partir à pied jusqu’à Genève, Plainpalais" in item().locator(".foot-toggle[data-side=start]").inner_text()
    pg.select_option("#lang", "en")
    b.close()

print("errors:", errors); assert not errors
print("OK")
