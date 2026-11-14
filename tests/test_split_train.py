"""US-54: trains with several destinations (coupled trains that split), from the OJP notice A__FL.

Real case (OJP, 16.11.2026): RE 2143 Zürich HB 23:39 → "Winterthur | St. Gallen", notice A__FL; OJP shows the split
as a change at Winterthur: track 5, then RE 75 to Konstanz from track 5, sectors E–H, 3 min later.
Expected: the notice on the train's ride (planning and following), "same train" instead of a change walk, and the
get-off reminder before Winterthur says the train splits."""
import os, re, json, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes" / "sprint-09-my-places" / "index.html").as_uri()
FX = ROOT / "tests" / "fixtures" / "ojp-split"
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
CORS = {"Access-Control-Allow-Origin": "*"}
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 16, 23, 20, tzinfo=tz)
EMPTY_SER = ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns:siri="http://www.siri.org.uk/siri" version="2.0" xmlns="http://www.vdv.de/ojp"><OJPResponse><siri:ServiceDelivery>'
             '<OJPStopEventDelivery><siri:ErrorCondition><siri:OtherError/><siri:Description>STOPEVENT_NORESULTS</siri:Description></siri:ErrorCondition></OJPStopEventDelivery>'
             '</siri:ServiceDelivery></OJPResponse></OJP>')
STOP = lambda i, n, lat, lon: {"kind": "stop", "id": i, "name": n, "coord": [lat, lon]}
errors = []

def ojp(route):
    if route.request.method == "OPTIONS":
        return route.fulfill(status=204, headers=dict(CORS, **{"Access-Control-Allow-Headers": "authorization,content-type"}))
    body = route.request.post_data or ""
    if "OJPTripRequest" in body:
        return route.fulfill(status=200, headers=CORS, content_type="application/xml", body=(FX / "trip_zurich_konstanz.xml").read_text())
    route.fulfill(status=200, headers=CORS, content_type="application/xml", body=EMPTY_SER)

def session(b, lang="fr"):
    ctx = b.new_context(locale="fr-CH", timezone_id="Europe/Zurich", viewport={"width": 390, "height": 1000})
    ctx.route("https://api.opentransportdata.swiss/**", ojp)
    ctx.route("https://transport.opendata.ch/**", lambda r: r.abort())
    ctx.route("https://cdnjs.cloudflare.com/**", lambda r: r.abort())
    ctx.route("https://*.tile.openstreetmap.org/**", lambda r: r.abort())
    ctx.route("https://routing.openstreetmap.de/**", lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp())
    pg.goto(PAGE)
    store = {"tab": "journey", "lang": lang, "ojpKey": "test-key-0123456789abcdef", "settings": {"footMaxMin": 0, "realWalk": False},
             "journey:from": STOP("8503000", "Zürich HB", 47.378177, 8.540212), "journey:to": STOP("8014586", "Konstanz", 47.658, 9.177)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney")
    pg.wait_for_selector("#journeyList .jr", timeout=10000)
    pg.wait_for_timeout(1500)
    return ctx, pg

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx, pg = session(b)
    pg.locator("#journeyList .jr").first.click(); det = pg.locator("#journeyList .jr-detail").first
    txt = " ".join(det.inner_text().split())
    note = det.locator(".leg.ride").first.locator(".split-note").inner_text()
    assert "Ce train se sépare à Winterthur" in note and "voie 5, secteurs E–H" in note and "« Konstanz »" in note, note
    assert det.locator(".leg.ride").nth(1).locator(".split-note").count() == 0      # the RE 75 is a plain train
    assert "Même train : restez dans la partie pour Konstanz" in txt and "3 min d’attente" in txt, txt
    assert "min de marche" not in txt, txt                                          # no change walk on the same train
    pg.screenshot(path=str(OUT / "split-train-plan.png"))
    print("planning   → notice on the RE (splits at Winterthur, part for Konstanz from track 5, sectors E–H); same train, no walk")

    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    a = pg.evaluate("JSON.parse(localStorage.getItem('tpp:alarms'))[0]")
    assert a["plan"][0]["multiDest"] is True and a["plan"][1]["splitStay"] is True, a["plan"][:2]
    assert a["alights"][0]["split"]["dest"] == "Konstanz" and a["alights"][0]["split"]["sectors"] == "E–H", a["alights"][0]
    trip = " ".join(pg.locator("#alarmList .trip").first.inner_text().split())
    assert "Ce train se sépare à Winterthur" in trip and "Même train : restez dans la partie pour Konstanz" in trip, trip
    assert "Changement de quai" not in trip, trip
    pg.click("#alarmList [data-act='test-alight']")
    assert pg.inner_text("#abTitle") == "🔔 Prochain arrêt : le train se sépare", pg.inner_text("#abTitle")
    body = pg.inner_text("#abBody")
    assert body.startswith("À Winterthur, seule la partie pour Konstanz continue (voie 5, secteurs E–H).") and "rejoignez la partie pour Konstanz" in body, body
    pg.screenshot(path=str(OUT / "split-train-follow.png"))
    ctx.close()
    print("following  → notice on the step, same train row, reminder: “le train se sépare”, part for Konstanz")

    ctx, pg = session(b, "de")
    pg.locator("#journeyList .jr").first.click()
    note = pg.locator("#journeyList .jr-detail .leg.ride .split-note").first.inner_text()
    assert "Dieser Zug wird in Winterthur geteilt" in note and "Sektoren E–H" in note, note
    ctx.close()
    print("German     → Dieser Zug wird in Winterthur geteilt …")
    b.close()
print("errors:", errors); assert not errors
print("OK")
