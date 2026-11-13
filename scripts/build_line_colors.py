#!/usr/bin/env python3
"""Build assets/line-colors-ch.js: line colours of Swiss public transport operators.

Sources
- Line colours: OpenStreetMap route relations in Switzerland (tags ref, colour, operator, network), via the
  Overpass API. © OpenStreetMap contributors, ODbL 1.0 — the generated file is under ODbL too.
- Operators: the official list of Swiss transport companies (ATLAS business organisations / transport companies,
  opentransportdata.swiss), to link each OSM operator to the company number used by OJP (OperatorRef "ojp:881").

The colours collected by hand from the operators' own websites (assets/line-colors.js: TPG, Léman Express,
Mouettes genevoises) keep priority in the app; this file covers the rest of Switzerland.

Usage:
    python scripts/build_line_colors.py assets/line-colors-ch.js [report.json]
Standard library only (GitHub Actions runner).
"""
import csv
import collections
import datetime as dt
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
import gzip

UA = {"User-Agent": "swissPublicTransport/line-colors (+github.com/TiagSant/swissPublicTransport)"}
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
QUERY = """[out:json][timeout:600];
area["ISO3166-1"="CH"][admin_level=2]->.ch;
relation(area.ch)["type"="route"]["route"~"^(bus|trolleybus|tram|light_rail|subway|ferry|funicular|aerialway|monorail|train)$"]["ref"];
out tags;"""
CKAN = "https://data.opentransportdata.swiss/api/3/action/"
COMPANY_PACKAGES = ["business-organisations", "transport-companies", "business-organisation", "transport-company"]

# OSM operator names that do not match the official names well enough → official abbreviation
ALIASES = {
    "tl": "tl", "transports publics de la region lausannoise": "tl", "transports lausannois": "tl",
    "tpg": "TPG", "transports publics genevois": "TPG",
    "postauto": "PAG", "postauto ag": "PAG", "postauto schweiz": "PAG", "carpostal": "PAG", "autopostale": "PAG", "postbus": "PAG",
    "vbz": "VBZ", "verkehrsbetriebe zurich": "VBZ", "bvb": "BVB", "basler verkehrs-betriebe": "BVB",
    "bernmobil": "BERNMOBIL", "stadtische verkehrsbetriebe bern": "BERNMOBIL", "vbl": "VBL", "verkehrsbetriebe luzern": "VBL",
    "tpf": "TPF", "transports publics fribourgeois": "TPF", "tpn": "TPN", "transports publics de la region nyonnaise": "TPN",
    "transn": "TRN", "trn": "TRN", "travys": "TRAVYS", "mbc": "MBC", "vmcv": "VMCV", "tpl": "TPL", "trasporti pubblici luganesi": "TPL",
    "blt": "BLT", "blt baselland transport": "BLT", "stadtbus winterthur": "SBW", "vbsg": "VBSG", "verkehrsbetriebe st. gallen": "VBSG",
    "vbg": "VBG", "verkehrsbetriebe glattal": "VBG", "sbb": "SBB", "sbb cff ffs": "SBB", "bls": "BLS", "rhb": "RhB", "rhatische bahn": "RhB",
    "mgb": "MGB", "matterhorn gotthard bahn": "MGB", "sob": "SOB", "zb": "ZB", "zentralbahn": "ZB", "tmr": "TMR", "mob": "MOB",
    "cgn": "CGN", "mouettes genevoises": "MGN", "sgv": "SGV", "zsg": "ZSG", "bls schiff": "BLS-S", "urh": "URh",
    "aare seeland mobil": "ASM", "asm": "ASM", "regiobus": "RBS", "rbs": "RBS", "auto ag uri": "AAGU", "ar": "AAR",
}
COLOUR_NAMES = {"red": "#FF0000", "blue": "#0000FF", "green": "#008000", "yellow": "#FFFF00", "black": "#000000", "white": "#FFFFFF",
                "orange": "#FFA500", "purple": "#800080", "brown": "#A52A2A", "grey": "#808080", "gray": "#808080", "pink": "#FFC0CB"}
MODE = {"bus": "bus", "trolleybus": "bus", "tram": "tram", "light_rail": "tram", "subway": "metro", "ferry": "ship",
        "funicular": "funicular", "aerialway": "cableway", "monorail": "metro", "train": "train"}


def fetch(url, data=None, timeout=300):
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[()\[\],.;:/]", " ", s)
    s = re.sub(r"\b(sa|ag|gmbh|s a|a g|spa|cie|co)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def colour(value):
    v = str(value or "").strip()
    if not v:
        return None
    if v.lower() in COLOUR_NAMES:
        return COLOUR_NAMES[v.lower()]
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", v)
    if m:
        return "#" + m.group(1).upper()
    m = re.fullmatch(r"#?([0-9a-fA-F]{3})", v)
    if m:
        return "#" + "".join(c * 2 for c in m.group(1)).upper()
    return None


def text_on(bg):
    """Black or white text, whichever contrasts more (WCAG relative luminance)."""
    r, g, b = (int(bg[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#000000" if (L + 0.05) / 0.05 > 1.05 / (L + 0.05) else "#FFFFFF"


# ---------- Official companies ----------
def companies(report):
    """number → {abbr, name}. Tries the ATLAS datasets on opentransportdata.swiss (CKAN)."""
    for pkg in COMPANY_PACKAGES:
        try:
            info = json.loads(fetch(CKAN + "package_show?id=" + pkg, timeout=60))
        except Exception as e:  # noqa: BLE001 — try the next name
            report.setdefault("ckan_errors", []).append(f"{pkg}: {e}")
            continue
        resources = info.get("result", {}).get("resources", [])
        report.setdefault("ckan_resources", {})[pkg] = [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")} for r in resources]
        csvs = [r for r in resources if "csv" in (r.get("format") or "").lower() or str(r.get("url", "")).lower().endswith((".csv", ".zip"))]
        csvs.sort(key=lambda r: ("actual" not in str(r.get("url", "")).lower(), str(r.get("name"))))
        for r in csvs:
            try:
                raw = fetch(r["url"], timeout=120)
            except Exception as e:  # noqa: BLE001
                report.setdefault("ckan_errors", []).append(f"{r['url']}: {e}")
                continue
            if raw[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    raw = z.read(next(n for n in z.namelist() if n.lower().endswith(".csv")))
            elif raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8-sig", "replace")
            delim = ";" if text[:3000].count(";") > text[:3000].count(",") else ","
            rows = list(csv.reader(io.StringIO(text), delimiter=delim))
            if not rows:
                continue
            head = [h.strip().lower() for h in rows[0]]
            report.setdefault("company_headers", {})[r["url"]] = head[:40]
            pick = lambda *names: next((head.index(n) for n in names if n in head), None)
            i_num = pick("number", "transportcompanynumber", "organisationnumber", "tunumber", "nummer")
            i_abbr = pick("abbreviation", "abbreviationde", "abbreviationfr", "abkuerzung")
            i_name = pick("businessregistername", "descriptionde", "description", "descriptionfr", "name", "designation")
            if i_num is None or i_abbr is None:
                continue
            out = {}
            for row in rows[1:]:
                if len(row) <= max(i_num, i_abbr):
                    continue
                num = re.sub(r"\D", "", row[i_num])
                if not num:
                    continue
                out[str(int(num))] = {"abbr": row[i_abbr].strip(), "name": row[i_name].strip() if i_name is not None and i_name < len(row) else ""}
            if out:
                report["companies_source"] = r["url"]
                report["companies"] = len(out)
                return out
    return {}


# ---------- OpenStreetMap ----------
def osm_routes(report):
    for url in OVERPASS:
        for attempt in range(2):
            try:
                raw = fetch(url, data=urllib.parse.urlencode({"data": QUERY}).encode(), timeout=900)
                data = json.loads(raw)
                report["overpass"] = url
                return [e.get("tags", {}) for e in data.get("elements", [])]
            except Exception as e:  # noqa: BLE001
                report.setdefault("overpass_errors", []).append(f"{url}: {e}")
                time.sleep(30)
    raise SystemExit("Overpass unreachable: " + json.dumps(report.get("overpass_errors")))


def build(routes, comps, report):
    by_abbr = collections.defaultdict(list)
    by_name = {}
    for num, c in comps.items():
        by_abbr[norm(c["abbr"])].append(num)
        if c["name"]:
            by_name[norm(c["name"])] = num

    def resolve(op):
        n = norm(op)
        if not n:
            return None
        alias = ALIASES.get(n)
        for cand in ([norm(alias)] if alias else []) + [n]:
            if cand in by_abbr:
                return sorted(by_abbr[cand], key=int)[0]
        if n in by_name:
            return by_name[n]
        for name, num in by_name.items():     # "Transports publics de la région lausannoise SA" ⊃ "…lausannoise"
            if len(n) >= 6 and (n in name or name in n):
                return num
        return None

    lines = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    unmatched, no_colour, used = collections.Counter(), 0, 0
    modes = collections.defaultdict(dict)
    for tags in routes:
        bg = colour(tags.get("colour"))
        ref = str(tags.get("ref", "")).strip()
        if not bg or not ref or len(ref) > 8:
            no_colour += 1
            continue
        ops = [o.strip() for o in re.split(r"[;]", tags.get("operator", "")) if o.strip()] or [tags.get("network", "")]
        key = None
        for op in ops:
            key = resolve(op)
            if key:
                break
        if not key and tags.get("network"):
            key = resolve(tags["network"])
        if not key:
            unmatched[tags.get("operator") or tags.get("network") or "?"] += 1
            continue
        fg = colour(tags.get("colour:text") or tags.get("text_colour")) or text_on(bg)
        lines[key][ref.lower()][(bg, fg)] += 1
        modes[key][ref.lower()] = MODE.get(tags.get("route"), "other")
        used += 1

    operators = {}
    for num, refs in sorted(lines.items(), key=lambda kv: int(kv[0])):
        c = comps.get(num, {})
        operators[num] = {"abbr": c.get("abbr", ""), "name": c.get("name", ""),
                          "lines": {ref: [*cnt.most_common(1)[0][0], "pill"] for ref, cnt in sorted(refs.items())}}
    report.update(routes=len(routes), used=used, without_colour_or_ref=no_colour,
                  operators=len(operators), lines=sum(len(o["lines"]) for o in operators.values()),
                  unmatched_operators=unmatched.most_common(60),
                  per_operator={f'{num} {o["abbr"]}': len(o["lines"]) for num, o in operators.items()})
    return operators


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/line-colors-ch.js"
    report_path = sys.argv[2] if len(sys.argv) > 2 else None
    report = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    comps = companies(report)
    routes = osm_routes(report)
    operators = build(routes, comps, report)
    aliases = {}
    for num, c in comps.items():   # abbreviation → number, for transport.opendata.ch ("operator": "TPG")
        if c["abbr"]:
            aliases.setdefault(c["abbr"].lower(), num)
    payload = {"generated": report["generated"], "source": "OpenStreetMap contributors (ODbL 1.0); operators: ATLAS, opentransportdata.swiss",
               "operators": operators, "aliases": {k: v for k, v in sorted(aliases.items()) if v in operators}}
    with open(out, "w", encoding="utf-8") as f:
        f.write("/*\n * Line colours of Swiss public transport, generated by scripts/build_line_colors.py — do not edit by hand.\n"
                " * Colours: © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright).\n"
                " * Operators: ATLAS business organisations, opentransportdata.swiss.\n"
                " * operators: company number (OJP OperatorRef) → { abbr, name, lines: { label (lower case): [background, text, shape] } }\n */\n")
        f.write("window.LINE_COLORS_CH = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_operator", "ckan_resources", "company_headers")}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
