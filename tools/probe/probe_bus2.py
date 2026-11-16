"""Temporary probe: route of bus 2 from Musée d'ethnographie (16.11.2026 ~11:27) and its stops near Les Esserts."""
import json, math, urllib.request
ESS = (46.188095, 6.113098)
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "swissPublicTransport-probe"}), timeout=30) as r: return json.load(r)
def d(a, b):
    R=6371000; p1,p2=math.radians(a[0]),math.radians(b[0]); dl=math.radians(b[1]-a[1])
    return 2*R*math.asin(math.sqrt(math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
b = get("https://transport.opendata.ch/v1/stationboard?id=8592868&limit=15&datetime=2026-11-16%2011:20")
for x in b["stationboard"]:
    if x["number"] != "2": continue
    print("== bus", x["number"], "→", x["to"], x["stop"]["departure"], "platform", x["stop"].get("platform"))
    for p in x.get("passList", []):
        s = p["station"]; c = s.get("coordinate") or {}
        dist = round(d((c["x"], c["y"]), ESS)) if c.get("x") else None
        print("  ", (p.get("arrival") or p.get("departure") or "")[11:16], s.get("id"), s.get("name"), "→ Les Esserts", dist, "m")
    break
c = get("https://transport.opendata.ch/v1/connections?from=8592868&to=8587418&date=2026-11-16&time=11:20&limit=6")
for k in c["connections"]:
    print("CONN", k["from"]["departure"][11:16], "→", k["to"]["arrival"][11:16], [ (s["journey"]["category"]+s["journey"]["number"], s["departure"]["station"]["name"], s["arrival"]["station"]["name"]) if s.get("journey") else ("walk", s["departure"]["station"]["name"], s["arrival"]["station"]["name"]) for s in k["sections"]])
