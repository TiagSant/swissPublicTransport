"""Temporary probe: traffic messages (SIRI SX situations) in OJP answers: trips and stop events."""
import os, re, datetime as dt, urllib.request
TOKEN = os.environ["OJP_TOKEN"]
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
NOW = dt.datetime.now(dt.timezone.utc)
def env(inner):
    return ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">'
            f'<OJPRequest><siri:ServiceRequest><siri:ServiceRequestContext><siri:Language>fr</siri:Language></siri:ServiceRequestContext>'
            f'<siri:RequestTimestamp>{iso(NOW)}</siri:RequestTimestamp><siri:RequestorRef>swissPublicTransport-probe</siri:RequestorRef>{inner}'
            '</siri:ServiceRequest></OJPRequest></OJP>')
def call(inner):
    req = urllib.request.Request("https://api.opentransportdata.swiss/ojp20", data=env(inner).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/xml", "User-Agent": "swissPublicTransport-probe"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode()
def trip(a, b, extra=""):
    p = lambda i: f'<PlaceRef><StopPlaceRef>{i}</StopPlaceRef><Name><Text>n/a</Text></Name></PlaceRef>'
    return call(f'<OJPTripRequest><siri:RequestTimestamp>{iso(NOW)}</siri:RequestTimestamp><Origin>{p(a)}<DepArrTime>{iso(NOW)}</DepArrTime></Origin><Destination>{p(b)}</Destination>'
                f'<Params><NumberOfResults>4</NumberOfResults><UseRealtimeData>explanatory</UseRealtimeData><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines>'
                f'<IncludeTrackSections>false</IncludeTrackSections><IncludeLegProjection>false</IncludeLegProjection><IncludeIntermediateStops>true</IncludeIntermediateStops>{extra}</Params></OJPTripRequest>')
def board(s):
    return call(f'<OJPStopEventRequest><siri:RequestTimestamp>{iso(NOW)}</siri:RequestTimestamp><Location><PlaceRef><siri:StopPointRef>{s}</siri:StopPointRef><Name><Text>n/a</Text></Name></PlaceRef>'
                f'<DepArrTime>{iso(NOW)}</DepArrTime></Location><Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><NumberOfResults>30</NumberOfResults>'
                '<StopEventType>departure</StopEventType><IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>false</IncludeOnwardCalls><UseRealtimeData>explanatory</UseRealtimeData></Params></OJPStopEventRequest>')
def report(name, x):
    sits = re.findall(r"<PtSituation>.*?</PtSituation>", x, re.S)
    print(f"== {name}: {len(x)} bytes, {len(sits)} situations, {x.count('<SituationFullRef>')} refs, error={re.findall(r'<siri:ErrorText>([^<]*)', x)[:1]}", flush=True)
    for s in sits[:6]:
        g = lambda tag: (re.findall(rf"<siri:{tag}[^>]*>([^<]*)</siri:{tag}>", s) or [""])
        langs = re.findall(r'<siri:SummaryText xml:lang="([A-Za-z]+)"', s)
        print("   ", g("SituationNumber")[0][-12:], "| sev", g("Severity")[0], "| scope", g("ScopeType")[0], "| langs", langs,
              "| lines", g("PublishedLineName")[:3] or g("LineRef")[:3], "| summary:", g("SummaryText")[:3])
        print("      desc:", g("DescriptionText")[0][:200])
        print("      validity:", re.findall(r"<siri:ValidityPeriod><siri:StartTime>([^<]*)</siri:StartTime>(?:<siri:EndTime>([^<]*))?", s)[:2],
              "| perspectives", sorted(set(g("Perspective"))), "| affects:", sorted(set(re.findall(r"<siri:(AffectedLine|AffectedStopPlace|AffectedVehicleJourney|AffectedStopPoint|AffectedNetwork)>", s))))
    if "<SituationFullRef>" in x:
        i = x.index("<SituationFullRef>"); print("    ref context:", re.sub(r"\s+", " ", x[max(0, i - 300):i])[-300:])
for name, f in [("trip Bel-Air → Les Esserts", lambda: trip("8587387", "8587418")),
                ("trip Bel-Air → Les Esserts + IncludeSituationsContext", lambda: trip("8587387", "8587418", "<IncludeSituationsContext>true</IncludeSituationsContext>")),
                ("trip Genève → Coppet", lambda: trip("8501008", "8501023")),
                ("board Bel-Air", lambda: board("ch:1:sloid:87387")),
                ("board Genève, gare Cornavin", lambda: board("ch:1:sloid:87065")),
                ("board Blandonnet", lambda: board("ch:1:sloid:87439"))]:
    try: report(name, f())
    except Exception as e: print("==", name, "ERROR", e)
