"""BUG-07: a followed ride is matched on the live board by line AND direction. At Petit-Lancy, Les Esserts the tram 14
to Meyrin leaves from platform A and the tram 14 to Bernex from platform B, often in the same minute (real OJP data,
tests/fixtures/ojp/ser_esserts.xml): the Bernex tram's platform and delay must not be taken for ours.
A platform change is only what the board announces (its live platform differs from its own planned one)."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 13, 8, 40, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.1886, 6.1153)
BACHET = st("8587340", "Lancy, Pont-Rouge", 46.1900, 6.1260)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
ONEX = st("8587380", "Onex, Bandol", 46.1840, 6.1000)
VAILLY = st("8592911", "Bernex, Vailly", 46.1760, 6.0700)

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def call(s, arr=None, dep=None): return {"station": s, "arrival": fmt(at(arr)) if arr is not None else None, "departure": fmt(at(dep)) if dep is not None else None}
PLAN = {"sections": [{"journey": {"category": "T", "number": "14", "to": "Meyrin, Gravière", "operator": "TPG",
                                  "passList": [call(ESSERTS, dep=14), call(BACHET, 16, 16), call(BELAIR, arr=27)]}, "walk": None,
                      "departure": end(ESSERTS, 14, "departure", "A"), "arrival": end(BELAIR, 27, "arrival", "A")}]}

S = {"with_stops": True, "meyrin": True, "meyrin_live": "A"}
def run(to, m, plan_plat, live_plat, delay, nxt):
    t0 = at(m)
    e = {"category": "T", "number": "14", "to": to, "operator": "TPG",
         "stop": {"station": ESSERTS, "departure": fmt(t0), "departureTimestamp": int(t0.timestamp()),
                  "prognosis": {"departure": fmt(t0 + dt.timedelta(minutes=delay)), "platform": live_plat}, "platform": plan_plat, "delay": delay},
         "passList": [{"station": ESSERTS}]}
    if S["with_stops"]:
        e["passList"] += [{"station": x, "arrival": fmt(at(mm + delay)), "prognosis": {"arrival": fmt(at(mm + delay))}} for x, mm in nxt]
    return e
def board():
    # the Bernex tram leaves 30 s before ours, 1 min late, from B
    out = [run("Bernex-Vailly", 13.5, "B", "B", 1, [(ONEX, 17), (VAILLY, 24)])]
    if S["meyrin"]: out.append(run("Meyrin-Gravière", 14, "A", S["meyrin_live"], 0, [(BACHET, 16), (BELAIR, 27)]))
    out.append(run("Bernex-Vailly", 30, "B", "B", 0, [(ONEX, 33)]))   # the board covers later times
    return out
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query)
    if u.path.endswith("/connections"): body = {"connections": [PLAN]}
    elif u.path.endswith("/locations"): body = {"stations": [BELAIR]}
    else: body = {"station": {"id": q["id"][0]}, "stationboard": board() if q["id"][0] == ESSERTS["id"] else []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="en-US", timezone_id="Europe/Zurich")
    ctx.route("https://transport.opendata.ch/**", api)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    pg.evaluate("""() => {
      localStorage.setItem('tpp:journey:from', JSON.stringify({ kind: 'stop', id: '8587418', name: 'Petit-Lancy, Les Esserts', coord: [46.1886, 6.1153] }));
      localStorage.setItem('tpp:journey:to', JSON.stringify({ kind: 'stop', id: '8587387', name: 'Genève, Bel-Air', coord: [46.204728, 6.143048] }));
      localStorage.setItem('tpp:settings', JSON.stringify({ footMaxMin: 0 }));
      localStorage.setItem('tpp:tab', '"journey"'); }""")
    pg.reload()
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
    pg.click("#journeyList .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    def refresh():
        pg.clock.run_for(61000); pg.wait_for_timeout(300)
        while pg.is_visible("#alarmBanner"): pg.click("#abOk")
        return pg.locator("#alarmList .trip").first
    def ride():
        return pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan.find(l => l.type === 'ride')")

    # 1. live boards with next stops: the Meyrin tram is ours, on time, platform A
    trip = refresh()
    r = ride()
    assert r["platformLive"] is None and r["real"] == int(at(14).timestamp() * 1000), r
    assert trip.locator(".plat.changed").count() == 0 and "Platform A" in trip.inner_text() and "Platform B" not in trip.inner_text(), trip.inner_text()
    print("next stops  → Bernex tram (B, +1) ignored; ours: platform A, on time")

    # 2. light boards (no next stops): the terminus decides ("Meyrin-Gravière" = "Meyrin, Gravière")
    S["with_stops"] = False
    trip = refresh(); r = ride()
    assert r["platformLive"] is None and r["real"] == int(at(14).timestamp() * 1000), r
    print("terminus    → without next stops, matched by terminus")

    # 3. a real change, announced by the board: A → C
    S["meyrin_live"] = "C"
    trip = refresh(); r = ride()
    assert r["platformLive"] == "C" and trip.locator(".plat.changed .plat-v").inner_text() == "C", r
    S["meyrin_live"] = "A"
    trip = refresh(); assert ride()["platformLive"] is None
    print("announced   → A → C shown, back to A cleared")

    # 4. our tram not on the board but the other direction is: not 'cancelled', nothing taken from it
    S["meyrin"] = False
    trip = refresh(); r = ride()
    assert not r.get("missing") and r["platformLive"] is None, r
    S["meyrin"] = True
    print("other only  → not marked cancelled, nothing taken from the Bernex tram")

    # 5. a journey followed before the fix, with the Bernex tram's platform and delay: cleaned once
    pg.evaluate("""() => { const l = JSON.parse(localStorage.getItem('tpp:alarms'));
      const r = l[0].plan.find(x => x.type === 'ride'); r.platformLive = 'B'; r.real = r.dep + 60000; delete l[0].runCheck;
      localStorage.setItem('tpp:alarms', JSON.stringify(l)); }""")
    pg.reload(); pg.wait_for_selector("#alarmList .trip")
    trip = refresh(); r = ride()
    assert r["platformLive"] is None and r["real"] == int(at(14).timestamp() * 1000), r
    assert trip.locator(".plat.changed").count() == 0, trip.inner_text()
    pg.screenshot(path=str(OUT / "run-direction.png"))
    print("old journey → wrong platform B and +1 min cleared")
    b.close()

print("errors:", errors); assert not errors
print("OK")
