import os, json, sys, datetime as dt
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-01-departs/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
tz = ZoneInfo("Europe/Zurich")
now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")

def dep(cat, num, to, mins, delay=0, plat="", op="TPG"):
    t = now + dt.timedelta(minutes=mins)
    real = t + dt.timedelta(minutes=delay)
    return {"category": cat, "number": num, "name": f"{cat} {num}", "to": to, "operator": op,
            "stop": {"departure": fmt(t), "departureTimestamp": int(t.timestamp()), "delay": delay or None,
                     "platform": plat, "prognosis": {"departure": fmt(real) if delay else None, "platform": None}}}

board = {"station": {"id": "8587057", "name": "Genève, Bel-Air"}, "stationboard": [
    dep("T", "12", "Moillesulaz", 1), dep("T", "14", "Meyrin, Gravière", 3, plat="A"),
    dep("B", "3", "Gardiol", 4, delay=2), dep("T", "12", "Carouge, Bachet", 6),
    dep("BAT", "M2", "Pâquis", 7, op="SMGN"), dep("S", "L2", "Annemasse", 9, plat="3", op="SNCF"),
    dep("IR", "2523", "Lausanne", 11, plat="5", op="SBB"), dep("T", "18", "CERN", 12),
    dep("B", "5", "Aéroport", 14), dep("NFB", "N1", "Rive", 70)]}
locs_belair = {"stations": [
    {"id": "1", "name": "Bel-Air, Lausanne", "coordinate": {"x": 46.52, "y": 6.63}, "icon": "bus"},
    {"id": "8587057", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
locs_gva = {"stations": [{"id": "8587057", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"},
    {"id": "8587058", "name": "Genève, Bel-Air Cité", "coordinate": {"x": 46.2047, "y": 6.1430}, "icon": "bus"}]}
calls = []
def handle(route):
    u = route.request.url; calls.append(u)
    if "/stationboard" in u: body = board
    elif "Gen%C3%A8ve" in u: body = locs_gva
    else: body = locs_belair
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body),
                  headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="light")
    ctx.route("https://transport.opendata.ch/**", handle)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: m.type == "error" and errors.append(m.text))
    pg.goto(PAGE)
    pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
    res = pg.locator("#results button").all_inner_texts()
    print("results:", res)
    assert not any("Lausanne" in r for r in res), "out-of-zone stop shown"
    pg.locator("#results button[data-id='8587057']").click()
    pg.wait_for_selector(".dep")
    chips = pg.locator(".line-chip").all_inner_texts(); print("chips:", chips)
    rows = pg.locator(".dep").all_inner_texts(); print("rows:", len(rows)); print(rows[:4])
    pg.screenshot(path=str(OUT / "board.png"), full_page=True)
    # deselect tram 12
    pg.locator(".line-chip[data-key='tram|12']").click()
    rows2 = pg.locator(".dep .badge").all_inner_texts(); print("after hide 12:", rows2)
    assert "12" not in rows2
    # persistence after reload (auto-reopen last stop)
    pg.reload(); pg.wait_for_selector(".dep")
    assert pg.locator(".line-chip[data-key='tram|12']").get_attribute("aria-pressed") == "false"
    print("recent:", pg.locator("#recent").inner_text())
    pg.click("#noLines"); print("none:", pg.locator("#departures").inner_text())
    pg.click("#allLines"); print("all count:", pg.locator(".dep").count())
    pg.locator(".line-chip[data-key='tram|12']").click()
    pg.screenshot(path=str(OUT / "board_filtered.png"), full_page=True)
    dark = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark")
    dark.route("https://transport.opendata.ch/**", handle)
    d = dark.new_page(); d.goto(PAGE); d.fill("#q", "Bel"); d.wait_for_selector("#results button[data-id]")
    d.locator("#results button[data-id='8587057']").click(); d.wait_for_selector(".dep")
    d.screenshot(path=str(OUT / "board_dark.png"), full_page=True)
    b.close()
print("errors:", errors); print("calls:", len(calls))
