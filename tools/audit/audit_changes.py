"""Audit of the changes (US-50, US-51, US-53, BUG-11) on real data, all over Switzerland.

1. The real app (prototype Sprint 9, both data sources: transport.opendata.ch and OJP 2.0) plans journeys between
   pairs of stops in several cities, at fixed times. After its own improvements, each change of the 8 journeys
   shown is read from the page (a read-only hook added to the served copy only).
2. An independent check: for each change, the two vehicles' full runs (all previous and next stops, OJP stop
   events) give every place where the change could be made with the same vehicles: get off anywhere after boarding,
   board the next one anywhere before getting off. The shortest walk that keeps the change comfortable is the best
   possible one.
3. Report: per change, the API's walk, the app's walk, the best possible walk; misses (the app could walk less by
   1 min or more), regressions (the app walks more than the API, or the change no longer works).

Same rules as the app: straight line × 1.3 at 4.8 km/h, platform positions from ATLAS (assets/quays.js), a change
keeps its margin (at least 1 min, at most 3), same stop and same platform means no walk.
Env: OJP_TOKEN (never printed), OUT (folder for the report)."""
import json, math, os, re, sys, time, datetime as dt, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("OUT", "audit-out")); OUT.mkdir(parents=True, exist_ok=True)
TOKEN = os.environ["OJP_TOKEN"]
TZ = ZoneInfo("Europe/Zurich")
PAGE = "http://127.0.0.1:8765/prototypes/sprint-09-my-places/index.html"
SPEED = 4.8 * 1000 / 60; DETOUR = 1.3; COMFORT = 3

PAIRS = [  # (from, to) by name; resolved to the first stop OJP gives
    ("Petit-Lancy, Les Esserts", "Lausanne"), ("Genève, Jonction", "Genève, Nations"),
    ("Onex, Bandol", "Genève-Aéroport"), ("Vernier, Blandonnet", "Genève, Plainpalais"),
    ("Thônex, Moillesulaz", "Genève, Servette"), ("Carouge GE, Rondeau", "Meyrin, Gravière"),
    ("Lausanne, Ouchy-Olympique", "Ecublens VD, EPFL"), ("Prilly, Galicien", "Lausanne, CHUV"),
    ("Renens VD, gare", "Lausanne, Bellevaux"), ("Fribourg, Bourguillon", "Lausanne, Flon"),
    ("Bern, Zytglogge", "Köniz, Zentrum"), ("Bern, Wankdorf Bahnhof", "Bern, Bümpliz Nord"),
    ("Zürich, Bucheggplatz", "Zürich, Kreuzplatz"), ("Zürich, Hardplatz", "Zürich, ETH/Universitätsspital"),
    ("Winterthur, Hauptbahnhof", "Zürich Flughafen"), ("Basel, Barfüsserplatz", "Riehen, Dorf"),
    ("Allschwil, Dorf", "Basel, Bahnhof SBB"), ("Kriens, Zentrum Pilatus", "Luzern, Verkehrshaus"),
    ("St. Gallen, Marktplatz", "Herisau, Bahnhof"), ("Lugano, Centro", "Bellinzona, Stazione"),
    ("Neuchâtel, Place Pury", "Biel/Bienne, Zentralplatz"), ("Sion, Gare", "Montreux, Marché"),
]
TIMES = [dt.datetime(2026, 11, 16, 8, 0, tzinfo=TZ), dt.datetime(2026, 11, 16, 17, 30, tzinfo=TZ)]
SOURCES = ["opendata", "ojp"]
if os.environ.get("QUICK"): PAIRS, TIMES, SOURCES = PAIRS[:2], TIMES[:1], SOURCES[:1]
if os.environ.get("DEBUG"): PAIRS, TIMES, SOURCES = [("Carouge GE, Rondeau", "Meyrin, Gravière"), ("Kriens, Zentrum Pilatus", "Luzern, Verkehrshaus")], TIMES[1:], ["opendata"]

# ---------------- OJP from Python (the independent side) ----------------
def iso(t): return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def envelope(inner):
    ts = iso(dt.datetime.now(dt.timezone.utc))
    return ('<?xml version="1.0" encoding="utf-8"?><OJP xmlns="http://www.vdv.de/ojp" xmlns:siri="http://www.siri.org.uk/siri" version="2.0">'
            f'<OJPRequest><siri:ServiceRequest><siri:ServiceRequestContext><siri:Language>fr</siri:Language></siri:ServiceRequestContext>'
            f'<siri:RequestTimestamp>{ts}</siri:RequestTimestamp><siri:RequestorRef>swissPublicTransport-audit</siri:RequestorRef>{inner.replace("{TS}", ts)}'
            '</siri:ServiceRequest></OJPRequest></OJP>')
STATS = {"ojp_calls": 0, "ojp_errors": 0}
def ojp(inner):
    body = envelope(inner).encode()
    for attempt in range(5):
        try:
            STATS["ojp_calls"] += 1
            req = urllib.request.Request("https://api.opentransportdata.swiss/ojp20", data=body,
                                         headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/xml", "User-Agent": "swissPublicTransport-audit"})
            with urllib.request.urlopen(req, timeout=60) as r: x = r.read()
            time.sleep(0.4)
            root = ET.fromstring(x)
            for e in root.iter(): e.tag = e.tag.split("}")[-1]
            return root
        except Exception as e:
            STATS["ojp_errors"] += 1
            time.sleep(20 if "429" in str(e) else 3)
    return None

def txt(node, path):
    n = node.find(path) if node is not None else None
    return n.text.strip() if n is not None and n.text else None
def id7(ref):
    m = re.match(r"^ch:1:sloid:(\d+)", ref or "")
    if m: return "85" + m.group(1).zfill(5) if len(m.group(1)) <= 5 else m.group(1)
    return ref if re.match(r"^\d{7}$", ref or "") else None
def ptime(s): return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000) if s else None

def resolve(name):
    r = ojp(f'<OJPLocationInformationRequest><siri:RequestTimestamp>{{TS}}</siri:RequestTimestamp><InitialInput><Name>{name}</Name></InitialInput>'
            '<Restrictions><Type>stop</Type><NumberOfResults>5</NumberOfResults></Restrictions></OJPLocationInformationRequest>')
    for pr in (r.iter("PlaceResult") if r is not None else []):
        ref = txt(pr, "Place/StopPlace/StopPlaceRef"); nm = txt(pr, "Place/Name/Text") or txt(pr, "Place/StopPlace/StopPlaceName/Text")
        lat, lon = txt(pr, "Place/GeoPosition/Latitude"), txt(pr, "Place/GeoPosition/Longitude")
        if ref and id7(ref) and lat:
            return {"kind": "stop", "id": id7(ref), "name": nm, "coord": [float(lat), float(lon)]}
    return None

EVENTS = {}
def stop_events(stop, at_ms):
    """Departures at a stop around a time, with every previous and next call of each run (cached per minute)."""
    key = (stop, at_ms // 60000)
    if key in EVENTS: return EVENTS[key]
    t = dt.datetime.fromtimestamp((at_ms - 60000) / 1000, dt.timezone.utc)
    r = ojp('<OJPStopEventRequest><siri:RequestTimestamp>{TS}</siri:RequestTimestamp>'
            f'<Location><PlaceRef><StopPlaceRef>{stop}</StopPlaceRef><Name><Text>n/a</Text></Name></PlaceRef><DepArrTime>{iso(t)}</DepArrTime></Location>'
            '<Params><IncludeAllRestrictedLines>true</IncludeAllRestrictedLines><NumberOfResults>60</NumberOfResults><StopEventType>departure</StopEventType>'
            '<IncludePreviousCalls>true</IncludePreviousCalls><IncludeOnwardCalls>true</IncludeOnwardCalls><UseRealtimeData>none</UseRealtimeData></Params></OJPStopEventRequest>')
    out = []
    if r is not None:
        coords = {}
        for pl in r.iter("Place"):
            ref = txt(pl, "StopPoint/StopPointRef") or txt(pl, "StopPlace/StopPlaceRef")
            lat, lon = txt(pl, "GeoPosition/Latitude"), txt(pl, "GeoPosition/Longitude")
            if ref and lat: coords[ref] = [float(lat), float(lon)]
        for ev in r.iter("StopEvent"):
            calls = []
            for kind in ("PreviousCall", "ThisCall", "OnwardCall"):
                for c in ev.findall(kind):
                    cs = c.find("CallAtStop"); ref = txt(cs, "StopPointRef")
                    calls.append({"this": kind == "ThisCall", "id": id7(ref), "name": txt(cs, "StopPointName/Text"),
                                  "quay": txt(cs, "PlannedQuay/Text") or "", "coord": coords.get(ref),
                                  "arr": ptime(txt(cs, "ServiceArrival/TimetabledTime")), "dep": ptime(txt(cs, "ServiceDeparture/TimetabledTime")),
                                  "order": int(txt(cs, "Order") or 0)})
            calls.sort(key=lambda c: c["order"])
            svc = ev.find("Service")
            out.append({"line": txt(svc, "PublishedServiceName/Text") or "", "dest": txt(svc, "DestinationText/Text") or "", "calls": calls})
    EVENTS[key] = out
    return out

norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
def find_run(ride):
    """The run of a ride, seen from its boarding stop: line and planned departure must match."""
    best = None
    if not ride.get("from") or not ride["from"].get("id") or not ride.get("dep"): return None
    for ev in stop_events(ride["from"]["id"], ride["dep"]):
        this = next((c for c in ev["calls"] if c["this"]), None)
        if not this or this["id"] != str(ride["from"]["id"]) or this["dep"] is None or abs(this["dep"] - ride["dep"]) > 60000: continue
        after = [c["id"] for c in ev["calls"][ev["calls"].index(this) + 1:]]
        if str(ride["toStop"]["id"]) not in after: continue   # the other direction, same minute
        names = {norm(ride.get("number")), norm(ride.get("label")), norm(str(ride.get("category") or "") + str(ride.get("number") or ""))} - {""}
        ln = norm(ev["line"])
        num = norm(ride.get("number"))
        if ln in names or (num and ln.endswith(num) and ln[:-len(num)].isalpha()):
            if best is None or abs(this["dep"] - ride["dep"]) < best[0]: best = (abs(this["dep"] - ride["dep"]), ev)
    return best and best[1]

# ---------------- positions and walks, as the app ----------------
QS = {}
for f in sorted((ROOT / "assets/quays-ch").glob("*.js")):   # all of Switzerland (same data as the app)
    QS.update(json.loads(f.read_text().split("] = ", 1)[1].rstrip().rstrip(";")))
QS.update(json.loads(re.search(r"window\.QUAYS = (\{.*\});?\s*$", (ROOT / "assets/quays.js").read_text(), re.S).group(1))["stops"])
def hav(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1])
    return 2 * 6371000 * math.asin(math.sqrt(math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
def pos(sid, coord, quay):
    q = QS.get(str(sid) if sid else "", {})
    if quay:
        m = re.match(r"^(\d{1,2})\s*[A-Z]{1,3}(?:\s*-\s*[A-Z])?$", str(quay).upper())
        for k in (quay, str(quay).upper(), str(quay).zfill(2)) + ((m.group(1),) if m else ()):
            if k in q: return q[k]
    return coord
def walk_exact(a, b):
    """Minutes to walk from call a (getting off) to call b (boarding), as the app estimates them."""
    if a["id"] and a["id"] == b["id"] and a["quay"] and a["quay"].upper() == (b["quay"] or "").upper(): return 0.0
    pa, pb = pos(a["id"], a["coord"], a["quay"]), pos(b["id"], b["coord"], b["quay"])
    if not pa or not pb: return None
    m = hav(pa, pb) * DETOUR / SPEED
    return max(1.0 if a["id"] == b["id"] else 0.5, m)
shown = lambda m: 0 if m <= 0.05 else max(1, round(m))

def best_possible(run1, run2, ride1, ride2, need):
    """Every (get off, board) pair the same two vehicles allow, comfortable; the shortest walk."""
    c1 = run1["calls"]; i1 = next(n for n, c in enumerate(c1) if c["this"])
    c2 = run2["calls"]; i2 = next(n for n, c in enumerate(c2) if c["this"])
    a1 = next((n for n in range(i1 + 1, len(c1)) if c1[n]["id"] == str(ride1["toStop"]["id"])), None)
    b2end = next((n for n in range(i2 + 1, len(c2)) if c2[n]["id"] == str(ride2["toStop"]["id"])), None)
    if a1 is None or b2end is None: return None
    best = None
    for x in range(i1 + 1, len(c1)):
        X = c1[x]; tx = X["arr"] or X["dep"]
        if tx is None: continue
        for y in range(0, b2end):
            Y = c2[y]; ty = Y["dep"]
            if ty is None: continue
            w = walk_exact(X, Y)
            if w is None: continue
            if math.floor((ty - (tx + w * 60000)) / 60000) < need: continue
            cand = (shown(w), w, x - a1, y - i2, X["name"], X["quay"], Y["name"], Y["quay"])
            if best is None or cand[:2] < best[:2]: best = cand
    return best and {"walk": best[0], "exact": round(best[1], 2), "off_shift": best[2], "board_shift": best[3],
                     "off": f'{best[4]} {best[5]}'.strip(), "board": f'{best[6]} {best[7]}'.strip()}

# ---------------- the app ----------------
HOOK = ("  window.__audit = () => journeyBase.slice(0, 8).map(j => ({ key: j.key, enriched: !!j._enriched, stayOns: j.stayOns || null,"
        " raw: tripConnections(planOf(j)).map(c => ({ walk: c.walk, slack: c.slack, cur: c.cur, next: c.next })),"
        " fin: tripConnections(planOf(withStayOn(j))).map(c => ({ walk: c.walk, slack: c.slack, cur: c.cur, next: c.next })) }));\n")
def add_hook():
    p = ROOT / "prototypes/sprint-09-my-places/index.html"; s = p.read_text()
    anchor = "  // Journeys between two places (one part of the trip)"
    assert s.count(anchor) == 1
    s = s.replace(anchor, HOOK + anchor)
    if os.environ.get("DEBUG"):   # served copy only: why each candidate place was kept or left
        a = "      if (slack < need || min > limit) return;"
        assert s.count(a) == 1
        s = s.replace(a, "      (window.__dbg = window.__dbg || []).push({ cur: cur.label, nxt: next.label, x: s.name, xp: s.platform, y: y ? y.name : board ? 'earlier:' + s.name : next.from.name, yp: yPlat, min: +min.toFixed(2), slack, need, limit: +limit.toFixed(2) });\n" + a)
        b = "    pairs.sort("
        assert s.count(b) == 1
        s = s.replace(b, "    (window.__dbg = window.__dbg || []).push({ cur: cur.label, nxt: next.label, d0: Math.round(d0), base: +base.toFixed(2), cwalk: c.walk, early: early.map(e => e.s.name), via: (next.via || []).map(v => v.name), pairs: pairs.map(p => [p.x.s.name, p.y.name, Math.round(distanceM(p.x.s.coord, p.y.coord))]) });\n" + b)
    p.write_text(s)

def run_app(pairs):
    dumps = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for src in SOURCES:
            for t0 in TIMES:
                for a, z in pairs:
                    ctx = b.new_context(locale="fr-CH", timezone_id="Europe/Zurich", viewport={"width": 390, "height": 900})
                    pg = ctx.new_page(); state = {"inflight": 0, "last": time.time(), "fail": 0, "req": 0}
                    def on_req(r):
                        if "openstreetmap" in r.url or "cdnjs" in r.url: return
                        state["inflight"] += 1; state["req"] += 1; state["last"] = time.time()
                    def on_done(r, failed=False):
                        if "openstreetmap" in r.url or "cdnjs" in r.url: return
                        state["inflight"] -= 1; state["last"] = time.time()
                        resp = None if failed else r.response()
                        if failed or (resp and resp.status >= 400):
                            state["fail"] += 1
                            k = f'{r.url.split("/")[2]} {"failed" if failed else resp.status}'
                            state.setdefault("codes", {})[k] = state.setdefault("codes", {}).get(k, 0) + 1
                    pg.on("request", on_req); pg.on("requestfinished", on_done); pg.on("requestfailed", lambda r: on_done(r, True))
                    pg.clock.install(time=t0.timestamp())
                    pg.goto(PAGE)
                    store = {"tab": "journey", "lang": "fr", "settings": {"footMaxMin": 0, "realWalk": False},
                             "journey:from": a, "journey:to": z}
                    if src == "ojp": store["ojpKey"] = TOKEN
                    pg.evaluate("s => { localStorage.clear(); for (const [k, v] of Object.entries(s)) localStorage.setItem('tpp:' + k, JSON.stringify(v)); }", store)
                    pg.reload(); pg.click("#searchJourney")
                    t_start = time.time(); res = None
                    try:
                        pg.wait_for_selector("#journeyList .jr", timeout=60000)
                        while time.time() - t_start < 150:
                            pg.wait_for_timeout(1000)
                            d = pg.evaluate("window.__audit()")
                            if d and all(j["enriched"] for j in d) and state["inflight"] <= 0 and time.time() - state["last"] > 4:
                                res = d; break
                        res = res or pg.evaluate("window.__audit()")
                        if os.environ.get("DEBUG"):
                            for e in pg.evaluate("window.__dbg || []"): print("    DBG", json.dumps(e, ensure_ascii=False))
                    except Exception as e:
                        print("  app error", a["name"], "→", z["name"], src, e)
                    if state.get("codes"): print("    failed requests:", state["codes"], flush=True)
                    dumps.append({"src": src, "at": t0.isoformat(), "from": a["name"], "to": z["name"], "journeys": res or [],
                                  "requests": state["req"], "failed_requests": state["fail"], "secs": round(time.time() - t_start)})
                    print(f'  {src:8} {t0:%H:%M} {a["name"]} → {z["name"]}: {len(res or [])} journeys, {state["req"]} requests, {state["fail"]} failed, {round(time.time() - t_start)} s', flush=True)
                    ctx.close()
                    time.sleep(25 if src == "ojp" else 1)   # the OJP key's per-minute limit
        b.close()
    return dumps

def audit(dumps):
    rows = []
    for d in dumps:
        for jn, j in enumerate(d["journeys"]):
            if len(j["raw"]) != len(j["fin"]): rows.append({"src": d["src"], "case": f'{d["from"]} → {d["to"]} {d["at"][11:16]} #{jn}', "verdict": "STRUCTURE"}); continue
            for n, (r, f) in enumerate(zip(j["raw"], j["fin"])):
                cur, nxt = r["cur"], r["next"]
                row = {"src": d["src"], "case": f'{d["from"]} → {d["to"]} {d["at"][11:16]} #{jn}',
                       "change": f'{cur["label"]} {cur["toStop"]["name"]} {cur.get("arrPlatform") or ""} → {nxt["label"]} {nxt["from"]["name"]} {nxt.get("platform") or ""}',
                       "api_walk": r["walk"], "app_walk": f["walk"], "app_slack": f["slack"],
                       "app_change": f'{f["cur"]["toStop"]["name"]} {f["cur"].get("arrPlatform") or ""} → {f["next"]["from"]["name"]} {f["next"].get("platform") or ""}'}
                if f["slack"] < 0 <= r["slack"]: row["verdict"] = "REGRESSION_MISSED_CHANGE"
                elif f["walk"] > r["walk"]: row["verdict"] = "REGRESSION_MORE_WALK"
                run1, run2 = find_run(cur), find_run(nxt)
                if not run1 or not run2:
                    row.setdefault("verdict", "UNVERIFIABLE"); row["why"] = "run not found" + (" (1st)" if not run1 else "") + (" (2nd)" if not run2 else ""); rows.append(row); continue
                need = max(1, min(r["slack"], COMFORT))
                def est(ride_a, ride_b, info=None):
                    X = next((c for c in run1["calls"][[c["this"] for c in run1["calls"]].index(True) + 1:] if c["id"] == str(ride_a["toStop"]["id"])), None)
                    Y = next((c for c in run2["calls"] if c["id"] == str(ride_b["from"]["id"])), None)
                    if info is not None: info.update(X=bool(X), Y=bool(Y), Xc=bool(X and X["coord"]), Yc=bool(Y and Y["coord"]),
                                                     Xq=bool(X and str(X["id"]) in QS), Yq=bool(Y and str(Y["id"]) in QS))
                    if not X or not Y: return None
                    w = walk_exact(dict(X, quay=ride_a.get("arrPlatform") or X["quay"]), dict(Y, quay=ride_b.get("platform") or Y["quay"]))
                    return None if w is None else shown(w)
                info = {}
                row["api_est"], row["app_est"] = est(cur, nxt, info), est(f["cur"], f["next"])
                unchanged = str(f["cur"]["toStop"]["id"]) == str(cur["toStop"]["id"]) and str(f["next"]["from"]["id"]) == str(nxt["from"]["id"])
                best = best_possible(run1, run2, cur, nxt, need)
                if not best:
                    if row["api_est"] is None: row.setdefault("verdict", "UNVERIFIABLE"); row["why"] = f"no position {info}"
                    elif unchanged: row.setdefault("verdict", "TIGHT_UNCHANGED")
                    else: row.setdefault("verdict", "CHANGED_TIGHT"); row["why"] = "app moved a change the check finds too tight"
                    rows.append(row); continue
                row["best"] = best
                if row["app_est"] is not None and row["api_est"] is not None and row["app_est"] > row["api_est"]: row.setdefault("verdict", "REGRESSION_WORSE_PLACE")
                if "verdict" not in row:
                    if row["app_est"] is None:
                        row["verdict"], row["why"] = "UNVERIFIABLE", "app's change stops not on the runs"
                    elif row["app_est"] - best["walk"] >= 1:
                        why = []
                        if r["walk"] < 1: why.append("no API walk (not looked at)")
                        if best["off_shift"] > 5: why.append(f'off {best["off_shift"]} stops later (window 5)')
                        if best["off_shift"] < -5: why.append(f'off {-best["off_shift"]} stops earlier (window 5)')
                        if best["board_shift"] < -4: why.append(f'board {-best["board_shift"]} stops earlier (window 4)')
                        if best["board_shift"] > 5: why.append(f'board {best["board_shift"]} stops later (window 5)')
                        if best["off_shift"] and best["board_shift"] < 0 and best["off_shift"] < 0: why.append("off earlier + board earlier together (not looked at)")
                        row["verdict"], row["why"] = "MISSED", "; ".join(why) or "within the windows: data or rule"
                    elif row["app_est"] < row["api_est"]: row["verdict"] = "IMPROVED_OPTIMAL"
                    else: row["verdict"] = "OPTIMAL"
                rows.append(row)
    return rows

if __name__ == "__main__":
    pairs = []
    for a, z in PAIRS:
        A, Z = resolve(a), resolve(z)
        print(f"{a} → {A and A['name']} ({A and A['id']}) | {z} → {Z and Z['name']} ({Z and Z['id']})", flush=True)
        if A and Z: pairs.append((A, Z))
    add_hook()
    dumps = run_app(pairs)
    (OUT / "app.json").write_text(json.dumps(dumps, ensure_ascii=False))
    rows = audit(dumps)
    (OUT / "rows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    from collections import Counter
    cnt = Counter((r["src"], r["verdict"]) for r in rows)
    print("\n=== SUMMARY ===")
    for src in SOURCES:
        tot = sum(v for (s, _), v in cnt.items() if s == src)
        print(src, tot, "changes:", {v: c for (s, v), c in sorted(cnt.items()) if s == src})
    print("searches:", len(dumps), "| without journeys:", sum(1 for d in dumps if not d["journeys"]),
          "| app requests failed:", sum(d["failed_requests"] for d in dumps), "| audit OJP calls:", STATS)
    for r in rows:
        if r["verdict"] not in ("OPTIMAL", "IMPROVED_OPTIMAL"):
            print(f'{r["verdict"]:24} {r["src"]:8} {r["case"]} | {r.get("change", "")} | API {r.get("api_walk")} (est {r.get("api_est")}) app {r.get("app_walk")} (est {r.get("app_est")}) '
                  f'best {r.get("best", {}).get("walk")} ({r.get("best", {}).get("off", "")} → {r.get("best", {}).get("board", "")}) | app: {r.get("app_change", "")} | {r.get("why", "")}')
    print("\n=== IMPROVED (sample) ===")
    for r in [r for r in rows if r["verdict"] == "IMPROVED_OPTIMAL"][:30]:
        print(f'{r["src"]:8} {r["case"]} | {r["change"]} | API {r["api_walk"]} (est {r["api_est"]}) → app {r["app_walk"]} (est {r["app_est"]}) at {r["app_change"]}')
    big = [r for r in rows if r.get("api_walk") is not None and r.get("api_est") is not None and r["api_walk"] - r["api_est"] >= 3]
    print(f"\n=== API change times much longer than the distance ({len(big)} changes, sample) ===")
    for r in big[:15]: print(f'{r["src"]:8} {r["change"]} | API {r["api_walk"]} min, distance estimate {r["api_est"]} min')
