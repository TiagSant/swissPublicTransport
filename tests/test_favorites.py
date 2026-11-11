"""US-20: remove a single stop from "Your stops", or all of them, with undo (Sprint 6 prototype)."""
import os, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-06-journeys/index.html").as_uri()
STOPS = {
    "8587387": {"id": "8587387", "name": "Genève, Bel-Air", "mode": "tram", "count": 9, "last": 3},
    "8587418": {"id": "8587418", "name": "Petit-Lancy, Les Esserts", "mode": "tram", "count": 5, "last": 2},
    "8587057": {"id": "8587057", "name": "Genève, gare Cornavin", "mode": "train", "count": 2, "last": 1},
}
def api(route):
    route.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"},
                  body=json.dumps({"station": {"id": "8587387", "name": "Genève, Bel-Air"}, "stationboard": []}))
errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(locale="en-US", viewport={"width": 390, "height": 844}, device_scale_factor=2)
    ctx.route("https://transport.opendata.ch/**", api)
    ctx.add_init_script(f"""if (!sessionStorage.getItem('seeded')) {{ sessionStorage.setItem('seeded', '1');
        localStorage.setItem('tpp:stops', {json.dumps(json.dumps(STOPS))}); localStorage.setItem('tpp:lastStop', '"8587418"'); }}""")
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(PAGE)
    names = lambda: [e.inner_text().rsplit("\n", 1)[0].rstrip("0123456789×").strip() for e in pg.locator("#recent .stop-open").all()]
    stored = lambda: sorted(json.loads(pg.evaluate("localStorage.getItem('tpp:stops')")).keys())
    assert names() == ["Genève, Bel-Air", "Petit-Lancy, Les Esserts", "Genève, gare Cornavin"], names()
    assert pg.locator("#clearRecent").inner_text() == "Clear all"

    # 1. Remove one stop: the others stay; tapping ✕ does not open the stop
    pg.locator("[data-del='8587057']").click()
    assert names() == ["Genève, Bel-Air", "Petit-Lancy, Les Esserts"] and stored() == ["8587387", "8587418"]
    assert pg.locator("#toastText").inner_text() == "Genève, gare Cornavin removed from your stops."
    assert pg.locator("#board").is_visible()                      # the open board stays as it is
    print("1 one stop removed")

    # 2. Undo brings it back with its visit count
    pg.click("#toastUndo")
    assert names()[-1] == "Genève, gare Cornavin" and pg.locator("#toast").is_hidden()
    print("2 undo OK")

    # 3. Removing the last viewed stop: it no longer reopens at start-up
    pg.locator("[data-del='8587418']").click()
    assert json.loads(pg.evaluate("localStorage.getItem('tpp:lastStop')")) is None
    pg.screenshot(path=str(ROOT / "tests/out/favorites_removed.png"))
    pg.reload(); pg.wait_for_timeout(300)
    assert pg.locator("#board").is_hidden() and names() == ["Genève, Bel-Air", "Genève, gare Cornavin"]
    print("3 last stop removed → not reopened")

    # 4. Clear all, then undo, then clear all for good (toast expires)
    pg.click("#clearRecent")
    assert pg.locator("#recentCard").is_hidden() and pg.locator("#toastText").inner_text() == "Your stops were cleared."
    pg.click("#toastUndo"); assert len(names()) == 2
    pg.click("#clearRecent"); pg.wait_for_timeout(6300)
    assert pg.locator("#toast").is_hidden() and stored() == []
    print("4 clear all + undo + expiry OK")

    # 5. French labels
    pg.evaluate(f"localStorage.setItem('tpp:stops', {json.dumps(json.dumps(STOPS))})"); pg.reload()
    pg.click("#lang")
    assert pg.locator("#clearRecent").inner_text() == "Tout effacer"
    assert pg.locator("[data-del='8587387']").get_attribute("aria-label") == "Retirer Genève, Bel-Air de vos arrêts"
    print("5 FR OK")
    b.close()
print("errors:", errors); assert not errors
