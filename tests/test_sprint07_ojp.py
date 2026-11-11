"""Sprint 7: official data from opentransportdata.swiss (OJP 2.0, TECH-05) with the rider's key entered in
Settings (TECH-06). The OJP service is replaced by real answers recorded for Geneva (tests/fixtures/ojp-sprint07);
the browser clock is set to when they were recorded."""
import os, re, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-07-official-data/index.html").as_uri()
FX = ROOT / "tests" / "fixtures" / "ojp-sprint07"   # frozen copy: the probe refreshes tests/fixtures/ojp
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
NOW = "2026-11-11T19:05:30Z"            # the probe recorded the departures at 19:05 UTC
GOOD, BAD = "test-key-0123456789abcdef", "wrong-key"
CORS = {"Access-Control-Allow-Origin": "*"}

ojp_calls, community_calls = [], []
state = {"refuse": False}

def fixture_for(body):
    """Pick the recorded answer matching the request the app sent."""
    if "OJPLocationInformationRequest" in body:
        return "app_lir_zone_esserts" if "<Rectangle>" in body else "lir_name_belair"
    if "OJPStopEventRequest" in body:
        stop = re.search(r"<siri:StopPointRef>(\d+)<", body).group(1)
        light = "<IncludeOnwardCalls>false" in body
        return {("8587387", False): "ser_belair", ("8587387", True): "app_ser_belair_light",
                ("8587418", False): "app_ser_esserts_full", ("8587418", True): "app_ser_esserts_light",
                ("8501008", False): "ser_geneve_gare", ("8501008", True): "ser_geneve_gare"}[(stop, light)]
    if "OJPTripRequest" in body:
        return "app_tr_arrive" if re.search(r"<Destination>.*<DepArrTime>", body, re.S) else "app_tr_depart"
    raise AssertionError("unexpected OJP request")

def ojp(route):
    req = route.request
    if req.method == "OPTIONS":
        return route.fulfill(status=204, headers=dict(CORS, **{"Access-Control-Allow-Headers": "authorization,content-type"}))
    body = req.post_data or ""
    auth = req.headers.get("authorization", "")
    ojp_calls.append({"body": body, "auth": auth, "url": req.url})
    if state["refuse"] or auth != f"Bearer {GOOD}":
        return route.fulfill(status=401, headers=CORS, body='{"statusCode": 401, "message": "Access denied"}')
    route.fulfill(status=200, headers=CORS, content_type="application/xml", body=(FX / f"{fixture_for(body)}.xml").read_text())

def community(route):
    community_calls.append(route.request.url)
    body = {"stations": [], "stationboard": [], "connections": []}
    route.fulfill(status=200, headers=CORS, content_type="application/json", body=json.dumps(body))

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(locale="en-US", viewport={"width": 420, "height": 900})
    ctx.route("https://api.opentransportdata.swiss/**", ojp)
    ctx.route("https://transport.opendata.ch/**", community)
    ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW)
    pg.goto(PAGE)
    ls = lambda k: pg.evaluate(f"localStorage.getItem('tpp:{k}')")

    # 1. Without a key: community source, nothing sent to OJP
    pg.click("#settingsBtn")
    assert "transport.opendata.ch" in pg.inner_text("#srcBadge")
    assert pg.is_hidden("#ojpKeyRemove")

    # 2. A refused key is not saved
    pg.fill("#setOjpKey", BAD); pg.click("#ojpKeySave")
    pg.wait_for_function("document.getElementById('ojpKeyStatus').textContent.includes('refused')")
    assert "401" in pg.inner_text("#ojpKeyStatus") and ls("ojpKey") is None
    assert pg.is_hidden("#apiStatus"), "a key test must not leave the outage banner"
    print("refused key →", pg.inner_text("#ojpKeyStatus"))

    # 3. A good key ("Bearer " pasted by mistake is removed) is checked, saved on the device, then masked
    pg.fill("#setOjpKey", f"  Bearer {GOOD} "); pg.click("#ojpKeySave")
    pg.wait_for_function("document.getElementById('ojpKeyStatus').textContent.includes('works')")
    assert json.loads(ls("ojpKey")) == GOOD
    assert pg.input_value("#setOjpKey") == "" and pg.get_attribute("#setOjpKey", "placeholder").endswith("cdef")
    assert "opentransportdata.swiss" in pg.inner_text("#srcBadge") and pg.is_visible("#ojpKeyRemove")
    assert pg.inner_text("#srcLink") == "opentransportdata.swiss"
    pg.screenshot(path=str(OUT / "sprint07-settings.png"))
    print("good key    →", pg.inner_text("#ojpKeyStatus"))
    pg.click("#settingsClose")

    # 4. Stop search through OJP: Switzerland-wide answer, only the Unireso area kept
    n0 = len(ojp_calls)
    pg.fill("#q", "Bel-Air"); pg.clock.run_for(400)
    pg.wait_for_function("document.getElementById('results').innerText.includes('Genève, Bel-Air')")
    res = pg.inner_text("#results")
    assert "Marly" not in res and "Lausanne" not in res, res
    assert all("OJPLocationInformationRequest" in c["body"] for c in ojp_calls[n0:])
    print("search      →", res.replace("\n", " | ")[:80])

    # 5. Departures: one request with the next stops (directions) + one light request, real time, platforms
    n0 = len(ojp_calls)
    pg.locator("#results button", has_text="Genève, Bel-Air").first.click()
    pg.wait_for_selector("#departures li.dep")
    first = ojp_calls[n0:]
    assert len(first) == 2, len(first)
    assert sum("<IncludeOnwardCalls>true" in c["body"] for c in first) == 1
    assert sum("<IncludeOnwardCalls>false" in c["body"] for c in first) == 1
    assert all("<IncludePreviousCalls>false" in c["body"] for c in first)
    deps = pg.locator("#departures li.dep")
    text = pg.inner_text("#departures")
    assert re.search(r"\+\d+ min", text), "live delays shown"
    assert pg.locator("#departures button.plat").count() > 0, "platform letters shown"
    tram17 = pg.locator("#departures li.dep", has_text="Annemasse").first
    assert "background" in (tram17.locator(".badge").get_attribute("style") or ""), "TPG line colour"
    print(f"departures  → {deps.count()} shown, e.g.", tram17.inner_text().replace("\n", " ")[:70])

    # Directions are known from the next stops, even for the light answer
    pg.click("#dirToggle")
    dirs = pg.inner_text("#dirs")
    assert "Molard" in dirs, dirs[:300]
    pg.click("#dirToggle")
    pg.screenshot(path=str(OUT / "sprint07-board.png"), full_page=True)

    # Next stops of a departure, rebuilt from its remembered run pattern (runs not yet learned say so)
    found = None
    for i in range(min(deps.count(), 25)):
        row = pg.locator("#departures li.dep").nth(i)
        row.locator(".to").click()
        exp = pg.inner_text("#departures li.dep[aria-expanded=true]")
        if "not available" not in exp and len(exp.split("\n")) > 6: found = exp; break
    assert found, "no departure with next stops"
    print("next stops  →", " · ".join(found.split("\n")[5:9]))

    # 6. Refresh after 30 s: only the light request
    n0 = len(ojp_calls)
    pg.clock.run_for(31000)
    pg.wait_for_timeout(500)
    refresh = ojp_calls[n0:]
    assert refresh and all("<IncludeOnwardCalls>false" in c["body"] for c in refresh), len(refresh)
    patterns = json.loads(ls("patterns:8587387"))
    assert patterns["fullAt"] and len(patterns["map"]) >= 5
    print(f"refresh     → {len(refresh)} light request(s), {len(patterns['map'])} run patterns remembered")

    # Runs whose next stops are unknown: the stops are asked again, but not before 5 minutes
    n0 = len(ojp_calls)
    pg.clock.run_for(5 * 60000); pg.wait_for_timeout(500)
    assert any("<IncludeOnwardCalls>true" in c["body"] for c in ojp_calls[n0:]), "patterns asked again after 5 min"
    assert sum("<IncludeOnwardCalls>true" in c["body"] for c in ojp_calls[n0:]) == 1

    # 7. Train station: SBB timetable icons (IR 95, IC 1), Léman Express colour for L4
    pg.evaluate("""() => { const s = JSON.parse(localStorage.getItem('tpp:stops') || '{}');
      s['8501008'] = { id: '8501008', name: 'Genève', mode: 'train', count: 1, last: Date.now() };
      localStorage.setItem('tpp:stops', JSON.stringify(s)); localStorage.setItem('tpp:lastStop', '"8501008"'); }""")
    pg.reload(); pg.wait_for_selector("#departures li.dep")
    assert pg.locator("#departures img[src*='ir-95']").count() > 0, "IR 95 icon"
    assert pg.locator("#departures img[src*='ic-1']").count() > 0, "IC 1 icon"
    l4 = pg.locator("#departures .badge", has_text=re.compile(r"^L4$")).first
    assert "background" in (l4.get_attribute("style") or ""), "Léman Express colour"
    print("station     → IR 95 and IC 1 icons, L4 colour OK")

    # 8. Journeys through OJP (Les Esserts → Cornavin), leaving now and arriving by a time
    pg.evaluate("""() => {
      localStorage.setItem('tpp:journey:from', JSON.stringify({ kind: 'stop', id: '8587418', name: 'Petit-Lancy, Les Esserts', coord: [46.1881, 6.1131] }));
      localStorage.setItem('tpp:journey:to', JSON.stringify({ kind: 'stop', id: '8587057', name: 'Genève, gare Cornavin', coord: [46.2097, 6.1424] }));
      localStorage.setItem('tpp:tab', '"journey"'); }""")
    pg.reload()
    n0 = len(ojp_calls)
    pg.click("#searchJourney")
    pg.wait_for_selector("#journeyList .jr", timeout=10000)
    jtext = pg.inner_text("#journeyList")
    trips = [c for c in ojp_calls[n0:] if "OJPTripRequest" in c["body"]]
    assert len(trips) == 1 and "<StopPlaceRef>8587418<" in trips[0]["body"] and "<StopPlaceRef>8587057<" in trips[0]["body"]
    assert re.search(r"\b(22|14|6)\b", jtext), jtext[:300]
    print("journeys    →", jtext.replace("\n", " ")[:90])
    pg.screenshot(path=str(OUT / "sprint07-journeys.png"), full_page=True)

    # 9. The key goes only to OJP, in the Authorization header, never in a URL; no community calls meanwhile
    assert all(c["url"].startswith("https://api.opentransportdata.swiss/ojp20") for c in ojp_calls)
    assert not any(GOOD in c["url"] for c in ojp_calls) and not any(GOOD in u for u in community_calls)
    assert not community_calls, community_calls

    # 10. Key refused later (expired): clear banner, in both languages
    state["refuse"] = True
    pg.evaluate("localStorage.setItem('tpp:tab', '\"departures\"')"); pg.reload()
    pg.wait_for_function("!document.getElementById('apiStatus').hidden")
    assert "key was refused" in pg.inner_text("#apiStatus"), pg.inner_text("#apiStatus")
    pg.click("#lang"); assert "clé opentransportdata.swiss a été refusée" in pg.inner_text("#apiStatus")
    pg.click("#lang")
    print("expired key →", pg.inner_text("#apiStatus")[:70], "…")

    # 11. Remove the key: back to transport.opendata.ch, banner gone
    state["refuse"] = False
    pg.click("#settingsBtn"); pg.click("#ojpKeyRemove")
    assert ls("ojpKey") is None and "transport.opendata.ch" in pg.inner_text("#srcBadge")
    pg.wait_for_function("document.getElementById('apiStatus').hidden")
    pg.wait_for_timeout(300)
    assert any("/stationboard" in u for u in community_calls), community_calls
    assert all("authorization" not in u.lower() for u in community_calls)
    print("key removed →", pg.inner_text("#ojpKeyStatus"))
    b.close()

print("errors:", errors); assert not errors
print("OK")
