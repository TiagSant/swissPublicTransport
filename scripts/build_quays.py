#!/usr/bin/env python3
"""Build assets/quays.js: GPS position of every platform (quay) in the Unireso area, and the same for the whole of
Switzerland in small parts, one per block of stop numbers (assets/quays-ch/8587.js, …: the first 4 digits of the
stop id), loaded by the app for the stops of a journey only.

Source: ATLAS traffic points (official Swiss registry of public transport stops), published on
opentransportdata.swiss under "Open use. Must provide the source.". Each boarding platform has the
official designation shown on departure boards ("A"…"Z" at TPG stops, track numbers at stations)
and belongs to a service point whose number is the stop id used by transport.opendata.ch.

Usage:
    python scripts/build_quays.py assets/quays.js            # download the current dataset
    python scripts/build_quays.py assets/quays.js local.csv  # use a local CSV (tests)

Standard library only, so it runs as-is on a GitHub Actions runner.
"""
import csv
import datetime as dt
import gzip
import io
import json
import re
import sys
import urllib.request
import zipfile

SOURCES = [
    # Stable permalink first, then the resource URL listed on opendata.swiss (traffic-point-v2, actual date)
    "https://data.opentransportdata.swiss/dataset/traffic-point-v2/resource_permalink/actual-date-world-traffic-point.csv",
    "https://data.opentransportdata.swiss/de/dataset/b06d90be-91c6-440e-ab97-09f579d2fad0/resource/"
    "928cb136-d598-4ac5-b4af-8988dd9c3d83/download/actual-date-world-traffic-point.csv",
]
# Same area as the app's ZONE: Geneva, Nyon district, and the French Léman Express area
ZONE = {"lat_min": 45.85, "lat_max": 46.50, "lon_min": 5.80, "lon_max": 6.65}

# Column names differ slightly between dataset versions: match case-insensitively against candidates
COLUMNS = {
    "sloid": ["sloid"],
    "number": ["servicepointnumber", "servicepointnumberlong", "number"],
    "number_short": ["servicepointnumbershort", "numbershort"],
    "country": ["uiccountrycode", "servicepointuiccountrycode", "countrycode"],
    "designation": ["designation"],
    "designation_op": ["designationoperational"],
    "type": ["trafficpointelementtype", "type"],
    "lat": ["wgs84north", "lat", "latitude"],
    "lon": ["wgs84east", "lon", "longitude"],
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "swissPublicTransport/quays (+github.com/TiagSant)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def to_text(raw):
    """The dataset is served as CSV, sometimes zipped or gzipped."""
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            raw = z.read(name)
    elif raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8-sig")


def index_columns(header):
    lower = {h.strip().lower(): i for i, h in enumerate(header)}
    found = {}
    for key, candidates in COLUMNS.items():
        for c in candidates:
            if c in lower:
                found[key] = lower[c]
                break
    missing = [k for k in ("designation", "lat", "lon") if k not in found]
    if missing or not ({"sloid", "number", "number_short"} & found.keys()):
        raise SystemExit(f"Unexpected CSV header, missing {missing or 'a stop number column'}: {header[:30]}")
    return found


def stop_id(row, col):
    """7-digit stop id as used by transport.opendata.ch (e.g. 8587387 for Genève, Bel-Air)."""
    def cell(k):
        return row[col[k]].strip() if k in col and col[k] < len(row) else ""
    number = re.sub(r"\D", "", cell("number"))
    if len(number) == 7:
        return number
    short = re.sub(r"\D", "", cell("number_short"))
    if not short:
        m = re.match(r"ch:1:sloid:(\d+)", cell("sloid"))
        short = m.group(1) if m else ""
    if short:
        country = re.sub(r"\D", "", cell("country")) or "85"
        return country + short.zfill(5)
    return number or None


def parse_float(s):
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def build(text):
    sample = text[:5000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = csv.reader(io.StringIO(text), delimiter=delimiter)
    col = index_columns(next(rows))
    stops, everywhere, kept, seen_types = {}, {}, 0, {}
    for row in rows:
        if not row:
            continue
        kind = row[col["type"]].strip().upper() if "type" in col else ""
        seen_types[kind] = seen_types.get(kind, 0) + 1
        if kind and kind != "BOARDING_PLATFORM":
            continue  # BOARDING_AREA = a whole zone, not a platform with a letter
        lat, lon = parse_float(row[col["lat"]]), parse_float(row[col["lon"]])
        if lat is None or lon is None:
            continue
        sid = stop_id(row, col)
        names = {row[col["designation"]].strip()}
        if "designation_op" in col:
            names.add(row[col["designation_op"]].strip())
        names.discard("")
        if not sid or not names:
            continue
        for n in sorted(names):   # a stable order: the same data gives the same files
            everywhere.setdefault(sid, {}).setdefault(n, [round(lat, 6), round(lon, 6)])
        if not (ZONE["lat_min"] <= lat <= ZONE["lat_max"] and ZONE["lon_min"] <= lon <= ZONE["lon_max"]):
            continue
        quays = stops.setdefault(sid, {})
        for n in sorted(names):
            quays.setdefault(n, [round(lat, 6), round(lon, 6)])
        kept += 1
    return stops, kept, seen_types, everywhere


def write_js(path, stops, source):
    payload = {
        "generated": dt.date.today().isoformat(),
        "source": source,
        "licence": "ATLAS traffic points, opentransportdata.swiss — open use, source must be cited",
        "stops": dict(sorted(stops.items())),
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write("/* Generated by scripts/build_quays.py — do not edit by hand. */\n")
        f.write("window.QUAYS = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")


def write_parts(folder, everywhere):
    """One file per block of stop numbers: window.QUAYS_CH["8587"] = {stop id: {platform: [lat, lon]}}."""
    import os
    os.makedirs(folder, exist_ok=True)
    parts = {}
    for sid, q in everywhere.items():
        if re.fullmatch(r"\d{7}", sid):
            parts.setdefault(sid[:4], {})[sid] = q
    for name in os.listdir(folder):   # blocks that disappeared
        if name.endswith(".js") and name[:-3] not in parts:
            os.remove(os.path.join(folder, name))
    for key, stops in parts.items():
        with open(os.path.join(folder, key + ".js"), "w", encoding="utf-8") as f:
            f.write("/* Generated by scripts/build_quays.py from ATLAS traffic points (opentransportdata.swiss) — do not edit. */\n")
            f.write(f"(window.QUAYS_CH = window.QUAYS_CH || {{}})[{json.dumps(key)}] = "
                    + json.dumps(dict(sorted(stops.items())), ensure_ascii=False, separators=(",", ":")) + ";\n")
    return parts


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/quays.js"
    if len(sys.argv) > 2:
        source = sys.argv[2]
        text = to_text(open(source, "rb").read())
    else:
        text, source, errors = None, None, []
        for url in SOURCES:
            try:
                text, source = to_text(fetch(url)), url
                break
            except Exception as e:  # try the next URL
                errors.append(f"{url}: {e}")
        if text is None:
            raise SystemExit("Download failed:\n" + "\n".join(errors))
    print("header:", text.split("\n", 1)[0][:400])
    stops, kept, types, everywhere = build(text)
    print(f"element types: {types}")
    print(f"kept {kept} platforms at {len(stops)} stops in the Unireso area")
    for sid in ("8587387", "8587057", "8587418", "8501008", "8516155"):  # Bel-Air, Cornavin, Les Esserts, Genève, Pont-Rouge
        print(f"  {sid}: {stops.get(sid)}")
    if len(stops) < 50:
        raise SystemExit("Too few stops — refusing to overwrite the data file")
    write_js(out, stops, source)
    print("written", out)
    import os
    folder = os.path.join(os.path.dirname(out) or ".", "quays-ch")
    parts = write_parts(folder, everywhere)
    print(f"written {folder}: {len(everywhere)} stops in {len(parts)} parts")
    for sid in ("8507000", "8505000", "8504221"):  # Bern, Luzern, Neuchâtel
        print(f"  {sid}: {everywhere.get(sid)}")


if __name__ == "__main__":
    main()
