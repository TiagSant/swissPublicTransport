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
codes = collections.Counter(); hits = []; sits = collections.Counter()
days = [dt.date(2026, 11, 16), dt.date(2026, 11, 14), dt.date(2026, 11, 20)]
for stop, name in (("8503000", "Zürich HB"), ("8500010", "Basel SBB"), ("8507000", "Bern")):
    for day in days if stop == "8503000" else days[:1]:
        for hh, mm in ((17, 0), (18, 30), (20, 0), (21, 15), (22, 30), (23, 30)) if stop == "8503000" else ((19, 0), (21, 30)):
            for lang in ("de", "fr"):
                t = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)
                root, raw = ojp('<OJPStopEventRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
                                f'<Location><PlaceRef><StopPlaceRef>{stop}</StopPlaceRef><Name><Text>{name}</Text></Name></PlaceRef><DepArrTime>{iso(t)}</DepArrTime></Location>'
                                '<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><NumberOfResults>100</NumberOfResults><StopEventType>departure</StopEventType>'
                                '<IncludePreviousCalls>false</IncludePreviousCalls><IncludeOnwardCalls>true</IncludeOnwardCalls><UseRealtimeData>full</UseRealtimeData></Params></OJPStopEventRequest>', lang)
                if root is None: continue
                for s in root.iter("PtSituation"):
                    tx = " | ".join(t.text.strip() for t in s.iter("Text") if t.text)
                    if KEY.search(tx): sits[tx[:300]] += 1
                n = 0
                for ev in root.iter("StopEvent"):
                    svc = ev.find("Service"); n += 1
                    line = txt(svc, "PublishedServiceName/Text"); dest = txt(svc, "DestinationText/Text"); mode = txt(svc, "Mode/PtMode")
                    this = ev.find("ThisCall/CallAtStop"); dep = txt(this, "ServiceDeparture/TimetabledTime"); quay = txt(this, "PlannedQuay/Text")
                    for where, node in [("service", svc)] + [("call " + txt(c.find("CallAtStop"), "StopPointName/Text"), c) for c in ev.findall("OnwardCall")] + [("this", ev.find("ThisCall"))]:
                        for code, text in attrs(node):
                            codes[(lang, code if not code.startswith("ojp") else re.sub(r"\d+", "#", code), text[:90])] += 1
                            if KEY.search(text) or (code and not code.startswith(("A__NF", "A__VN", "A__PH", "A__FS", "A__BZ", "A__FA", "A__GK", "A__VR", "A__R", "A__WR", "A__MN", "A__VB", "A__BW", "A__FZ", "A__RZ", "A__KL", "A__VC")) and "Aussteigeseite" not in text and "Ausstiegsseite" not in text and "côté" not in text.lower()):
                                hits.append(f"{lang} {day} {dep[11:16]} {name} {mode} {line} → {dest} (quai {quay}) | {where} | {code} | {text}")
                    # other children of the service that might carry it
                    for child in svc:
                        if child.tag not in ("OperatingDayRef", "JourneyRef", "PublicCode", "LineRef", "DirectionRef", "Mode", "ProductCategory", "PublishedServiceName", "TrainNumber", "Attribute", "OperatorRef", "DestinationStopPointRef", "DestinationText", "OriginStopPointRef", "OriginText", "SituationFullRefs", "Unplanned", "Cancelled", "Deviation"):
                            codes[(lang, "SERVICE-CHILD", child.tag)] += 1
                print(f"{name} {day} {hh:02}:{mm:02} {lang}: {n} departures", flush=True)
print("\n=== HITS (notices that are not the usual ones) ===")
for h in sorted(set(hits))[:400]: print(h)
print("\n=== SITUATIONS mentioning parts of trains ===")
for k, v in sits.most_common(30): print(v, k)
print("\n=== ALL NOTICE CODES / TEXTS ===")
for k, v in sorted(codes.items(), key=lambda kv: -kv[1])[:200]: print(v, k)
