"""Sprint 6: journeys (US-14/15, US-07/08/09), departure alarms (US-16/17), settings and learned walking speed
(US-18/19), web simulation (TECH-04). The browser clock is frozen so alarms can be fast-forwarded."""
import os, json, math, re, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-06-journeys/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)            # frozen browser clock
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

ESSERTS = {"id": "8587418", "name": "Petit-Lancy, Les Esserts", "coordinate": {"type": "WGS84", "x": 46.188100, "y": 6.113100}}
PREMONNARD = {"id": "8592993", "name": "Petit-Lancy, Pré-Monnard", "coordinate": {"type": "WGS84", "x": 46.191000, "y": 6.118000}}
BELAIR = {"id": "8587387", "name": "Genève, Bel-Air", "coordinate": {"type": "WGS84", "x": 46.204728, "y": 6.143048}}
CORNAVIN = {"id": "8587057", "name": "Genève, gare Cornavin", "coordinate": {"type": "WGS84", "x": 46.209733, "y": 6.142437}}
HOME = (46.189000, 6.115000)    # a point picked on the map, ~170 m from Les Esserts

def point(st, m, kind, plat="", prog=None):
    p = {"station": st, "platform": plat, "delay": None, "prognosis": {}}
    p[kind] = fmt(at(m)); p[kind + "Timestamp"] = int(at(m).timestamp())
    if prog is not None: p["prognosis"][kind] = fmt(at(prog)); p["delay"] = prog - m
    return p
def ride(cat, num, to, a, b, ma, mb, plat="", prog=None):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": [{"station": a}, {}, {}, {"station": b}]},
            "walk": None, "departure": point(a, ma, "departure", plat, prog), "arrival": point(b, mb, "arrival")}
def walk(a, b, ma, mb):
    return {"journey": None, "walk": {"duration": (mb - ma) * 60}, "departure": point(a, ma, "departure"), "arrival": point(b, mb, "arrival")}
def conn(*sections): return {"sections": list(sections)}

CONNECTIONS = {
    ("8587418", "8587057"): [conn(ride("T", "14", "Meyrin, Gravière", ESSERTS, CORNAVIN, 14, 38, "B", prog=16)),            # fast, live +2
                             conn(ride("B", "21", "Carouge, Rondeau", ESSERTS, BELAIR, 9, 25, "C"), walk(BELAIR, BELAIR, 25, 28),
                                  ride("T", "15", "Genève, Nations", BELAIR, CORNAVIN, 29, 36, "E"))],                     # 1 change, earliest arrival
    ("8592993", "8587057"): [conn(ride("B", "23", "Aéroport", PREMONNARD, CORNAVIN, 12, 35, "A"))],
}
STATIONBOARD_PROG = {"value": 16}   # live departure of the tram 14 (minutes after NOW), changed during the test
requests = []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query); requests.append(route.request.url)
    if u.path.endswith("/locations"):
        if "x" in q:
            body = {"stations": [dict(ESSERTS, distance=170), dict(PREMONNARD, distance=330)]}
        else:
            name = q["query"][0].lower()
            body = {"stations": [s for s in (ESSERTS, CORNAVIN, BELAIR) if any(w in s["name"].lower() for w in name.split())]}
            body["stations"] = [dict(s, icon="tram") for s in body["stations"]]
    elif u.path.endswith("/connections"):
        body = {"connections": CONNECTIONS.get((q["from"][0], q["to"][0]), [])}
    else:   # stationboard: live data for the tram 14 at Les Esserts
        j = {"category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG", "passList": [{"station": ESSERTS}],
             "stop": {"station": ESSERTS, "departure": fmt(at(14)), "departureTimestamp": int(at(14).timestamp()),
                      "prognosis": {"departure": fmt(at(STATIONBOARD_PROG["value"]))}, "delay": STATIONBOARD_PROG["value"] - 14, "platform": "B"}}
        body = {"station": ESSERTS, "stationboard": [j]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def hav(a, b):
    r = math.pi / 180; h = math.sin((b[0]-a[0])*r/2)**2 + math.cos(a[0]*r)*math.cos(b[0]*r)*math.sin((b[1]-a[1])*r/2)**2
    return 2 * 6371000 * math.asin(math.sqrt(h))
hm = lambda d: d.strftime("%H:%M")

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="en-US", timezone_id="Europe/Zurich",
                        geolocation={"latitude": HOME[0], "longitude": HOME[1], "accuracy": 10}, permissions=["geolocation"])
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)

    # 1. Stop-to-stop journey (US-14), fastest first (US-07)
    pg.click(".tabs button[data-tab='journey']")
    pg.fill("#fromQ", "Esserts"); pg.clock.run_for(400); pg.locator("#fromResults button").first.click()
    pg.fill("#toQ", "Cornavin"); pg.clock.run_for(400); pg.locator("#toResults button").first.click()
    pg.click("#searchJourney"); pg.wait_for_selector(".jr")
    tops = [e.inner_text() for e in pg.locator(".jr-top b").all()]
    print("1 stop→stop:", tops)
    assert tops == ["07:39 → 08:06", "07:46 → 08:08"], tops     # bus 21 + tram 15 arrives first; tram 14 live +2
    assert "1 change" in pg.locator(".jr").first.inner_text() and "Fastest" in pg.locator(".jr").first.inner_text()

    # 2. Least walking (US-08) re-sorts; remembered (US-09)
    pg.click("#prio button[data-prio='walk']")
    tops2 = [e.inner_text() for e in pg.locator(".jr-top b").all()]
    assert tops2 == ["07:46 → 08:08", "07:39 → 08:06"], tops2
    assert pg.evaluate("JSON.parse(localStorage.getItem('tpp:prio'))") == "walk"
    print("2 least walking:", tops2)

    # 3. Start from a point on the map (US-15): nearest stops tried, walk at the rider's speed included
    pg.clock.resume()
    pg.click(".place-map[data-which='from']"); pg.wait_for_selector(".leaflet-container")
    box = pg.locator("#map").bounding_box()
    pg.evaluate(f"document.querySelector('#map')")   # map ready
    pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    pg.wait_for_function("document.getElementById('mapInfo').textContent.includes('from Petit-Lancy')")
    pg.click("#pickConfirm")
    label = pg.input_value("#fromQ"); assert label.startswith("Point on the map · ") and "Les Esserts" in label, label
    print("3 picked:", label)
    pg.evaluate(f"""(() => {{ const k = 'tpp:journey:from'; const v = JSON.parse(localStorage.getItem(k));
        v.coord = [{HOME[0]}, {HOME[1]}]; localStorage.setItem(k, JSON.stringify(v)); }})()""")   # pin the point precisely
    pg.reload(); pg.wait_for_selector("#fromQ")
    pg.clock.install(time=NOW.timestamp()); pg.reload(); pg.wait_for_selector("#fromQ")
    pg.click("#searchJourney"); pg.wait_for_selector(".jr")
    access = hav(HOME, (46.1881, 6.1131)) * 1.3 / 80          # metres × detour / (4.8 km/h in m/min)
    segs = pg.locator(".jr").first.inner_text()
    print("3 from point:", [e.inner_text() for e in pg.locator(".jr-top b").all()], "| access walk", round(access, 2), "min")
    assert "🚶" in segs
    assert pg.locator(".jr").count() == 3                     # Les Esserts ×2 + Pré-Monnard ×1

    # 4. Detail view and alarms (US-16): times from the first vehicle, walk, margin and preparation
    pg.click("#prio button[data-prio='fast']")
    tram14 = [i for i, e in enumerate(pg.locator(".jr").all()) if "14" in e.locator(".jr-segs").inner_text()][0]
    pg.locator(".jr").nth(tram14).click(); pg.wait_for_selector("#journeyDetail:not([hidden]) .leg.ride")
    detail = pg.locator("#journeyDetail").inner_text()
    assert "Walk 3 min" in detail and "to Petit-Lancy, Les Esserts" in detail, detail
    assert pg.locator("#journeyDetail .plat").first.inner_text().split() == ["Platform", "B"]
    pg.click("#setAlarms"); pg.wait_for_selector(".alarm")
    leave = at(16) - dt.timedelta(minutes=access + 1); ready = leave - dt.timedelta(minutes=10)
    got = {k: pg.locator(f".alarm b[data-k='{k}']").inner_text() for k in ("ready", "leave", "dep")}
    print("4 alarm:", got, "| expected leave", hm(leave), "ready", hm(ready))
    assert got == {"ready": hm(ready), "leave": hm(leave), "dep": "07:46"}, got
    assert "Live +2 min" in pg.locator(".alarm [data-k='src']").inner_text()

    # 5. Live data moves the alarm (US-17): the tram is now +5
    STATIONBOARD_PROG["value"] = 19
    pg.clock.run_for(61000)
    pg.wait_for_function("document.querySelector(\".alarm b[data-k='dep']\").textContent === '07:49'")
    leave2 = at(19) - dt.timedelta(minutes=access + 1)
    assert pg.locator(".alarm b[data-k='leave']").inner_text() == hm(leave2)
    assert "Live +5 min" in pg.locator(".alarm [data-k='src']").inner_text()
    print("5 live +5 → leave", hm(leave2))

    # 6. Settings (US-18): 12 min to get ready → "Get ready" moves 2 min earlier
    pg.click("#settingsBtn"); pg.fill("#setPrep", "12"); pg.dispatch_event("#setPrep", "change"); pg.click("#settingsClose")
    ready2 = leave2 - dt.timedelta(minutes=12)
    assert pg.locator(".alarm b[data-k='ready']").inner_text() == hm(ready2)
    assert pg.locator("#alarmBanner").is_hidden()          # still in the future: nothing rings yet
    print("6 prep 12 → ready", hm(ready2))

    # 7. Alarms ring at the right time (fast-forward the clock)
    until_ready = (ready2 - at(0)).total_seconds() - 61 + 5
    pg.clock.run_for(int(until_ready * 1000))
    pg.wait_for_selector("#alarmBanner:not([hidden])")
    assert pg.locator("#abTitle").inner_text() == "⏰ Time to get ready"
    assert f"Leave at {hm(leave2)}" in pg.locator("#abBody").inner_text()
    pg.click("#abOk")
    pg.clock.run_for(15 * 60 * 1000)
    pg.wait_for_selector("#alarmBanner:not([hidden])")
    assert pg.locator("#abTitle").inner_text() == "🚶 Leave now" and pg.locator("#abTrack").is_visible()
    print("7 rang:", pg.locator("#abBody").inner_text())
    pg.screenshot(path=str(OUT / "s6_alarm_leave.png"))
    pg.click("#abOk")

    # 8. Learned walking speed (US-19, TECH-04): simulated 600 m walk at 5.6 km/h
    pg.click("#settingsBtn"); pg.fill("#simSpeed", "5.6"); pg.click("#simWalk")
    res = pg.locator("#simResult").inner_text(); print("8", res)
    measured = float(re.search(r"→ (\d\.\d) km/h", res).group(1))
    assert 5.5 <= measured <= 5.8, measured                  # GPS jitter adds a little path length
    expected = f"{round((0.3 * measured + 0.7 * 4.8) * 10) / 10:.1f}"   # moving average, 30 % weight for the new walk
    assert f"now {expected} km/h (1 walks)" in res, res
    assert pg.input_value("#setSpeed") == expected and "Learned from 1 walks" in pg.locator("#speedInfo").inner_text()
    pg.fill("#simSpeed", "12"); pg.click("#simWalk")
    assert "unusual speed" in pg.locator("#simResult").inner_text() and pg.input_value("#setSpeed") == expected
    pg.click("#resetLearning"); assert pg.input_value("#setSpeed") == "4.8"
    pg.click("#settingsClose")
    print("8 outlier ignored, reset OK")

    # 9. French
    pg.click("#lang")
    assert pg.locator(".tabs button[data-tab='journey']").inner_text() == "Itinéraire"
    assert pg.locator("#journeyDetail .leg.walk").first.inner_text().startswith("🚶") and "Marche" in pg.locator("#journeyDetail").inner_text()
    assert "Préparez-vous" in pg.locator("#alarmCard").inner_text()
    pg.screenshot(path=str(OUT / "s6_journey_fr.png"), full_page=True)
    print("9 FR OK")
    b.close()
print("errors:", errors); assert not errors
