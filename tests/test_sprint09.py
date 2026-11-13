"""Sprint 9: my places (US-21, US-22), address search (US-23), next stop after removing the one on screen (US-27),
alarms that adapt when set late (US-33). transport.opendata.ch is replaced by mocks; OJP address answers by
frozen real ones. The browser clock is frozen."""
import os, json, re, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes/sprint-09-my-places/index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
FX = ROOT / "tests" / "fixtures" / "ojp-sprint09"
LEAFLET_DIR, TILE = os.environ.get("LEAFLET_DIR"), os.environ.get("TILE_PNG")
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 12, 7, 30, tzinfo=tz)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
at = lambda m: NOW + dt.timedelta(minutes=m)

def st(id_, name, x, y): return {"id": id_, "name": name, "coordinate": {"type": "WGS84", "x": x, "y": y}}
ESSERTS = st("8587418", "Petit-Lancy, Les Esserts", 46.188100, 6.113100)
COMMUNES = st("8592887", "Lancy, Communes-Réunies", 46.174500, 6.121900)
CORNAVIN = st("8587057", "Genève, gare Cornavin", 46.209733, 6.142437)
BELAIR = st("8587387", "Genève, Bel-Air", 46.204728, 6.143048)
ADDRESS = {"id": None, "name": "Lancy, Avenue des Communes-Réunies 60", "coordinate": {"type": "WGS84", "x": 46.17391, "y": 6.12128}}
HOME_AT = (46.17391, 6.12128)

def end(s, m, kind, plat=""):
    return {"station": s, kind: fmt(at(m)), kind + "Timestamp": int(at(m).timestamp()), "platform": plat, "prognosis": {}, "delay": None}
def ride(a, b, ma, mb, cat="T", num="15"):
    return {"journey": {"category": cat, "number": num, "to": b["name"], "operator": "TPG",
                        "passList": [{"station": a, "departure": fmt(at(ma))}, {"station": BELAIR, "arrival": fmt(at(ma + 10)), "departure": fmt(at(ma + 10))},
                                     {"station": b, "arrival": fmt(at(mb))}]},
            "walk": None, "departure": end(a, ma, "departure", "A"), "arrival": end(b, mb, "arrival")}

calls = []
def api(route):
    u = urlparse(route.request.url); q = parse_qs(u.query); calls.append(route.request.url)
    if u.path.endswith("/locations"):
        if "x" in q:
            x, y = float(q["x"][0]), float(q["y"][0])
            near = [s for s in (COMMUNES, ESSERTS, CORNAVIN, BELAIR) if abs(s["coordinate"]["x"] - x) < 0.01 and abs(s["coordinate"]["y"] - y) < 0.01]
            body = {"stations": near}
        else:
            name = q["query"][0].lower()
            pool = [ADDRESS, COMMUNES, ESSERTS, CORNAVIN, BELAIR]
            body = {"stations": [dict(s, icon="tram") if s["id"] else s for s in pool
                                 if any(w in s["name"].lower() for w in name.replace("genève ", "").split() if len(w) > 3)]}
    elif u.path.endswith("/connections"):
        a, b = q["from"][0], q["to"][0]
        stops = {s["id"]: s for s in (COMMUNES, ESSERTS, CORNAVIN, BELAIR)}
        # the tram leaves 16 min after the asked time (07:46 when asked at 07:30)
        asked = dt.datetime.strptime(q["date"][0] + " " + q["time"][0], "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        off = (asked - NOW).total_seconds() / 60
        body = {"connections": [{"sections": [ride(stops[a], stops[b], off + 16, off + 34)]}]} if a in stops and b in stops else {"connections": []}
    else:
        body = {"station": BELAIR, "stationboard": []}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

def new_page(b, when):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, locale="en-US", timezone_id="Europe/Zurich",
                        geolocation={"latitude": HOME_AT[0], "longitude": HOME_AT[1], "accuracy": 10}, permissions=["geolocation"])
    ctx.route("https://transport.opendata.ch/**", api)
    if LEAFLET_DIR: ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.fulfill(path=str(Path(LEAFLET_DIR) / r.request.url.rsplit("/", 1)[-1])))
    if TILE: ctx.route("https://tile.openstreetmap.org/**", lambda r: r.fulfill(path=TILE, content_type="image/png"))
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=when.timestamp())
    pg.goto(PAGE)
    return pg

def chips(pg): return [c.strip() for c in pg.locator("#placeChips .place-open").all_inner_texts()]
def typing(pg, sel, text):
    pg.fill(sel, text); pg.clock.run_for(400)

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    pg = new_page(b, NOW)
    pg.evaluate("localStorage.setItem('tpp:tab', '\"journey\"')"); pg.reload()

    # Empty: a hint, no chips
    assert pg.is_visible("#placesHint") and chips(pg) == [] and pg.is_hidden("#clearPlaces")

    # US-21 + US-23: Home from an address search
    pg.click("#addPlace")
    assert pg.get_attribute("#placeKind button[data-kind=home]", "aria-pressed") == "true" and pg.input_value("#placeName") == "Home"
    typing(pg, "#placeQ", "Communes-Réunies 60")
    pg.wait_for_selector("#placeResults button[data-addr]")
    row = pg.locator("#placeResults li").first.inner_text()
    assert "Address" in row and "Avenue des Communes-Réunies 60" in row, row
    pg.click("#placeResults button[data-addr]")
    assert "Avenue des Communes-Réunies 60" in pg.inner_text("#placeChosenText")
    pg.click("#placeSave")
    assert chips(pg) == ["🏠 Home"], chips(pg)
    print("home        →", chips(pg))

    # Work from the To field (☆ next to a stop)
    typing(pg, "#toQ", "Cornavin")
    pg.wait_for_selector("#toResults button[data-id]")
    pg.click("#toResults button[data-id]")
    assert pg.is_visible(".place-save[data-which=to]") and pg.is_hidden(".place-save[data-which=from]")
    pg.click(".place-save[data-which=to]")
    assert pg.input_value("#placeName") == "Genève, gare Cornavin" and pg.get_attribute("#placeKind button[data-kind=other]", "aria-pressed") == "true"
    pg.click("#placeKind button[data-kind=work]")
    assert pg.input_value("#placeName") == "Work"
    pg.click("#placeSave")
    assert pg.is_hidden(".place-save[data-which=to]") is False   # the field still holds the stop, not the saved place

    # Another place, from the map, with my own name
    pg.click("#addPlace")
    assert pg.get_attribute("#placeKind button[data-kind=other]", "aria-pressed") == "true"
    pg.fill("#placeName", "Gym")
    pg.click("#placeSave"); assert "Choose where" in pg.inner_text("#placeMsg")
    pg.clock.resume()
    pg.click("#placeMap"); pg.wait_for_selector("#mapSheet:not([hidden]) .leaflet-container")
    pg.locator("#map").click(position={"x": 200, "y": 250})
    pg.wait_for_selector("#pickConfirm:not([hidden])"); pg.click("#pickConfirm")
    assert pg.is_visible("#placeSheet") and pg.is_visible("#placeChosen")
    pg.click("#placeSave")
    pg.clock.install(time=NOW.timestamp() + 60)
    assert chips(pg) == ["🏠 Home", "💼 Work", "📍 Gym"], chips(pg)

    # A second Home asks for confirmation, then replaces the first one
    pg.click("#addPlace"); pg.click("#placeKind button[data-kind=home]")
    pg.click("#placeMe"); pg.wait_for_selector("#placeChosen:not([hidden])")
    pg.click("#placeSave")
    assert "replaces your current Home" in pg.inner_text("#placeMsg"), pg.inner_text("#placeMsg")
    pg.click("#placeSave")
    assert chips(pg).count("🏠 Home") == 1 and len(chips(pg)) == 3, chips(pg)
    print("places      →", chips(pg))

    # US-22: one tap fills From (To already set) and searches; use is counted
    pg.fill("#fromQ", ""); pg.evaluate("localStorage.removeItem('tpp:journey:from')")
    pg.reload()
    typing(pg, "#toQ", "Cornavin"); pg.wait_for_selector("#toResults button[data-id]"); pg.click("#toResults button[data-id]")
    pg.fill("#fromQ", ""); pg.dispatch_event("#fromQ", "input")
    pg.locator("#placeChips .place-open", has_text="Gym").click()
    assert pg.input_value("#fromQ") == "📍 Gym", pg.input_value("#fromQ")
    pg.wait_for_selector("#journeyList .jr")
    print("one tap     →", pg.input_value("#fromQ"), "→", pg.input_value("#toQ"), "|", pg.locator("#journeyList .jr").first.inner_text().split("\n")[0])
    # both set: a tap replaces To and searches again
    pg.locator("#placeChips .place-open", has_text="Home").click()
    assert pg.input_value("#toQ") == "🏠 Home"
    # Gym used again later (> 10 min): used most, but Home and Work stay first once used
    pg.clock.run_for(11 * 60000)
    pg.click("#swap"); pg.locator("#placeChips .place-open", has_text="Gym").click()   # To = Gym
    pg.clock.run_for(11 * 60000)
    pg.click("#searchJourney")
    pg.locator("#placeChips .place-open", has_text="Work").click()
    assert chips(pg) == ["🏠 Home", "💼 Work", "📍 Gym"], chips(pg)
    usage = json.loads(pg.evaluate("localStorage.getItem('tpp:places')"))
    gym = [v for v in usage.values() if v["name"] == "Gym"][0]
    assert gym["usage"]["s"] > 2, gym["usage"]

    # Suggested while typing, before stops and addresses
    typing(pg, "#toQ", "gy")
    pg.wait_for_selector("#toResults li")
    first = pg.locator("#toResults li").first
    assert first.locator("button[data-pid]").count() == 1 and "Gym" in first.inner_text()
    first.locator("button").click()
    assert pg.input_value("#toQ") == "📍 Gym"
    typing(pg, "#toQ", "work"); pg.wait_for_selector("#toResults button[data-pid]")
    assert "Work" in pg.locator("#toResults li").first.inner_text()
    pg.keyboard.press("Escape"); pg.fill("#toQ", ""); pg.dispatch_event("#toQ", "input")

    # Rename, remove with undo, clear all with undo
    pg.locator("#placeChips .place-chip", has_text="Gym").locator(".place-edit").click()
    assert pg.inner_text("#placeTitle") == "Edit place" and pg.input_value("#placeName") == "Gym"
    pg.fill("#placeName", "Fitness"); pg.click("#placeSave")
    assert "📍 Fitness" in chips(pg)
    pg.locator("#placeChips .place-chip", has_text="Fitness").locator(".stop-del").click()
    assert "Fitness removed" in pg.inner_text("#toast") and "📍 Fitness" not in chips(pg)
    pg.click("#toastUndo"); assert "📍 Fitness" in chips(pg)
    pg.click("#clearPlaces"); assert chips(pg) == [] and pg.is_visible("#placesHint")
    pg.click("#toastUndo"); assert len(chips(pg)) == 3
    # French
    pg.select_option("#lang", "fr"); assert chips(pg)[:2] == ["🏠 Domicile", "💼 Travail"], chips(pg); pg.select_option("#lang", "en")
    pg.screenshot(path=str(OUT / "sprint09-places.png"), full_page=True)

    # A saved place is a starting point like a point on the map: walk shown with its name
    pg.locator("#placeChips .place-open", has_text="Home").click()   # To = Home
    pg.fill("#fromQ", ""); pg.dispatch_event("#fromQ", "input")
    pg.locator("#placeChips .place-open", has_text="Work").click()   # From = Work, both set → search
    pg.wait_for_selector("#journeyList .jr")
    pg.locator("#journeyList .jr").first.click()
    meta = pg.inner_text("#journeyList .jr-detail .jr-meta")
    assert meta == "💼 Work → 🏠 Home", meta
    # time on board next to the number of stops; arrival written like the departure
    ride_leg = pg.locator("#journeyList .jr-detail .leg.ride").first
    assert ride_leg.locator(".via-toggle").inner_text().startswith("2 stops · 18 min"), ride_leg.locator(".via-toggle").inner_text()
    style = "e => [getComputedStyle(e).color, getComputedStyle(e).fontSize, getComputedStyle(e).fontWeight]"
    stops_lines = ride_leg.locator(".leg-stop")
    assert stops_lines.count() == 2 and stops_lines.first.evaluate(style) == stops_lines.last.evaluate(style), [stops_lines.first.evaluate(style), stops_lines.last.evaluate(style)]
    print("ride        →", ride_leg.inner_text().replace("\n", " | "))
    assert "to Home" in pg.inner_text("#journeyList .jr-detail .leg.walk >> nth=-1") or "destination" in pg.inner_text("#journeyList .jr-detail")

    # ---------- US-27: removing the stop on screen
    pg.evaluate("""() => {
      const now = Date.now();
      localStorage.setItem('tpp:stops', JSON.stringify({
        '8587387': { id: '8587387', name: 'Genève, Bel-Air', mode: 'tram', count: 5, last: now },
        '8587418': { id: '8587418', name: 'Petit-Lancy, Les Esserts', mode: 'bus', count: 3, last: now - 1000 },
        '8587057': { id: '8587057', name: 'Genève, gare Cornavin', mode: 'train', count: 1, last: now - 2000 } }));
      localStorage.setItem('tpp:lastStop', '"8587387"'); localStorage.setItem('tpp:tab', '"departures"'); }""")
    pg.reload()
    assert pg.inner_text("#stationName") == "Genève, Bel-Air"
    pg.locator("#recent .stop-chip", has_text="Cornavin").locator(".stop-del").click()      # not on screen: nothing changes
    assert pg.inner_text("#stationName") == "Genève, Bel-Air"
    pg.click("#toastUndo")
    pg.locator("#recent .stop-chip", has_text="Bel-Air").locator(".stop-del").click()
    assert pg.inner_text("#stationName") == "Petit-Lancy, Les Esserts", pg.inner_text("#stationName")
    stops = json.loads(pg.evaluate("localStorage.getItem('tpp:stops')"))
    assert stops["8587418"]["count"] == 3, "showing the next stop is not a visit"
    assert json.loads(pg.evaluate("localStorage.getItem('tpp:lastStop')")) == "8587418"
    print("US-27       → removed Bel-Air, now showing", pg.inner_text("#stationName"))
    pg.click("#toastUndo")
    assert pg.inner_text("#stationName") == "Genève, Bel-Air" and "Bel-Air" in pg.inner_text("#recent")
    pg.click("#clearRecent")
    assert pg.is_hidden("#board") and pg.is_hidden("#recentCard")
    pg.click("#toastUndo")
    assert pg.is_visible("#board") and pg.inner_text("#stationName") == "Genève, Bel-Air"
    pg.context.close()

    # ---------- US-33: alarms set late. Journey Communes-Réunies → Cornavin leaving 07:46 (16 min after 07:30);
    # from a stop: walk 0 → leave = 07:46 − 0 − 1 min margin = 07:45, get ready = 07:35 (10 min).
    def alarm_at(minute):
        page = new_page(b, at(minute))
        page.evaluate("""() => {
          localStorage.setItem('tpp:journey:from', JSON.stringify({ kind: 'stop', id: '8592887', name: 'Lancy, Communes-Réunies', coord: [46.1745, 6.1219] }));
          localStorage.setItem('tpp:journey:to', JSON.stringify({ kind: 'stop', id: '8587057', name: 'Genève, gare Cornavin', coord: [46.209733, 6.142437] }));
          localStorage.setItem('tpp:tab', '"journey"'); }""")
        page.reload()
        return page
    pg = alarm_at(0)   # planned: nothing rings now
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click(); pg.click(".set-alarms")
    assert pg.is_hidden("#alarmBanner")
    pg.context.close()

    pg = alarm_at(0)   # set at 07:30, journey picked at 07:38: 7 min left before leaving at 07:45
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
    pg.clock.run_for(8 * 60000)
    pg.click(".set-alarms")
    pg.wait_for_selector("#alarmBanner:not([hidden])")
    assert pg.get_attribute("#alarmBanner", "data-kind") == "ready"
    body = pg.inner_text("#abBody")
    assert body.startswith("Less time than planned: 7 min left to get ready. Leave at 07:45"), body
    print("late ready  →", body)
    pg.context.close()

    pg = alarm_at(0)   # set at 07:45:30, past the leave time: only "Leave"
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
    pg.clock.run_for(15 * 60000 + 30000)
    pg.click(".set-alarms")
    pg.wait_for_selector("#alarmBanner:not([hidden])")
    assert pg.get_attribute("#alarmBanner", "data-kind") == "leave", pg.inner_text("#alarmBanner")
    pg.click("#abOk"); pg.clock.run_for(6000)
    assert pg.is_hidden("#alarmBanner"), "no 'Get ready' after 'Leave'"
    print("past leave  →", "only 'Leave' rang")
    pg.context.close()

    pg = alarm_at(0)   # set at 07:47, the tram left at 07:46: on board
    pg.click("#searchJourney"); pg.locator("#journeyList .jr").first.click()
    pg.clock.run_for(17 * 60000)
    pg.click(".set-alarms")
    pg.clock.run_for(6000)
    assert pg.is_hidden("#alarmBanner"), pg.inner_text("#alarmBanner")
    assert "Already on board" in pg.inner_text("#alarmList"), pg.inner_text("#alarmList")
    assert "Get-off reminders: Genève, gare Cornavin" in pg.inner_text("#alarmList")
    pg.clock.run_for((26 - 17) * 60000 + 6000)     # the get-off reminder still rings (Bel-Air leaves at 07:56)
    pg.wait_for_selector("#alarmBanner:not([hidden])")
    assert pg.get_attribute("#alarmBanner", "data-kind") == "alight"
    print("on board    →", pg.inner_text("#alarmList [data-k=onboard]"), "| then", pg.inner_text("#abTitle"))
    pg.context.close()

    # ---------- OJP: addresses and places of interest
    pg = b.new_page(); pg.goto("about:blank"); pg.add_script_tag(path=str(ROOT / "assets/ojp.js"))
    lancy = pg.evaluate("x => OJP_ADAPTER.toPlaces(x).places", (FX / "app_lir_address_lancy.xml").read_text())
    assert [(x["type"], x["name"]) for x in lancy] == [("address", "Lancy, Avenue des Communes-Réunies 60")], lancy
    rhone = pg.evaluate("x => OJP_ADAPTER.toPlaces(x).places.map(p => [p.type, p.id, p.name])", (FX / "app_lir_address_rhone.xml").read_text())
    assert rhone[0][0] == "address" and rhone[1] == ["stop", "8592900", "Genève, Rue du Lac"], rhone
    req = pg.evaluate("OJP_ADAPTER.locationsByName('x', { types: ['stop', 'address', 'poi'] })")
    assert "<Type>stop</Type><Type>address</Type><Type>poi</Type>" in req
    print("OJP         →", lancy[0]["name"], "| entrances 60.1…60.5 dropped")
    b.close()

print("errors:", errors); assert not errors
print("OK")
