"""Temporary probe: tram 14 to Meyrin around 07:43 at Les Esserts — departures board vs journeys, both sources."""
import os, json, time, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
TZ = ZoneInfo("Europe/Zurich")
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "swissPublicTransport-probe"}), timeout=60) as r: return json.loads(r.read())
ESS = "8587418"
jon = get("https://transport.opendata.ch/v1/locations?query=" + urllib.parse.quote("Genève, Jonction") + "&type=station")["stations"][0]
print("Jonction:", jon["id"], jon["name"])
for frm in ("07:13", "07:30"):
    sb = get(f"https://transport.opendata.ch/v1/stationboard?id={ESS}&limit=150&datetime=2026-11-16%20{frm}")["stationboard"]
    print(f"\nopendata board from {frm}: tram 14 to Meyrin 07:30–08:00:")
    for e in sb:
        if e["number"] == "14" and "Meyrin" in e["to"] and "07:30" <= e["stop"]["departure"][11:16] <= "08:00":
            print("  ", e["stop"]["departure"][11:16], e["to"], "| prognosis", e["stop"].get("prognosis"), "| name", e.get("name"), "| delay", e["stop"].get("delay"))
for t in ("07:35", "07:40", "07:42"):
    cs = get(f"https://transport.opendata.ch/v1/connections?from={ESS}&to={jon['id']}&limit=6&date=2026-11-16&time={t}")["connections"]
    print(f"\nopendata journeys Esserts → Jonction from {t}:")
    for c in cs:
        s = c["sections"][0]; j = s.get("journey") or {}
        print("  ", s["departure"]["departure"][11:16], j.get("category"), j.get("number"), j.get("to"), "| name", j.get("name"), "| prognosis", s["departure"].get("prognosis"))
