"""US-67: traffic messages (OJP: SIRI SX situations) on the journey and the departures.

Real answers carry them (probe 16.11.2026 19:50, Genève → Coppet: L1/L4 trains in single composition, linked to
those trains). Here a recorded OJP answer (Zürich HB → Konstanz) with two messages added to its first train: one valid
now (shown: summary, the rest on a tap; tag on the card) and one valid next month (not shown).
The departures' parser is checked on a recorded stop event answer with a message added."""
import os, re, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "prototypes" / "sprint-09-my-places" / "index.html").as_uri()
OUT = ROOT / "tests" / "out"; OUT.mkdir(exist_ok=True)
CORS = {"Access-Control-Allow-Origin": "*"}
tz = ZoneInfo("Europe/Zurich")
NOW = dt.datetime(2026, 11, 16, 23, 20, tzinfo=tz)
EMPTY_SER = ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns:siri="http://www.siri.org.uk/siri" version="2.0" xmlns="http://www.vdv.de/ojp"><OJPResponse><siri:ServiceDelivery>'
             '<OJPStopEventDelivery><siri:ErrorCondition><siri:OtherError/><siri:Description>STOPEVENT_NORESULTS</siri:Description></siri:ErrorCondition></OJPStopEventDelivery>'
             '</siri:ServiceDelivery></OJPResponse></OJP>')
def situation(num, start, end, fr, de):
    def lang(tag, texts): return "".join(f'<siri:{tag} xml:lang="{l}">{t}</siri:{tag}>' for l, t in texts)
    return (f'<PtSituation><siri:CreationTime>2026-11-16T10:00:00Z</siri:CreationTime><siri:ParticipantRef>ski-ems-out-sx_prod</siri:ParticipantRef>'
            f'<siri:SituationNumber>{num}</siri:SituationNumber><siri:Version>1</siri:Version>'
            f'<siri:ValidityPeriod><siri:StartTime>{start}</siri:StartTime><siri:EndTime>{end}</siri:EndTime></siri:ValidityPeriod>'
            '<siri:AlertCause>constructionWork</siri:AlertCause><siri:Severity>normal</siri:Severity><siri:ScopeType>line</siri:ScopeType><siri:Planned>false</siri:Planned>'
            '<siri:PublishingActions><siri:PublishingAction><siri:PassengerInformationAction><siri:ActionRef>1</siri:ActionRef><siri:Perspective>general</siri:Perspective>'
            '<siri:TextualContent>'
            f'<siri:SummaryContent>{lang("SummaryText", [("DE", de[0]), ("FR", fr[0])])}</siri:SummaryContent>'
            f'<siri:DescriptionContent>{lang("DescriptionText", [("DE", de[1]), ("FR", fr[1])])}</siri:DescriptionContent>'
            f'<siri:ConsequenceContent>{lang("ConsequenceText", [("FR", fr[2])])}</siri:ConsequenceContent>'
            '</siri:TextualContent></siri:PassengerInformationAction></siri:PublishingAction></siri:PublishingActions></PtSituation>')
REF = lambda num: f'<SituationFullRefs><SituationFullRef><siri:ParticipantRef>ski-ems-out-sx_prod</siri:ParticipantRef><siri:SituationNumber>{num}</siri:SituationNumber></SituationFullRef></SituationFullRefs>'
NOW_SIT = situation("ch:1:sstid:test-now", "2026-11-16T05:00:00Z", "2026-11-17T03:00:00Z",
                    ("Interruption entre Winterthur et Wil", "Travaux sur la voie entre Winterthur et Wil.", "Des bus remplacent les trains entre Winterthur et Wil."),
                    ("Unterbruch zwischen Winterthur und Wil", "Bauarbeiten zwischen Winterthur und Wil."))
LATER_SIT = situation("ch:1:sstid:test-later", "2026-12-01T05:00:00Z", "2026-12-02T03:00:00Z",
                      ("Travaux en décembre", "Horaire modifié en décembre.", "Prévoyez plus de temps."), ("Bauarbeiten im Dezember", "Fahrplan im Dezember."))
def trip_xml():
    x = (ROOT / "tests/fixtures/ojp-split/trip_zurich_konstanz.xml").read_text()
    i = x.index("</Service>")                                     # the first train (RE Zürich HB → Winterthur)
    x = x[:i] + REF("ch:1:sstid:test-now") + REF("ch:1:sstid:test-later") + x[i:]
    return x.replace("</TripResponseContext>", f"<Situations>{NOW_SIT}{LATER_SIT}</Situations></TripResponseContext>", 1)
def board_xml():
    x = (ROOT / "tests/fixtures/ojp/ser_geneve_gare.xml").read_text()
    x = re.sub(r"<PtSituation>.*?</PtSituation>", "", x, flags=re.S)   # the recorded one: other dates
    x = x.replace("<SituationFullRefs>", "<SituationFullRefs_>").replace("</SituationFullRefs>", "</SituationFullRefs_>")
    i = x.index("</Service>")
    x = x[:i] + REF("ch:1:sstid:test-now") + x[i:]
    return x.replace("<Situations>", f"<Situations>{NOW_SIT}", 1) if "<Situations>" in x else x
def ojp(route):
    if route.request.method == "OPTIONS":
        return route.fulfill(status=204, headers=dict(CORS, **{"Access-Control-Allow-Headers": "authorization,content-type"}))
    body = route.request.post_data or ""
    route.fulfill(status=200, headers=CORS, content_type="application/xml", body=trip_xml() if "OJPTripRequest" in body else EMPTY_SER)
STOP = lambda i, n, lat, lon: {"kind": "stop", "id": i, "name": n, "coord": [lat, lon]}
norm = lambda s: " ".join(s.split())
errors = []

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    ctx = b.new_context(locale="fr-CH", timezone_id="Europe/Zurich", viewport={"width": 390, "height": 1000})
    ctx.route("https://api.opentransportdata.swiss/**", ojp)
    for u in ("https://transport.opendata.ch/**", "https://cdnjs.cloudflare.com/**", "https://*.tile.openstreetmap.org/**", "https://routing.openstreetmap.de/**"):
        ctx.route(u, lambda r: r.abort())
    pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.clock.install(time=NOW.timestamp()); pg.goto(PAGE)
    store = {"tab": "journey", "lang": "fr", "ojpKey": "test-key-0123456789abcdef", "settings": {"footMaxMin": 0, "realWalk": False},
             "journey:from": STOP("8503000", "Zürich HB", 47.378177, 8.540212), "journey:to": STOP("8014586", "Konstanz", 47.658, 9.177)}
    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
    pg.reload(); pg.click("#searchJourney"); pg.wait_for_selector("#journeyList .jr", timeout=10000); pg.wait_for_timeout(1000)

    # 1. journey: tag on the card; the message valid now on the first train, in French; next month's not shown
    card = norm(pg.locator("#journeyList .jr").first.inner_text())
    assert "⚠ Info trafic" in card, card
    pg.locator("#journeyList .jr").first.click()
    det = pg.locator("#journeyList .jr-detail").first
    r0, r1 = det.locator(".leg.ride").nth(0), det.locator(".leg.ride").nth(1)
    sit = r0.locator(".sit")
    assert sit.count() == 1 and "⚠ Interruption entre Winterthur et Wil" in sit.inner_text(), r0.inner_text()
    assert "décembre" not in det.inner_text() and r1.locator(".sit").count() == 0
    assert not r0.locator(".sit p").first.is_visible()
    r0.locator(".sit summary").click()
    more = norm(r0.locator(".sit").inner_text())
    assert "Travaux sur la voie" in more and "Des bus remplacent les trains" in more, more
    pg.screenshot(path=str(OUT / "traffic-info.png"))
    print("journey     →", more)

    # 2. followed: the message stays on the ride
    pg.click("#journeyList .jr-detail .set-alarms"); pg.wait_for_selector("#alarmList .trip")
    while pg.is_visible("#alarmBanner"): pg.click("#abOk")
    assert "Interruption entre Winterthur et Wil" in pg.locator("#alarmList .trip").first.inner_text()
    print("followed    → shown on the followed ride")

    # 3. departures (stop events): the message of a departure, read in the app's language
    got = pg.evaluate("xml => { const r = OJP_ADAPTER.toStationboard(xml, '8501008', new Map(), 'fr'); const d = r.stationboard.find(x => x.situations.length);"
                      " return d ? [d.category + ' ' + d.number, d.situations.map(s => s.summary)] : null; }", board_xml())
    assert got and got[1] == ["Interruption entre Winterthur et Wil"], got
    de = pg.evaluate("xml => OJP_ADAPTER.toStationboard(xml, '8501008', new Map(), 'de').stationboard.find(x => x.situations.length).situations[0].summary", board_xml())
    assert de == "Unterbruch zwischen Winterthur und Wil", de
    print("departures  →", got)
    ctx.close(); b.close()
print("errors:", errors); assert not errors
print("OK")
