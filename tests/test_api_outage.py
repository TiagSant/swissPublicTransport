"""transport.opendata.ch outages: every API call times out after 10 s, says why it failed, and a banner
explains the problem until a call succeeds again (Sprint 6 prototype)."""
import os, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-06-journeys/index.html").as_uri()
STOP = {"id": "8587387", "name": "Genève, Bel-Air", "coordinate": {"x": 46.2047, "y": 6.143}, "icon": "tram"}
state = {"mode": "ok"}
pending = []
CORS = {"Access-Control-Allow-Origin": "*"}

def api(route):
    m = state["mode"]
    if m == "network": return route.abort("failed")
    if m == "server": return route.fulfill(status=503, headers=CORS, content_type="application/json",
                                           body=json.dumps({"errors": [{"message": "The router is not reachable"}]}))
    if m == "rate": return route.fulfill(status=429, headers=CORS, body="Too Many Requests")
    if m == "hang": pending.append(route); return          # never answers
    route.fulfill(status=200, headers=CORS, content_type="application/json", body=json.dumps({"stations": [STOP]}))

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(locale="en-US"); ctx.route("https://transport.opendata.ch/**", api)
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install()
    pg.goto(PAGE)
    banner = pg.locator("#apiStatus")

    def search(q):
        pg.fill("#q", ""); pg.fill("#q", q); pg.clock.run_for(400)

    for mode, words in [("network", "cannot be reached"), ("server", "internal error"), ("rate", "Too many requests")]:
        state["mode"] = mode; search("Bel-Air")
        pg.wait_for_function("!document.getElementById('apiStatus').hidden")
        assert words in banner.inner_text(), (mode, banner.inner_text())
        assert "Search failed" in pg.locator("#results").inner_text()
        print(f"{mode:8} → {banner.inner_text()[:70]}…")
        state["mode"] = "ok"; search("Bel-Air")                      # service back: banner disappears
        pg.wait_for_function("document.getElementById('apiStatus').hidden")
        assert "Genève, Bel-Air" in pg.locator("#results").inner_text()

    # No answer at all: the call gives up after 10 s instead of waiting forever
    state["mode"] = "hang"; search("Bel-Air")
    assert banner.is_hidden()
    pg.clock.run_for(9000); assert banner.is_hidden()
    pg.clock.run_for(1500)
    pg.wait_for_function("!document.getElementById('apiStatus').hidden")
    assert "not responding" in banner.inner_text()
    print("timeout  →", banner.inner_text()[:70], "…")

    # French
    pg.click("#lang"); assert "ne répond pas" in banner.inner_text()
    print("FR       →", banner.inner_text()[:60], "…")
    for r in pending:                                   # release the requests left hanging on purpose
        try: r.abort()
        except Exception: pass
    b.close()
print("errors:", errors); assert not errors
