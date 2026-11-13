"""BUG-08: changing platform means walking. Tram 17 arrives at Lancy-Pont-Rouge, gare platform A, bus 42 leaves from
platform C of the same stop, and the API gives no walk between them: the app adds one (from the platforms'
positions, at least 1 min). No walk only at the same stop AND the same platform."""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); NOW = dt.datetime(2026, 11, 13, 16, 20, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z"); at = lambda m: NOW + dt.timedelta(minutes=m)
def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
UNIMAIL = st("8592858", "Genève, Uni-Mail", 46.1953, 6.1398)
LPR = st("8516155", "Lancy-Pont-Rouge, gare", 46.1867, 6.1257)
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188095, 6.113098)
S = {"p42": "C"}
def end(s, m, kind, plat): return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(cat, num, to, a, b, m0, m1, p0, p1):
    return {"journey": {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": [{"station": a, "departure": fmt(at(m0))}, {"station": b, "arrival": fmt(at(m1))}]},
            "walk": None, "departure": end(a, m0, "departure", p0), "arrival": end(b, m1, "arrival", p1)}
def api(route):
    u = urlparse(route.request.url)
    if u.path.endswith("/connections"):
        body = {"connections": [{"sections": [ride("T", "17", "Lancy-Pont-Rouge, gare", UNIMAIL, LPR, 8, 15, "O", "A"),     # no walk section
                                              ride("B", "42", "Avusy-Village", LPR, ESSERTS, 20, 24, S["p42"], "B")]}]}
    else: body = {"stations": [ESSERTS]} if u.path.endswith("/locations") else {"stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
STOP = lambda s: {"kind": "stop", "id": s["id"], "name": s["name"], "coord": [s["coordinate"]["x"], s["coordinate"]["y"]]}
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    def session(store):
        ctx = b.new_context(viewport={"width": 390, "height": 900}, locale="fr-CH", timezone_id="Europe/Zurich")
        ctx.route("https://transport.opendata.ch/**", api)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
        pg.evaluate("s => { for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", dict({"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False}}, **store))
        pg.reload(); pg.wait_for_function("!!window.QUAYS", timeout=10000)
        return ctx, pg
    base = {"journey:from": STOP(UNIMAIL), "journey:to": STOP(ESSERTS)}

    ctx, pg = session(base)
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    jr = pg.locator("#journeyList .jr").first
    assert jr.locator(".jw").count() == 1 and "1 min de marche" in jr.locator(".jr-meta").inner_text(), jr.inner_text()
    jr.click(); det = pg.locator("#journeyList .jr-detail").first
    w = det.locator(".leg.walk")
    assert w.count() == 1 and "jusqu’à Lancy-Pont-Rouge, gare" in " ".join(w.inner_text().split()) and w.locator(".walk-map").count() == 1, det.inner_text()
    wait = det.locator(".leg.ride .wait").inner_text()
    import re as _re
    assert not _re.search(r"\d[.,]\d+ min", det.inner_text() + jr.inner_text()), det.inner_text()   # whole minutes only
    assert "1 min de marche, puis 4 min d’attente" in wait, wait
    pg.screenshot(path=str(OUT / "change-walk.png"))
    print("A → C       → walk added: '1 min de marche, puis 4 min d’attente', with its map")

    # a journey followed before: its walk added at the next refresh
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    pg.evaluate("""() => { const l = JSON.parse(localStorage.getItem('tpp:alarms')); l[0].plan = l[0].plan.filter(x => x.type !== 'walk' || x.edge !== 'transfer'); delete l[0].changeWalks; localStorage.setItem('tpp:alarms', JSON.stringify(l)); }""")
    pg.reload(); pg.wait_for_selector("#alarmList .trip")
    pg.clock.run_for(61000); pg.wait_for_timeout(400)
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    types = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0].plan.map(x => x.type)")
    assert types == ["ride", "walk", "ride"], types
    assert "1 min de marche, puis 4 min d’attente" in pg.locator("#alarmList .trip").inner_text()
    ctx.close()
    print("followed    → a journey followed before gets its walk")

    # the same platform: no walk (BUG-06 unchanged)
    S["p42"] = "A"
    ctx, pg = session(base)
    pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr")
    jr = pg.locator("#journeyList .jr").first
    assert jr.locator(".jw").count() == 0 and "pas de marche" in jr.locator(".jr-meta").inner_text(), jr.inner_text()
    ctx.close()
    print("A → A       → no walk")
    b.close()
print("errors:", errors); assert not errors
print("OK")
