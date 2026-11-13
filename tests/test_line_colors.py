"""US-42: colours and pictograms of the lines of every Swiss operator, PostAuto included, and the metro (Lausanne m1, m2).

Checks the generated table (assets/line-colors-ch.js), the departures board of the current prototype with a mocked
transport.opendata.ch, and the check page tools/line-colors.html.
"""
import os, json, re, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
TOOL = (ROOT / "tools/line-colors.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)

# ---- the generated table
src = (ROOT / "assets/line-colors-ch.js").read_text(encoding="utf-8")
assert "OpenStreetMap contributors" in src and "ODbL" in src, "attribution missing"
CH = json.loads(re.search(r"window\.LINE_COLORS_CH = (\{.*\});", src, re.S).group(1))
ops = CH["operators"]
assert len(ops) >= 50, len(ops)
for abbr in ("TL", "TPG", "PAG", "VBZ", "BVB", "BERNMOBIL", "TPF", "TPL"):
    assert ops.get(abbr, {}).get("lines"), f"{abbr}: no lines"
assert CH["numbers"].get("151") == "TL" and CH["numbers"].get("801") == "PAG" and CH["numbers"].get("881") == "TPG", CH["numbers"]
assert "m1" in ops["TL"]["lines"] and "m2" in ops["TL"]["lines"]
def lum(h):
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b_ = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b_)
low = []
for abbr, o in ops.items():
    assert abbr == abbr.upper(), abbr
    for ref, (bg, fg, shape) in o["lines"].items():
        assert re.fullmatch(r"#[0-9A-F]{6}", bg) and re.fullmatch(r"#[0-9A-F]{6}", fg) and shape == "pill", (abbr, ref, bg, fg)
        hi, lo = sorted((lum(bg), lum(fg)), reverse=True)
        if (hi + 0.05) / (lo + 0.05) < 3: low.append((abbr, ref, bg, fg))
        assert ref == ref.lower(), (abbr, ref)
assert len(low) <= 5, low   # text colours given in OSM, a few may be weak
print(f"table       → {len(ops)} operators, {sum(len(o['lines']) for o in ops.values())} lines; numbers 151→TL 801→PAG 881→TPG")

# ---- the departures board
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
HERE = {"id": "8587057", "name": "Genève, Bel-Air"}   # the search keeps the Geneva area until US-25; the board itself is mocked
free_pag = next(str(n) for n in range(990, 900, -1) if str(n) not in ops["PAG"]["lines"])
some_tl_bus = next(r for r in ops["TL"]["lines"] if r.isdigit())
some_vbz = next(r for r in ops["VBZ"]["lines"] if r.isdigit())
ROWS = [  # (category, number, operator, expected label, expected colours or a marker)
    ("M", "1", "TL", "m1", ops["TL"]["lines"]["m1"]),
    ("M", "M2", "TL", "m2", ops["TL"]["lines"]["m2"]),
    ("B", some_tl_bus, "TL", some_tl_bus, ops["TL"]["lines"][some_tl_bus]),
    ("T", some_vbz, "VBZ", some_vbz, ops["VBZ"]["lines"][some_vbz]),
    ("B", free_pag, "PAG", free_pag, ["#FFCC00", "#000000"]),          # PostAuto yellow by default
    ("B", "77", "XYZ", "77", "neutral"),                              # unknown operator
]
def dep(i, cat, num, op):
    t = now + dt.timedelta(minutes=2 + i)
    return {"category": cat, "number": num, "to": f"Terminus {i}", "operator": op,
            "passList": [{"station": HERE}, {"station": {"id": f"85{i:05d}", "name": f"Next {i}"}}],
            "stop": {"station": HERE, "departure": fmt(t), "departureTimestamp": int(t.timestamp()), "delay": 0,
                     "prognosis": {"departure": fmt(t)}}}
def handle(route):
    url = route.request.url
    if "/stationboard" in url:
        body = {"station": HERE, "stationboard": [dep(i, *r[:3]) for i, r in enumerate(ROWS)]}
    else:
        body = {"stations": [{"id": HERE["id"], "name": HERE["name"], "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def rgb(hex_):
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5)); return f"rgb({r}, {g}, {b})"

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(locale="fr-CH", viewport={"width": 390, "height": 844}); ctx.route("https://transport.opendata.ch/**", handle)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e))); pg.goto(PAGE)
    pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
    pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")
    pg.wait_for_timeout(300)
    deps = pg.locator(".dep")
    assert deps.count() == len(ROWS), deps.count()
    seen = {}
    for i in range(deps.count()):
        badge = deps.nth(i).locator(".badge").first
        seen[badge.text_content().strip()] = (badge.get_attribute("class"), badge.evaluate("e => [getComputedStyle(e).backgroundColor, getComputedStyle(e).color]"),
                                               deps.nth(i).locator("img.picto").first.get_attribute("src") if deps.nth(i).locator("img.picto").count() else None)
    for cat, num, op, label, want in ROWS:
        cls, (bg, fg), picto = seen[label]
        if want == "neutral":
            assert "neutral" in cls, (label, cls)
        else:
            assert (bg, fg) == (rgb(want[0]), rgb(want[1])), (label, bg, fg, want)
        if cat == "M":
            assert picto and picto.endswith("/sbb/pictograms/Metro_r_fr.svg"), (label, picto)
    assert pg.evaluate("document.querySelector('img.picto[src$=\"Metro_r_fr.svg\"]').naturalWidth") > 0, "metro pictogram not loaded"
    pg.screenshot(path=str(OUT / "line-colors-board.png"))
    print(f"board       → m1 m2 metro pictogram + tl colours; tl {some_tl_bus}, VBZ {some_vbz} coloured; PostAuto {free_pag} yellow; unknown neutral")

    # ---- the check page
    pg2 = ctx.new_page(); pg2.on("pageerror", lambda e: errors.append(str(e))); pg2.goto(TOOL)
    assert re.search(r"\d+ operators · \d+ lines", pg2.text_content("#meta")), pg2.text_content("#meta")
    m = pg2.locator("#metro .badge")
    assert [m.nth(0).text_content(), m.nth(1).text_content()] == ["m1", "m2"]
    assert m.nth(0).evaluate("e => getComputedStyle(e).backgroundColor") == rgb(ops["TL"]["lines"]["m1"][0])
    assert pg2.evaluate("document.querySelector('#metro img').naturalWidth") > 0
    n_all = pg2.locator("#list section").count()
    pg2.fill("#q", "postauto"); assert pg2.locator("#list section").count() >= 1 and pg2.locator("#list h2").first.text_content().startswith("PA")
    pg2.fill("#q", "tl"); assert "TL" in [h.split(" ")[0] for h in pg2.locator("#list h2").all_text_contents()]
    pg2.fill("#q", ""); assert pg2.locator("#list section").count() == n_all == len(ops)
    pg2.screenshot(path=str(OUT / "line-colors-tool.png"), full_page=False)
    print(f"check page  → {n_all} operators, metro m1/m2, search")
    b.close()

print("errors:", errors); assert not errors
print("OK")
