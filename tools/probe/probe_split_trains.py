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
fl = []
for day in (dt.date(2026, 11, 14), dt.date(2026, 11, 16)):
    for hh, mm in ((6, 0), (8, 0), (10, 0), (12, 0), (14, 0), (16, 0), (17, 30), (19, 0), (20, 30), (22, 0), (23, 15)):
        t = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)
        root, raw = ojp('<OJPStopEventRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
                        f'<Location><PlaceRef><StopPlaceRef>8503000</StopPlaceRef><Name><Text>Zürich HB</Text></Name></PlaceRef><DepArrTime>{iso(t)}</DepArrTime></Location>'
                        '<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><NumberOfResults>100</NumberOfResults><StopEventType>departure</StopEventType>'
                        '<IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>true</IncludeOnwardCalls><UseRealtimeData>full</UseRealtimeData></Params></OJPStopEventRequest>', "fr")
        if root is None: continue
        evs = []
        for ev in root.iter("StopEvent"):
            svc = ev.find("Service"); this = ev.find("ThisCall/CallAtStop")
            evs.append({"line": txt(svc, "PublishedServiceName/Text"), "num": txt(svc, "TrainNumber"), "dest": txt(svc, "DestinationText/Text"),
                        "dep": txt(this, "ServiceDeparture/TimetabledTime"), "quay": txt(this, "PlannedQuay/Text"),
                        "codes": [c for c, _ in attrs(svc)], "texts": [x for c, x in attrs(svc) if c == "A__FL"],
                        "calls": [txt(c.find("CallAtStop"), "StopPointName/Text") for c in ev.findall("OnwardCall")],
                        "callfl": [txt(c.find("CallAtStop"), "StopPointName/Text") for c in ev.findall("OnwardCall") if any(a[0] == "A__FL" for a in attrs(c))]})
        for e in evs:
            if "A__FL" in e["codes"] or e["callfl"]:
                partners = [f'{o["line"]} {o["num"]} → {o["dest"]}' for o in evs if o is not e and o["dep"] == e["dep"] and o["quay"] == e["quay"]]
                key = (e["dep"], e["line"], e["dest"])
                if key in [f[0] for f in fl]: continue
                fl.append((key, f'{e["dep"][:16]} {e["line"]} n°{e["num"]} → {e["dest"]} voie {e["quay"]} | stops: {" · ".join(e["calls"][:12])} | notice at stops: {e["callfl"][:5]} | same time+platform: {partners}'))
        print(day, f"{hh:02}:{mm:02}", len(evs), "departures", flush=True)
print("\n=== TRAINS WITH A__FL ===")
for _, line in fl: print(line)
# The same notice in a journey (TripRequest), for the first one found
if fl:
    (dep, line, dest), _ = fl[0]
    t = dt.datetime.fromisoformat(dep.replace("Z", "+00:00"))
    for lang in ("fr",):
        root, raw = ojp('<OJPTripRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
                        f'<Origin><PlaceRef><StopPlaceRef>8503000</StopPlaceRef><Name><Text>Zürich HB</Text></Name></PlaceRef><DepArrTime>{iso(t - dt.timedelta(minutes=1))}</DepArrTime></Origin>'
                        f'<Destination><PlaceRef><Name><Text>{dest}</Text></Name><StopPlaceRef>{dest}</StopPlaceRef></PlaceRef></Destination>'
                        '<Params><NumberOfResults>3</NumberOfResults><IncludeIntermediateStops>true</IncludeIntermediateStops></Params></OJPTripRequest>', lang)
        print("\n=== TRIP REQUEST to", dest, "===")
        if root is not None:
            for leg in root.iter("TimedLeg"):
                svc = leg.find("Service")
                print(txt(svc, "PublishedServiceName/Text"), txt(svc, "DestinationText/Text"), [a for a in attrs(svc)][:12])
            m = re.findall(rb"A__FL[^<]*", raw); print("A__FL in raw trip answer:", len(m))
