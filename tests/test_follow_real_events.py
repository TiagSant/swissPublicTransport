"""BUG-17: following what really happens — the PO's trip of 17.11.2026, replayed.

Les Esserts → an address 10 min on foot from Jonction (tram 14, then on foot). Tram 14 runs late: the 08:30 is 7 min
late (leaves 08:37:30), the 08:34 4 min (08:38).
1. Followed at 08:35:30, the time to leave (08:37) within 2 min: leaving now — neither "Get ready" nor "Leave" rings.
2. 08:37 in a supermarket 450 m away: "You won't make the tram 14" (as before).
3. He runs and boards the earlier tram (08:30, still there): the GPS on the line, the phone in a vehicle → the 08:30
   run is followed, the warning goes.
4. The tram stops in traffic near Quidort: still "in a vehicle", no warning.
5. Late at Jonction (08:46): bus 19 (08:47) gets there 4 min sooner than the 10-min walk → offered.
6. He takes bus 19 without tapping: the GPS on its line, in a vehicle → the plan follows bus 19.
   (2nd run: the offer tapped instead.)
Motion: simulated DeviceMotion; GPS: emulated positions every 10 s. transport.opendata.ch is mocked.
Stop ids / positions: Les Esserts, Quidort, Jonction, Sainte-Clotilde real; "Petit-Lancy, place" and "Bains" approximate."""
import os, json, math, datetime as dt
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
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
PLACE = st("8592896", "Petit-Lancy, place", 46.1912, 6.1172)
QUIDORT = st("8592905", "Petit-Lancy, Quidort", 46.1945, 6.1215)
JONCTION = st("8587062", "Genève, Jonction", 46.200687, 6.129467)
CLOTILDE = st("8592908", "Genève, Sainte-Clotilde", 46.199879, 6.132626)
BAINS = st("8592780", "Genève, Bains", 46.1995, 6.1362)
STOPS = [ESSERTS, PLACE, QUIDORT, JONCTION, CLOTILDE, BAINS]
DEST = {"kind": "addr", "name": "Destination (rue des Bains)", "coord": [46.1990, 6.1368]}
C = lambda s: (s["coordinate"]["x"], s["coordinate"]["y"])
BASE = dt.datetime(2026, 11, 17, 8, 31, tzinfo=tz)
def at(h, m, s=0): return dt.datetime(2026, 11, 17, h, m, s, tzinfo=tz)
def dist(a, b):
    R = 6371000; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * R * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))

# tram 14 runs from Les Esserts: planned departure, delay (min); stops +2 / +4 / +7 min; the 08:30 is held in traffic
# before Jonction (arrives there 08:46)
RUNS = [(at(8, 30), 7, {"8587062": 9}), (at(8, 34), 4, {}), (at(8, 38), 0, {})]
def tram_calls(t0, d, extra):
    return [(PLACE, t0 + dt.timedelta(minutes=2), d), (QUIDORT, t0 + dt.timedelta(minutes=4), d), (JONCTION, t0 + dt.timedelta(minutes=7), extra.get("8587062", d))]
def prog(kind, t, d): return {kind: fmt(t + dt.timedelta(minutes=d))} if d else {}
def sec_ride(cat, num, to, a, b, t0, d0, calls, t1, d1, p0, p1):
    pl = [{"station": a, "departure": fmt(t0), "prognosis": prog("departure", t0, d0)}] + \
         [{"station": s, "arrival": fmt(t), "departure": fmt(t), "prognosis": prog("arrival", t, d)} for s, t, d in calls] + \
         [{"station": b, "arrival": fmt(t1), "prognosis": prog("arrival", t1, d1)}]
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl}, "walk": None,
            "departure": {"station": a, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": p0, "prognosis": prog("departure", t0, d0), "delay": d0},
            "arrival": {"station": b, "arrival": fmt(t1), "arrivalTimestamp": int(t1.timestamp()), "platform": p1, "prognosis": prog("arrival", t1, d1), "delay": d1}}
def tram_conn(t0, d, extra):
    calls = tram_calls(t0, d, extra); jt, jd = calls[-1][1], calls[-1][2]
    return {"sections": [sec_ride("T", "14", "Meyrin-Gravière", ESSERTS, JONCTION, t0, d, calls[:-1], jt, jd, "A", "")]}
def bus19(t0):   # Jonction → Sainte-Clotilde +1 → Bains +3
    return {"sections": [sec_ride("B", "19", "Vernier, Village", JONCTION, BAINS, t0, 0, [(CLOTILDE, t0 + dt.timedelta(minutes=1), 0)], t0 + dt.timedelta(minutes=3), 0, "B", "")]}
def board_entry(cat, num, to, here, t0, d, calls, plat):
    return {"category": cat, "number": num, "to": to, "operator": "TPG",
            "stop": {"station": here, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()), "platform": plat,
                     "prognosis": prog("departure", t0, d), "delay": d},
            "passList": [{"station": here}] + [{"station": s, "arrival": fmt(t), "arrivalTimestamp": int(t.timestamp()), "prognosis": prog("arrival", t, dd)} for s, t, dd in calls]}
def board(stop_id):
    if stop_id == ESSERTS["id"]: return [board_entry("T", "14", "Meyrin-Gravière", ESSERTS, t0, d, tram_calls(t0, d, x), "A") for t0, d, x in RUNS]
    if stop_id == JONCTION["id"]: return [board_entry("B", "19", "Vernier, Village", JONCTION, t0, 0, [(CLOTILDE, t0 + dt.timedelta(minutes=1), 0), (BAINS, t0 + dt.timedelta(minutes=3), 0)], "B") for t0 in (at(8, 47), at(8, 57))]
    return []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"):
        f, to = q.get("from", [""])[0], q.get("to", [""])[0]
        hm = q.get("time", ["08:00"])[0]; when = at(int(hm[:2]), int(hm[3:5]))
        if f == ESSERTS["id"] and to == JONCTION["id"]: body = [tram_conn(t0, d, x) for t0, d, x in RUNS if t0 >= when]
        elif f == JONCTION["id"] and to == BAINS["id"]: body = [bus19(t0) for t0 in (at(8, 47), at(8, 57)) if t0 >= when - dt.timedelta(minutes=2)]
        else: body = []
        body = {"connections": body}
    elif u.path.endswith("/stationboard"): body = {"station": {}, "stationboard": board(q.get("id", [""])[0])}
    elif u.path.endswith("/locations") and "x" in q:
        p = (float(q["x"][0]), float(q["y"][0]))
        near = sorted([dict(s, distance=round(dist(p, C(s)))) for s in STOPS if dist(p, C(s)) < 1200 and s is not CLOTILDE], key=lambda s: s["distance"])   # (a stop of bus 19 only here)
        body = {"stations": near}
    else: body = {"stations": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": list(C(s))}
norm = lambda s: " ".join(s.split())
FEED = """([kind, secs]) => { const n = Math.round(secs * 1000 / 16);
  for (let i = 0; i < n; i++) { const t = (window.__ft = (window.__ft || 0) + 0.016); let z = 9.81;
    if (kind === 'walk') z += 2.5 * Math.sin(2 * Math.PI * 1.9 * t) + (Math.random() - 0.5) * 0.6;
    else if (kind === 'ride') z += 0.3 * Math.sin(2 * Math.PI * 0.4 * t) + (Math.random() - 0.5) * 0.5;
    else z += (Math.random() - 0.5) * 0.04;
    window.dispatchEvent(new DeviceMotionEvent('devicemotion', { accelerationIncludingGravity: { x: 0.2, y: 0.1, z }, interval: 16 })); } }"""

def lerp(a, b, f): return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
SHOP = (46.188095, 6.1073)   # 450 m west of Les Esserts
# where the rider is (position, motion) at each moment
def where(t):
    s = (t - at(8, 37, 30)).total_seconds()
    if t < at(8, 37, 30): return SHOP, "walk"
    if s < 80: return lerp(C(ESSERTS), C(PLACE), s / 80), "ride"                       # 6 m/s
    if s < 160: return lerp(C(PLACE), C(QUIDORT), (s - 80) / 80), "ride"
    if t < at(8, 43): return C(QUIDORT), "still"                                         # stopped in traffic
    if t < at(8, 46): return lerp(C(QUIDORT), C(JONCTION), (t - at(8, 43)).total_seconds() / 180), "ride"
    if t < at(8, 47): return C(JONCTION), "walk"                                         # to bus 19
    if t < at(8, 48): return lerp(C(JONCTION), C(CLOTILDE), (t - at(8, 47)).total_seconds() / 50 if t < at(8, 47, 50) else 1), "ride"
    return lerp(C(CLOTILDE), C(BAINS), min(1, (t - at(8, 48)).total_seconds() / 50)), "ride"

errors = []
def session(b):
    ctx = b.new_context(viewport={"width": 390, "height": 1100}, locale="fr-CH", timezone_id="Europe/Zurich",
                        permissions=["geolocation"], geolocation={"latitude": SHOP[0], "longitude": SHOP[1], "accuracy": 10})
    ctx.route("https://transport.opendata.ch/**", api)
    for u in ("https://routing.openstreetmap.de/**", "https://nominatim.openstreetmap.org/**"): ctx.route(u, lambda r: r.abort())
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=BASE.timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 15, "realWalk": False}, "journey:from": STOP(ESSERTS), "journey:to": DEST}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr"); pg.wait_for_timeout(500)
    return ctx, pg
def now(pg): return dt.datetime.fromtimestamp(pg.evaluate("Date.now()") / 1000, tz)
def live_until(pg, ctx, until):   # 10-s steps: position, motion, clock
    while now(pg) < until:
        p, kind = where(now(pg))
        ctx.set_geolocation({"latitude": p[0], "longitude": p[1], "accuracy": 10})
        pg.evaluate(FEED, [kind, 10]); pg.clock.run_for(10000); pg.wait_for_timeout(120)
        while pg.is_visible("#alarmBanner"): RANG.append((now(pg), pg.inner_text("#abTitle"))); pg.click("#abOk")
    pg.wait_for_timeout(400)
RANG = []   # (time, title) of each alarm rung
card = lambda pg: norm(pg.locator("#alarmList .alarm").first.inner_text())
alarm = lambda pg: pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
hm = lambda ms: dt.datetime.fromtimestamp(ms / 1000, tz).strftime("%H:%M")

def until_offer(b):
    RANG.clear(); ctx, pg = session(b)
    cards = pg.locator("#journeyList .jr")
    assert "08:34" in cards.first.inner_text() or "08:38" in cards.first.inner_text(), cards.first.inner_text()
    pg.clock.run_for(int((at(8, 35, 30) - BASE).total_seconds() * 1000))
    cards.first.click(); pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .alarm")
    # 1. leaving now: nothing rings
    pg.clock.run_for(6000); pg.wait_for_timeout(200)
    assert pg.is_hidden("#alarmBanner"), pg.inner_text("#alarmBanner")
    assert "Départ maintenant" in card(pg), card(pg)
    assert alarm(pg)["plan"][0]["dep"] == int(at(8, 34).timestamp() * 1000) or alarm(pg)["plan"][1]["dep"] == int(at(8, 34).timestamp() * 1000)
    print("1 follow    → leaving now, nothing rang")
    # 2. in the supermarket at the time to leave: won't make it
    live_until(pg, ctx, at(8, 37, 30))
    assert "Vous n’aurez pas le Tram 14" in card(pg), card(pg)
    print("2 late      → 'Vous n’aurez pas le Tram 14'")
    # 3. on the earlier tram: followed, warning gone
    live_until(pg, ctx, at(8, 40, 10))
    a = alarm(pg); r = next(l for l in a["plan"] if l["type"] == "ride")
    assert hm(r["dep"]) == "08:30" and a.get("onBoard") and not a.get("late"), (hm(r["dep"]), a.get("onBoard"), a.get("late"))
    c = card(pg)
    assert "Vous n’aurez pas" not in c and "🚋 dans un véhicule" in c, c
    print("3 on board  → the 08:30 run followed, no warning,", "dans un véhicule")
    # 4. stopped in traffic: still in a vehicle; 5. faster than walking at Jonction: bus 19
    live_until(pg, ctx, at(8, 42, 30))
    c = card(pg)
    assert "🚋 dans un véhicule" in c and "Vous n’aurez pas" not in c and "Vous êtes à pied" not in c, c
    pg.wait_for_function("() => document.querySelector('#alarmList [data-act=faster]')", timeout=10000)
    o = norm(pg.inner_text("#alarmList [data-act=faster]"))
    assert "Plus rapide qu’à pied : Bus 19 à 08:47" in o, o
    pg.screenshot(path=str(OUT / "follow-real-events.png"), full_page=True)
    print("4 traffic   → still 'dans un véhicule';  5 offer →", o)
    off = [t for t, x in RANG if "descendez" in x]
    assert not off, f"get-off reminder too early: {off}"   # (it rang at 08:39, four stops early, on the run switched to)
    return ctx, pg

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    # 6. bus 19 taken without tapping: the plan follows it
    ctx, pg = until_offer(b)
    RANG.clear(); live_until(pg, ctx, at(8, 48, 40))
    off = [t.strftime("%H:%M:%S") for t, x in RANG if "descendez" in x]
    assert off and "08:43" <= off[0] < "08:45", off   # leaving Quidort after the traffic stop, for Jonction
    a = alarm(pg); rides = [l for l in a["plan"] if l["type"] == "ride"]
    assert rides[-1]["label"] == "19" and rides[-1]["toStop"]["name"] == "Genève, Bains", [(x["label"], x["toStop"]["name"]) for x in rides]
    assert "Bus 19" in card(pg) or "19" in card(pg)
    print("6 taken     → plan:", " › ".join(f"{x['label']} → {x['toStop']['name']}" for x in rides))
    ctx.close()
    # 2nd run: the offer tapped
    RANG.clear(); ctx, pg = until_offer(b)
    pg.click("#alarmList [data-act=faster]"); pg.wait_for_timeout(300)
    rides = [l for l in alarm(pg)["plan"] if l["type"] == "ride"]
    assert [x["label"] for x in rides] == ["14", "19"], [x["label"] for x in rides]
    print("tapped      → 14 › 19")
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
