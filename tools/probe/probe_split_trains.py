"""Temporary probe: do OJP answers say when a train is split (two coupled trains going to different places)?
Evening departures from Zürich HB (and a few other hubs), all notices of each train and of each of its stops."""
import os, re, json, time, datetime as dt, urllib.request, collections, xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
TOKEN = os.environ["OJP_TOKEN"]; TZ = ZoneInfo("Europe/Zurich")
KEY = re.compile(r"geteilt|getrennt|trennung|teilung|zugteil|flügel|vorder|hinter|divis|sépar|separ|partie avant|partie arrière|tête|queue|diviso|separat|parte anteriore|parte posteriore|split|portion|front|rear|wagen|voiture|carrozz|vereinigt|vereinigung|couplé|accroch|attach", re.I)
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def ojp(inner, lang):
    ts = iso(dt.datetime.now(dt.timezone.utc))
    body = ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">'
            f'<OJPRequest><siri:ServiceRequest><siri:ServiceRequestContext><siri:Language>{lang}</siri:Language></siri:ServiceRequestContext>'
            f'<siri:RequestTimestamp>{ts}</siri:RequestTimestamp><siri:RequestorRef>swissPublicTransport-probe</siri:RequestorRef>{inner.replace("{TS}", ts)}'
            '</siri:ServiceRequest></OJPRequest></OJP>').encode()
    for _ in range(4):
        try:
            req = urllib.request.Request("https://api.opentransportdata.swiss/ojp20", data=body, headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/xml"})
            with urllib.request.urlopen(req, timeout=60) as r: x = r.read()
            time.sleep(1.5)
            root = ET.fromstring(x)
            for e in root.iter(): e.tag = e.tag.split("}")[-1]
            return root, x
        except Exception as e:
            print("  retry", e); time.sleep(20)
    return None, b""
def txt(n, p):
    m = n.find(p) if n is not None else None
    return m.text.strip() if m is not None and m.text else ""
def attrs(node):
    out = []
    for a in node.iter("Attribute"):
        out.append((txt(a, "Code"), " ".join(t.text.strip() for t in a.iter("Text") if t.text)))
    return out
def resolve(name):
    root, _ = ojp('<OJPLocationInformationRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
                  f'<InitialInput><Name>{name}</Name></InitialInput><Restrictions><Type>stop</Type><NumberOfResults>3</NumberOfResults></Restrictions></OJPLocationInformationRequest>', "fr")
    for pr in root.iter("PlaceResult"):
        ref = txt(pr, "Place/StopPlace/StopPlaceRef")
        if ref: return ref, txt(pr, "Place/Name/Text")
def trip(dest, t, lang="fr"):
    ref, nm = resolve(dest)
    root, raw = ojp('<OJPTripRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
                    f'<Origin><PlaceRef><StopPlaceRef>8503000</StopPlaceRef><Name><Text>Zürich HB</Text></Name></PlaceRef><DepArrTime>{iso(t)}</DepArrTime></Origin>'
                    f'<Destination><PlaceRef><StopPlaceRef>{ref}</StopPlaceRef><Name><Text>{nm}</Text></Name></PlaceRef></Destination>'
                    '<Params><NumberOfResults>2</NumberOfResults><IncludeIntermediateStops>true</IncludeIntermediateStops><UseRealtimeData>full</UseRealtimeData></Params></OJPTripRequest>', lang)
    print(f"\n=== TRIP Zürich HB → {nm} ({ref}) {t:%H:%M} {lang} ===")
    if root is None: print("no answer"); return
    for k, tr in enumerate(root.iter("Trip")):
        print(f"-- trip {k}: {txt(tr, 'StartTime')[11:16]} → {txt(tr, 'EndTime')[11:16]}, transfers {txt(tr, 'Transfers')}")
        for leg in tr.findall("Leg"):
            for kind in leg:
                if kind.tag == "TimedLeg":
                    svc = kind.find("Service")
                    b = kind.find("LegBoard"); a = kind.find("LegAlight")
                    extra = [c.tag for c in kind if c.tag not in ("LegBoard", "LegAlight", "LegIntermediate", "Service", "LegTrack", "Extension")]
                    print(f"   ride {txt(svc, 'PublishedServiceName/Text')} n°{txt(svc, 'TrainNumber')} → {txt(svc, 'DestinationText/Text')} | {txt(b, 'StopPointName/Text')} {txt(b, 'PlannedQuay/Text')} {txt(b, 'ServiceDeparture/TimetabledTime')[11:16]}"
                          f" → {txt(a, 'StopPointName/Text')} {txt(a, 'PlannedQuay/Text')} {txt(a, 'ServiceArrival/TimetabledTime')[11:16]} | notices {[c for c, _ in attrs(svc)]} | other: {extra}")
                    for c in [b, a] + kind.findall("LegIntermediate"):
                        fl = [x for x in attrs(c) if x[0] == "A__FL" or "multipl" in x[1]]
                        if fl: print("     at", txt(c, "StopPointName/Text"), fl)
                elif kind.tag in ("TransferLeg", "ContinuousLeg"):
                    print(f"   {kind.tag}: {[c.tag for c in kind]} {txt(kind, 'TransferType')} {txt(kind, 'Duration')}")
    print("A__FL in raw answer:", len(re.findall(rb"A__FL", raw)), "| words:", sorted(set(re.findall(rb"(?i)staySeated|InterchangeStatus|Guaranteed|Continu\w*", raw)))[:8])
day = dt.date(2026, 11, 16)
for dest in ("St. Gallen", "Konstanz", "Weinfelden", "Winterthur"):
    trip(dest, dt.datetime(day.year, day.month, day.day, 22, 37, tzinfo=TZ))
trip("St. Gallen", dt.datetime(day.year, day.month, day.day, 22, 37, tzinfo=TZ), "de")
