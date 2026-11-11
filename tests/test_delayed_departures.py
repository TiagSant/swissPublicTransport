"""BUG-01 (#19): delayed departures must stay on the board until they actually leave.

The mock reproduces the real API window: /stationboard only returns journeys whose *scheduled*
departure is at or after `datetime` (default: now). Sprint 3 is run first to reproduce the bug.
"""
import os, json, datetime as dt
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = {"sprint3": (ROOT / "prototypes/sprint-03-habitudes/index.html").as_uri(),
         "sprint4": (ROOT / "prototypes/sprint-04-identity/index.html").as_uri(),
         "sprint5": (ROOT / "prototypes/sprint-05-platforms/index.html").as_uri()}
tz = ZoneInfo("Europe/Zurich"); now = dt.datetime.now(tz).replace(second=0, microsecond=0)
fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%S%z")
HERE = {"id": "8587057", "name": "Genève, Bel-Air"}

def dep(num, sched_min, prognosis_min=None, delay=None):
    s = now + dt.timedelta(minutes=sched_min)
    p = now + dt.timedelta(minutes=prognosis_min) if prognosis_min is not None else None
    return {"category": "B", "number": num, "to": f"Line {num} terminus", "operator": "TPG",
            "passList": [{"station": HERE}, {"station": {"id": "1" + num, "name": "Next"}}],
            "stop": {"station": HERE, "departure": fmt(s), "departureTimestamp": int(s.timestamp()), "delay": delay,
                     "prognosis": {"departure": fmt(p) if p else None}}}

JOURNEYS = [
    dep("3", -5, prognosis_min=3, delay=8),     # A: scheduled 5 min ago, live +8 → still coming: SHOW
    dep("5", -5),                               # B: scheduled 5 min ago, no live data → gone: HIDE
    dep("7", -4, prognosis_min=None, delay=9),  # C: delay known, no prognosis time → real = sched + 9: SHOW
    dep("19", -10, prognosis_min=-3, delay=7),  # D: live, but already left 3 min ago: HIDE
    dep("10", 2, prognosis_min=2, delay=0),     # E: on time, upcoming: SHOW
    dep("22", 6),                               # F: no live data, upcoming: SHOW
]
requests = []
def handle(route):
    url = route.request.url; requests.append(url)
    if "/stationboard" in url:
        q = parse_qs(urlparse(url).query)
        start = dt.datetime.strptime(q["datetime"][0], "%Y-%m-%d %H:%M").replace(tzinfo=tz) if "datetime" in q \
            else dt.datetime.now(tz).replace(second=0, microsecond=0)
        rows = [j for j in JOURNEYS if j["stop"]["departureTimestamp"] >= start.timestamp()]   # scheduled-time window
        body = {"station": HERE, "stationboard": rows[: int(q.get("limit", ["40"])[0])]}
    else:
        body = {"stations": [{"id": HERE["id"], "name": HERE["name"], "coordinate": {"x": 46.2045, "y": 6.1425}, "icon": "tram"}]}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})

errors = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH"))
    shown = {}
    for name, page in PAGES.items():
        ctx = b.new_context(locale="en-US"); ctx.route("https://transport.opendata.ch/**", handle)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(page); pg.fill("#q", "Bel-Air"); pg.wait_for_selector("#results button[data-id]")
        pg.locator("#results button[data-id]").first.click(); pg.wait_for_selector(".dep")
        shown[name] = [li.get_attribute("data-dir").split("|")[1].split(">")[0] for li in pg.locator(".dep").all()]
        if name != "sprint3":
            row = pg.locator(".dep[data-dir^='bus|3>']")
            assert "+8 min" in row.inner_text(), row.inner_text()
            assert row.locator(".when b").inner_text() in ("2′", "3′"), row.locator(".when b").inner_text()
            c = pg.locator(".dep[data-dir^='bus|7>']").inner_text(); assert "+9 min" in c, c
        ctx.close()
    b.close()

print("sprint3 (bug):  ", shown["sprint3"])
print("sprint4 (fixed):", shown["sprint4"]); print("sprint5 (fixed):", shown["sprint5"])
assert "3" not in shown["sprint3"], "mock should reproduce the bug on Sprint 3"
assert shown["sprint4"] == ["7", "10", "3", "22"] or sorted(shown["sprint4"]) == ["10", "22", "3", "7"], shown["sprint4"]
assert "5" not in shown["sprint4"] and "19" not in shown["sprint4"]
assert shown["sprint5"] == shown["sprint4"]
board = [u for u in requests if "/stationboard" in u]
q4 = parse_qs(urlparse(board[-1]).query)
lookback = (now - dt.datetime.strptime(q4["datetime"][0], "%Y-%m-%d %H:%M").replace(tzinfo=tz)).total_seconds() / 60
assert 29 <= lookback <= 31 and q4["limit"] == ["150"], (q4, lookback)
print(f"request: datetime {q4['datetime'][0]} (look-back {lookback:.0f} min), limit {q4['limit'][0]}")
print("errors:", errors); assert not errors
