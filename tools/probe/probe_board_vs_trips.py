"""Temporary probe: are the runs of journeys found in the departures board of their stop? (Les Esserts, tram 14)."""
import os, re, json, time, datetime as dt, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
TZ = ZoneInfo("Europe/Zurich"); TOKEN = os.environ["OJP_TOKEN"]
now = dt.datetime.now(TZ)
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "swissPublicTransport-probe"}), timeout=60) as r: return json.loads(r.read())
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ojp(inner):
    ts = iso(dt.datetime.now(dt.timezone.utc))
    body = ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0"><OJPRequest><siri:ServiceRequest>'
            f'<siri:ServiceRequestContext><siri:Language>fr</siri:Language></siri:ServiceRequestContext><siri:RequestTimestamp>{ts}</siri:RequestTimestamp><siri:RequestorRef>probe</siri:RequestorRef>{inner.replace("{TS}", ts)}</siri:ServiceRequest></OJPRequest></OJP>').encode()
    req = urllib.request.Request("https://api.opentransportdata.swiss/ojp20", data=body, headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/xml"})
    with urllib.request.urlopen(req, timeout=60) as r: x = r.read()
    root = ET.fromstring(x)
    for e in root.iter(): e.tag = e.tag.split("}")[-1]
    time.sleep(2); return root
def txt(n, p):
    m = n.find(p) if n is not None else None
    return m.text.strip() if m is not None and m.text else ""
loc = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ).strftime("%H:%M") if s else "--"
ESS, JON = "8587418", "8587060"
print("now", now.strftime("%Y-%m-%d %H:%M"))
for rnd in range(3):
    t0 = dt.datetime.now(TZ)
    # --- transport.opendata.ch, as the app: board from now-30 min, limit 150; journeys Esserts → Jonction
    sb = get(f"https://transport.opendata.ch/v1/stationboard?id={ESS}&limit=150&datetime={urllib.parse.quote((t0 - dt.timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M'))}")["stationboard"]
    b14 = [(e["stop"]["departure"][11:16], e["to"], e["category"], e["number"], (e["stop"].get("prognosis") or {}).get("departure")) for e in sb if e["number"] == "14"]
    cs = get(f"https://transport.opendata.ch/v1/connections?from={ESS}&to={JON}&limit=6&date={t0:%Y-%m-%d}&time={urllib.parse.quote(t0.strftime('%H:%M'))}")["connections"]
    rides = [(c["sections"][0]["departure"]["departure"][11:16], c["sections"][0]["journey"]["category"], c["sections"][0]["journey"]["number"], c["sections"][0]["journey"]["to"]) for c in cs if c["sections"][0].get("journey")]
    times14 = {x[0] for x in b14}
    print(f"\n[{t0:%H:%M:%S}] opendata board: {len(sb)} entries, until {sb[-1]['stop']['departure'][11:16] if sb else '-'}; tram 14: {b14[:30]}")
    print("  opendata journeys (first ride):", rides)
    print("  journey runs missing from the board:", [r for r in rides if r[2] == "14" and r[0] not in times14])
    # --- OJP, as the app: light board (no onward calls) from now-30, 150 results; trips Esserts → Jonction
    r = ojp(f'<OJPStopEventRequest><siri:RequestTimestamp>{{TS}}</siri:RequestTimestamp><Location><PlaceRef><StopPlaceRef>{ESS}</StopPlaceRef><Name><Text>x</Text></Name></PlaceRef><DepArrTime>{iso(t0 - dt.timedelta(minutes=30))}</DepArrTime></Location>'
            '<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><NumberOfResults>150</NumberOfResults><StopEventType>departure</StopEventType><IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>false</IncludeOnwardCalls><UseRealtimeData>full</UseRealtimeData></Params></OJPStopEventRequest>')
    ev = [(loc(txt(e, "ThisCall/CallAtStop/ServiceDeparture/TimetabledTime")), txt(e, "Service/PublishedServiceName/Text"), txt(e, "Service/DestinationText/Text"),
           loc(txt(e, "ThisCall/CallAtStop/ServiceDeparture/EstimatedTime")), txt(e, "Service/Cancelled"), txt(e, "ThisCall/CallAtStop/NotServicedStop")) for e in r.iter("StopEvent")]
    o14 = [x for x in ev if x[1] == "14"]
    print(f"  OJP board: {len(ev)} events, until {ev[-1][0] if ev else '-'}; tram 14: {o14[:30]}")
    tr = ojp(f'<OJPTripRequest><siri:RequestTimestamp>{{TS}}</siri:RequestTimestamp><Origin><PlaceRef><StopPlaceRef>{ESS}</StopPlaceRef><Name><Text>x</Text></Name></PlaceRef><DepArrTime>{iso(t0)}</DepArrTime></Origin>'
             f'<Destination><PlaceRef><StopPlaceRef>{JON}</StopPlaceRef><Name><Text>y</Text></Name></PlaceRef></Destination><Params><NumberOfResults>6</NumberOfResults><UseRealtimeData>full</UseRealtimeData></Params></OJPTripRequest>')
    tl = [(loc(txt(l, "LegBoard/ServiceDeparture/TimetabledTime")), txt(l, "Service/PublishedServiceName/Text"), txt(l, "Service/DestinationText/Text"), loc(txt(l, "LegBoard/ServiceDeparture/EstimatedTime")), txt(l, "Service/Cancelled"))
          for t in tr.iter("Trip") for l in list(t.iter("TimedLeg"))[:1]]
    print("  OJP trips (first ride):", tl)
    print("  OJP trip runs missing from the OJP board:", [x for x in tl if x[1] == "14" and x[0] not in {e[0] for e in o14}])
    if rnd < 2: time.sleep(240)
