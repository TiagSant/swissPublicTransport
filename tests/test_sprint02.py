import os, json, datetime as dt
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-02-directions/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
HERE = {"id": "8587057", "name": "Genève, Bel-Air"}
def dep(cat, num, to, mins, nxt=None, delay=0, plat=""):
    t = now + dt.timedelta(minutes=mins)
    pl = [{"station": HERE}] + ([{"station": {"id": nxt[0], "name": nxt[1]}}] if nxt else [])
    return {"category": cat, "number": num, "to": to, "operator": "TPG", "passList": pl,
            "stop": {"station": HERE, "departure": fmt(t), "departureTimestamp": int(t.timestamp()),
                     "delay": delay or None, "platform": plat,
                     "prognosis": {"departure": fmt(t + dt.timedelta(minutes=delay)) if delay else None}}}
MOL = ("100", "Genève, Molard"); NEU = ("200", "Genève, Place de Neuve")
board = {"station": HERE, "stationboard": [
    dep("T", "12", "Moillesulaz", 1, MOL), dep("T", "12", "Carouge, Bachet", 3, NEU),
    dep("T", "12", "Genève, Rive", 5, MOL),  # short run, same direction as Moillesulaz
    dep("T", "14", "Meyrin, Gravière", 4, ("300", "Stand")), dep("T", "14", "Bernex, P+R", 6, MOL),
    dep("B", "3", "Gardiol", 7, ("400", "Coutance"), delay=2),
    dep("T", "12", "Moillesulaz", 9, MOL), dep("T", "12", "Carouge, Bachet", 11, NEU),
    dep("BAT", "M2", "Pâquis", 8)]}  # no passList → direction = terminus
locs = {"stations": [{"id": "8587057", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
def handle(route):
    body = board if "/stationboard" in route.request.url else locs
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://transport.opendata.ch/**", handle)
    # Existing Sprint 1 preference: line 3 hidden → must be carried over
    ctx.add_init_script("""if(!sessionStorage.getItem('x')){sessionStorage.setItem('x','1');
      localStorage.setItem('tpp:hidden:8587057', JSON.stringify(['bus|3']));}""")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(PAGE); pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
    pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")
    badges = lambda: pg.locator(".dep .badge").all_inner_texts()
    assert "3" not in badges(), "Sprint 1 pref not honored"; print("S1 pref OK")
    pg.click("#dirToggle")
    g12 = pg.locator(".dir[data-line='tram|12']")
    print("dirs 12:", g12.all_inner_texts())
    assert g12.count() == 2
    # keep only 12 → Moillesulaz (direction via Molard)
    pg.locator(".dir[data-dir='tram|12>200']").click()
    tos = [t for t in pg.locator(".dep").all_inner_texts() if t.startswith("12")]
    print("12 rows:", [t.split("\n")[1] for t in tos])
    assert all("Bachet" not in t for t in tos) and any("Rive" in t for t in tos)
    print("chip 12:", pg.locator(".line-chip[data-key='tram|12']").get_attribute("aria-pressed"),
          pg.locator(".line-chip[data-key='tram|12']").inner_text())
    pg.screenshot(path=str(OUT / "s2_dirs.png"), full_page=True)
    # last direction → whole line hidden, then re-enable a single direction
    pg.locator(".dir[data-dir='tram|12>100']").click()
    assert "12" not in badges(); print("hidden:", pg.evaluate("localStorage.getItem('tpp:hidden:8587057')"))
    pg.locator(".dir[data-dir='tram|12>200']").click()
    tos = [t.split("\n")[1] for t in pg.locator(".dep").all_inner_texts() if t.startswith("12")]
    print("only Bachet:", tos); assert tos and all("Bachet" in t for t in tos)
    # chip tap = whole line
    pg.locator(".line-chip[data-key='tram|12']").click(); assert "12" not in badges()
    pg.locator(".line-chip[data-key='tram|12']").click(); assert badges().count("12") == 5
    # persistence after reload
    pg.locator(".dir[data-dir='tram|14>300']").click()
    pg.wait_for_function("(localStorage.getItem('tpp:hidden:8587057') || '').includes('tram|14>300')")
    pg.reload(); pg.wait_for_selector(".dir[data-dir='tram|14>300']", state="attached")
    assert pg.locator(".dir[data-dir='tram|14>300']").get_attribute("aria-pressed") == "false"
    print("boat dir:", pg.locator(".dir[data-line='ship|M2']").inner_text().replace("\n", " "))
    pg.click("#noLines"); assert pg.locator(".dep").count() == 0
    pg.click("#allLines"); print("all:", pg.locator(".dep").count())
    b.close()
print("errors:", errors)
