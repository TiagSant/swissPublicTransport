"""Sprint 3 / US-06: automatic preselection of usual lines."""
import os, json, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-03-habitudes/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
HERE = {"id": "8587057", "name": "Genève, Bel-Air"}
def dep(cat, num, to, mins, path=()):
    t = now + dt.timedelta(minutes=mins)
    pl = [{"station": HERE}] + [{"station": {"id": sid, "name": nm}, "arrival": fmt(t + dt.timedelta(minutes=2 * (k + 1)))}
                                for k, (sid, nm) in enumerate(path)]
    return {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl,
            "stop": {"station": HERE, "departure": fmt(t), "departureTimestamp": int(t.timestamp()), "prognosis": {}}}
EST = [("100", "Genève, Molard"), ("101", "Genève, Rive"), ("102", "Terrassière")]
SUD = [("200", "Place de Neuve"), ("201", "Plainpalais")]
board = {"station": HERE, "stationboard": [
    dep("T", "12", "Moillesulaz", 2, EST), dep("T", "12", "Carouge, Bachet", 3, SUD),
    dep("T", "14", "Meyrin, Gravière", 4, [("300", "Stand")]), dep("B", "3", "Gardiol", 5, [("400", "Coutance")]),
    dep("T", "12", "Moillesulaz", 9, EST), dep("T", "12", "Carouge, Bachet", 11, SUD), dep("T", "14", "Meyrin, Gravière", 12, [("300", "Stand")])]}
locs = {"stations": [{"id": "8587057", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
def handle(route):
    body = board if "/stationboard" in route.request.url else locs
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://transport.opendata.ch/**", handle)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    LS = lambda k: pg.evaluate(f"JSON.parse(localStorage.getItem('tpp:{k}:8587057'))")
    badges = lambda: [t.split("\n")[0] + ">" + t.split("\n")[1] for t in pg.locator(".dep").all_inner_texts()]
    pg.goto(PAGE); pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
    pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")

    # 1. First visit: everything visible, no preselection
    assert pg.locator(".dep").count() == 7 and pg.locator("#autoInfo").is_hidden(); print("1 fresh OK")

    # 2. Tap a departure: next stops + 1 use; tapping again right away does not count (debounce)
    MOL = "tram|12>100"
    pg.locator(f".dep[data-dir='{MOL}']").first.click()
    stops = pg.locator(".dep[aria-expanded='true'] .stops li").all_inner_texts(); print("2 stops:", stops)
    assert len(stops) == 3 and "Molard" in stops[0]
    pg.locator(f".dep[data-dir='{MOL}']").first.click(); pg.locator(f".dep[data-dir='{MOL}']").first.click()
    assert round(LS("usage")[MOL]["s"], 2) == 1.0 and pg.locator("#autoInfo").is_hidden(); print("2 debounce OK")

    # 3. Second use (> 10 min later) → usual direction → auto selection
    pg.evaluate(f"""(() => {{ const k='tpp:usage:8587057', u=JSON.parse(localStorage.getItem(k));
        u['{MOL}'].t -= 11*60*1000; localStorage.setItem(k, JSON.stringify(u)); }})()""")
    pg.locator(f".dep[data-dir='{MOL}']").first.click(); pg.locator(f".dep[data-dir='{MOL}']").first.click()
    print("3 auto:", pg.locator("#autoInfo").inner_text().replace("\n", " | "), badges())
    assert set(badges()) == {"12>Moillesulaz"}
    chips = pg.locator(".line-chip").all_inner_texts(); print("3 chips:", [c.replace("\n", "") for c in chips])
    assert chips[0].replace("\n", "").startswith("🚋12★")
    pg.screenshot(path=str(OUT / "s3_auto.png"), full_page=True)

    # 4. "See all" is temporary
    pg.click("#peek"); assert pg.locator(".dep").count() == 7
    pg.click("#peek"); assert set(badges()) == {"12>Moillesulaz"}; print("4 see all OK")

    # 5. Manual setting: start from what is displayed, add the 14
    pg.locator(".line-chip[data-key='tram|14']").click()
    print("5 manual:", sorted(set(badges())), pg.locator("#autoInfo").inner_text().replace("\n", " | "))
    assert set(badges()) == {"12>Moillesulaz", "14>Meyrin, Gravière"} and LS("mode") == "manual"

    # 6. Reload: manual persists; then back to habits
    pg.reload(); pg.wait_for_selector(".dep"); assert set(badges()) == {"12>Moillesulaz", "14>Meyrin, Gravière"}
    pg.click("#backAuto"); assert set(badges()) == {"12>Moillesulaz"} and LS("mode") == "auto"; print("6 back to auto OK")
    pg.reload(); pg.wait_for_selector(".dep"); assert set(badges()) == {"12>Moillesulaz"}; print("6 auto persists OK")

    # 7. Gradual forgetting: 4 uses 60 days ago = score 1 → no longer usual
    pg.evaluate(f"""localStorage.setItem('tpp:usage:8587057', JSON.stringify({{'{MOL}': {{s: 4, t: Date.now() - 60*864e5}}}}))""")
    pg.reload(); pg.wait_for_selector(".dep"); assert pg.locator(".dep").count() == 7; print("7 decay OK")

    # 8. Compatibility: Sprint 2 filter (line 3 hidden, no mode) → stays manual
    pg.evaluate("""localStorage.removeItem('tpp:mode:8587057'); localStorage.setItem('tpp:hidden:8587057', '["bus|3"]')""")
    pg.reload(); pg.wait_for_selector(".dep"); assert "3>Gardiol" not in badges() and pg.locator(".dep").count() == 6
    print("8 migration OK")
    b.close()
print("errors:", errors); assert not errors
