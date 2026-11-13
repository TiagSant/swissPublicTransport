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
relation(area.ch)["type"="route"]["route"~"^(bus|trolleybus|tram|light_rail|subway|ferry|funicular|aerialway|monorail)$"]["ref"];
out tags;"""
# ATLAS business organisations: number (the OJP OperatorRef, e.g. 881) → abbreviation (e.g. TPG)
COMPANY_URLS = [
    "https://data.opentransportdata.swiss/dataset/business-organisation-v2/resource_permalink/full-business-organisation.csv",
    "https://data.opentransportdata.swiss/dataset/f0d5278e-4376-4cde-b02c-c5bf9a348673/resource/6bc140cf-42a7-4547-9fd8-09260f30de41/download/full-business-organisation.csv",
]
COMPANY_CKAN = ["https://ckan.opendata.swiss/api/3/action/package_show?id=business-organisation-v2",
                "https://opendata.swiss/api/3/action/package_show?id=business-organisation-v2"]

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
    """White text like on Swiss line badges, unless white would be hard to read (contrast below 3:1, WCAG large/bold text)."""
    r, g, b = (int(bg[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#FFFFFF" if 1.05 / (L + 0.05) >= 3 else "#000000"


# ---------- Official companies ----------
def read_csv(raw):
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            raw = z.read(next(n for n in z.namelist() if n.lower().endswith(".csv")))
    elif raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8-sig", "replace")
    delim = ";" if text[:3000].count(";") > text[:3000].count(",") else ","
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def companies(report):
    """number → abbreviation, from the ATLAS business organisations (current versions)."""
    urls = list(COMPANY_URLS)
    for api in COMPANY_CKAN:
        try:
            res = json.loads(fetch(api, timeout=60)).get("result", {}).get("resources", [])
            urls += [r.get("url") or r.get("download_url") for r in res if "full-business-organisation" in str(r.get("url") or r.get("download_url"))]
        except Exception as e:  # noqa: BLE001
            report.setdefault("company_errors", []).append(f"{api}: {e}")
    for url in urls:
        try:
            rows = read_csv(fetch(url, timeout=120))
        except Exception as e:  # noqa: BLE001
            report.setdefault("company_errors", []).append(f"{url}: {e}")
            continue
        if not rows:
            continue
        head = [h.strip().lower() for h in rows[0]]
        report["company_header"] = head[:60]
        pick = lambda *names: next((head.index(n) for n in names if n in head), None)
        i_num = pick("organisationnumber", "number", "transportcompanynumber")
        i_abbr = [i for i in (pick("abbreviationde"), pick("abbreviationfr"), pick("abbreviationit"), pick("abbreviationen"), pick("abbreviation")) if i is not None]
        i_name = pick("descriptionde", "descriptionfr", "description")
        i_to = pick("validto")
        if i_num is None or not i_abbr:
            continue
        today = dt.date.today().isoformat()
        out = {}
        for row in rows[1:]:
            if len(row) <= i_num:
                continue
            if i_to is not None and i_to < len(row) and row[i_to][:10] and row[i_to][:10] < today:
                continue   # an old version
            num = re.sub(r"\D", "", row[i_num])
            abbr = next((row[i].strip() for i in i_abbr if i < len(row) and row[i].strip()), "")
            if num and abbr:
                out[str(int(num))] = {"abbr": abbr, "name": row[i_name].strip() if i_name is not None and i_name < len(row) else ""}
        if out:
            report["companies_source"], report["companies"] = url, len(out)
            report["company_samples"] = {k: out[k] for k in ("881", "11", "199", "801", "151") if k in out}
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


def op_key(value):
    """OSM operator / network → operator abbreviation: "TPG: Globe Limo" → TPG, "BOS/wimo" → BOS, "MBC Auto" → MBC."""
    v = str(value or "").strip()
    if not v:
        return None
    alias = ALIASES.get(norm(v))
    if alias:
        return alias.upper()
    head = re.split(r"[:/;(]", v)[0].strip()
    head = re.sub(r"\s+(Auto|Bus|Schiff|Bahn)$", "", head, flags=re.I).strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{0,9}", head):
        return head.upper()
    alias = ALIASES.get(norm(head))
    return alias.upper() if alias else None


def build(routes, comps, report):
    lines = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    unmatched, skipped = collections.Counter(), 0
    for tags in routes:
        bg = colour(tags.get("colour"))
        ref = str(tags.get("ref", "")).strip()
        if not bg or not ref or len(ref) > 8:
            skipped += 1
            continue
        key = op_key(tags.get("operator")) or op_key(tags.get("network"))
        if not key:
            unmatched[tags.get("operator") or tags.get("network") or "?"] += 1
            continue
        fg = colour(tags.get("colour:text") or tags.get("text_colour")) or text_on(bg)
        lines[key][ref.lower()][(bg, fg)] += 1
    names = {}
    for num, c in comps.items():
        names.setdefault(c["abbr"].upper(), c["name"])
    # One number used in several regions (PostAuto "1" in Sion and in Frauenfeld…) with different colours: no colour
    ambiguous = collections.Counter()
    def pick(cnt):
        (best, n), total = cnt.most_common(1)[0], sum(cnt.values())
        return best if len(cnt) == 1 or n / total >= 0.75 else None
    operators = {}
    for k, v in sorted(lines.items()):
        kept = {}
        for ref, cnt in sorted(v.items()):
            best = pick(cnt)
            if best:
                kept[ref] = [*best, "pill"]
            else:
                ambiguous[k] += 1
        if kept:
            operators[k] = {"name": names.get(k, ""), "lines": kept}
    report["ambiguous_lines"] = dict(ambiguous.most_common())
    report.update(routes=len(routes), without_colour_or_ref=skipped, operators=len(operators),
                  lines=sum(len(o["lines"]) for o in operators.values()), unmatched_operators=unmatched.most_common(40),
                  per_operator={k: len(o["lines"]) for k, o in operators.items()})
    return operators


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/line-colors-ch.js"
    report_path = sys.argv[2] if len(sys.argv) > 2 else None
    report = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    comps = companies(report)
    routes = osm_routes(report)
    operators = build(routes, comps, report)
    # OJP gives the company number (OperatorRef "ojp:881"), transport.opendata.ch the abbreviation ("TPG")
    numbers = {num: c["abbr"].upper() for num, c in sorted(comps.items(), key=lambda kv: int(kv[0])) if c["abbr"].upper() in operators}
    payload = {"generated": report["generated"], "source": "OpenStreetMap contributors (ODbL 1.0); operators: ATLAS, opentransportdata.swiss",
               "operators": operators, "numbers": numbers}
    with open(out, "w", encoding="utf-8") as f:
        f.write("/*\n * Line colours of Swiss public transport, generated by scripts/build_line_colors.py — do not edit by hand.\n"
                " * Colours: © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright).\n"
                " * Operators: ATLAS business organisations, opentransportdata.swiss.\n"
                " * operators: abbreviation → { name, lines: { label (lower case): [background, text, shape] } }\n"
                " * numbers: company number (OJP OperatorRef) → abbreviation\n */\n")
        f.write("window.LINE_COLORS_CH = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n")
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in report.items() if k not in ("per_operator", "company_header")}, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
