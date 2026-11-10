"""Sprint 4: EN/FR interface (US-10), SBB pictograms (US-11), operator line colours (US-12)."""
import os, json, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-04-identity/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
HERE = {"id": "8587057", "name": "Genève, Bel-Air"}

def dep(cat, num, to, mins, op="TPG", nxt=("100", "Genève, Molard"), plat=""):
    t = now + dt.timedelta(minutes=mins)
    pl = [{"station": HERE}, {"station": {"id": nxt[0], "name": nxt[1]}, "arrival": fmt(t + dt.timedelta(minutes=2))}]
    return {"category": cat, "number": num, "to": to, "operator": op, "passList": pl,
            "stop": {"station": HERE, "departure": fmt(t), "departureTimestamp": int(t.timestamp()), "platform": plat, "prognosis": {}}}

board = {"station": HERE, "stationboard": [
    dep("T", "12", "Thônex, Moillesulaz", 1, plat="F"), dep("T", "14", "Meyrin, Gravière", 2, nxt=("300", "Coutance")),
    dep("B", "3", "Gardiol", 3, nxt=("300", "Coutance")), dep("BAT", "M2", "Quai Gustave Ador", 4, op="MGsa", nxt=("500", "Molard (lac)")),
    dep("R", "L2", "Annemasse", 5, op="SBB", nxt=("600", "Chêne-Bourg"), plat="1"),
    dep("IR", "15", "Luzern", 6, op="SBB", nxt=("700", "Genève"), plat="4"),
    dep("TER", "L3", "Annemasse", 7, op="SNCF", nxt=("600", "Chêne-Bourg")),
    dep("R", "55", "La Cure", 8, op="NStCM", nxt=("800", "Les Plantaz")),
    dep("B", "271", "Annemasse", 9, nxt=("900", "Rive")),
    dep("B", "N5", "Rive", 10, nxt=("900", "Rive")),          # not in the TPG table → neutral badge
    dep("IR", "001943", "Genève", 11, op="SBB", nxt=("700", "Genève")),  # run number → "IR", no icon → neutral
    dep("TER", "", "Bellegarde (Ain)", 13, op="SNCF", nxt=("700", "Genève")),  # non-LEX TER → SBB "TER" icon
    dep("T", "12", "Thônex, Moillesulaz", 12, plat="F")]}
locs = {"stations": [{"id": "8587057", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
def handle(route):
    body = board if "/stationboard" in route.request.url else locs
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def rgb(h): h = h.lstrip("#"); return f"rgb({int(h[0:2],16)}, {int(h[2:4],16)}, {int(h[4:6],16)})"
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))

    def open_board(locale, scheme="light"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale=locale, color_scheme=scheme)
        ctx.route("https://transport.opendata.ch/**", handle)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(PAGE); pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
        pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")
        pg.wait_for_function("[...document.images].every(i => i.complete)")
        return ctx, pg

    # 1. English phone → English UI
    ctx, pg = open_board("en-US")
    assert pg.evaluate("document.documentElement.lang") == "en"
    assert pg.locator("#q").get_attribute("placeholder").startswith("Stop:")
    assert pg.locator("#board [data-i18n='lines']").text_content() == "Lines"
    print("1 English UI OK")

    # 2. Every pictogram / timetable icon actually loads
    broken = pg.evaluate("[...document.images].filter(i => !i.naturalWidth).map(i => i.getAttribute('src'))")
    assert not broken, broken
    srcs = set(pg.evaluate("[...document.images].map(i => i.getAttribute('src').split('/').pop())"))
    for f in ["Tram_r.svg", "Bus_r.svg", "Zug_r.svg", "Schiff_r.svg", "ir-15.svg", "r-55.svg", "ter.svg"]:
        assert f in srcs, f
    print("2 pictograms loaded:", sorted(srcs))

    # 3. Operator colours
    def badge(dir_prefix):
        return pg.locator(f".dep[data-dir^='{dir_prefix}'] .badge").first
    checks = {"tram|12>": ("#F5A300", "#000000"), "tram|14>": ("#5A1E82", "#FFFFFF"), "bus|3>": ("#B82F89", "#FFFFFF"),
              "ship|M2>": ("#E95D15", "#FFFFFF"), "train|L2>": ("#0085CA", "#FFFFFF"), "train|L3>": ("#81B13E", "#FFFFFF"),
              "bus|271>": ("#FFDC00", "#000000")}
    for k, (bg, fg) in checks.items():
        el = badge(k)
        got = el.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]")
        assert got == [rgb(bg), rgb(fg)], (k, got)
    assert "hexagon" in badge("bus|271>").get_attribute("class")
    assert "neutral" in badge("bus|N5>").get_attribute("class")
    assert "neutral" in badge("train|IR>").get_attribute("class")
    assert pg.locator(".dep[data-dir^='train|IR 15>'] .tt img").get_attribute("src").endswith("ir-15.svg")
    assert pg.locator(".dep[data-dir^='train|L3>'] .tt").count() == 0          # SNCF "TER L3" is LEX-coloured, not the TER icon
    assert pg.locator(".dep[data-dir^='train|TER>'] .tt img").get_attribute("src").endswith("ter.svg")
    print("3 colours OK (TPG, LEX incl. SNCF-run L3, Mouettes, hexagon, neutral fallbacks, SBB icons)")
    overlaps = pg.evaluate("""[...document.querySelectorAll('.dep')].filter(li => {
        const id = li.querySelector('.line-id').getBoundingClientRect(), to = li.querySelector('.to').getBoundingClientRect();
        return id.right > to.left; }).map(li => li.dataset.dir)""")
    assert not overlaps, overlaps
    pg.screenshot(path=str(OUT / "s4_en_light.png"), full_page=True)

    # 4. Language switch persists, times stay 24-hour
    pg.click("#lang")
    assert pg.evaluate("document.documentElement.lang") == "fr" and pg.locator("#q").get_attribute("placeholder").startswith("Arrêt")
    assert "Quai F" in pg.locator(".dep").first.inner_text()
    pg.reload(); pg.wait_for_selector(".dep")
    assert pg.evaluate("document.documentElement.lang") == "fr"
    t = pg.locator(".dep .when small").first.inner_text()
    assert ":" in t and "M" not in t, t
    print("4 switch to FR persists; time format", t)
    ctx.close()

    # 5. French phone → French UI by default, dark mode uses negative SBB icons
    ctx, pg = open_board("fr-CH", "dark")
    assert pg.evaluate("document.documentElement.lang") == "fr"
    cur = pg.evaluate("document.querySelector(\".dep[data-dir^='train|IR 15>'] .tt img\").currentSrc")
    assert cur.endswith("ir-15-negative.svg"), cur
    pg.click("#dirToggle")
    assert "prochain arrêt" in pg.locator("#dirs").inner_text()
    print("5 French by default; dark mode icon:", cur.split("/")[-1])
    pg.screenshot(path=str(OUT / "s4_fr_dark.png"), full_page=True)
    ctx.close()

    # 6. Habits (US-06) still work: two uses > 10 min apart → auto selection
    ctx, pg = open_board("en-US")
    D = "tram|12>100"
    pg.locator(f".dep[data-dir='{D}']").first.click()
    assert len(pg.locator(".dep[aria-expanded='true'] .stops li").all()) == 1
    pg.evaluate(f"""(() => {{ const k='tpp:usage:8587057', u=JSON.parse(localStorage.getItem(k)); u['{D}'].t -= 11*60*1000; localStorage.setItem(k, JSON.stringify(u)); }})()""")
    pg.locator(f".dep[data-dir='{D}']").first.click(); pg.locator(f".dep[data-dir='{D}']").first.click()
    assert pg.locator("#autoInfo").inner_text().startswith("★ Your usual lines")
    assert {e.get_attribute("data-dir") for e in pg.locator(".dep").all()} == {D}
    assert pg.locator(".line-chip").first.get_attribute("data-key") == "tram|12"
    print("6 habits OK")
    ctx.close()
    b.close()
print("errors:", errors); assert not errors
