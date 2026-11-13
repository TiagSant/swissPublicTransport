"""US-50 with official data (OJP): a light departure board (no onward calls) rebuilds each run's next stops from
the remembered pattern — now with their times AND positions, so the app can tell where the vehicle goes next.
Real answers: tests/fixtures/ojp/app_ser_esserts_full.xml, then app_ser_esserts_light.xml."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "tests/fixtures/ojp"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROME_PATH")); pg = b.new_page()
    pg.goto((ROOT / "prototypes/sprint-09-my-places/index.html").as_uri())
    r = pg.evaluate("""([full, light]) => {
      const pat = new Map();
      const a = OJP_ADAPTER.toStationboard(full, '8587418', pat), l = OJP_ADAPTER.toStationboard(light, '8587418', pat);
      const next = j => j.passList.slice(1);
      const withPos = b => b.stationboard.filter(j => next(j).length).map(j => next(j).every(x => x.station.coordinate && x.station.coordinate.x && x.arrival));
      const quays = b => b.stationboard.flatMap(j => next(j)).filter(x => x.platform).length;
      return { full: withPos(a), light: withPos(l), patterns: pat.size, fullQ: quays(a), lightQ: quays(l) };
    }""", [(FX / "app_ser_esserts_full.xml").read_text(), (FX / "app_ser_esserts_light.xml").read_text()])
    assert r["patterns"] > 0 and r["full"] and all(r["full"]), r
    assert r["light"] and all(r["light"]), r
    assert r["fullQ"] > 0 and r["lightQ"] > 0, (r["fullQ"], r["lightQ"])   # the next stops' platforms too
    print(f"ojp         → {len(r['light'])} runs on the light board with their next stops' times and positions; {r['lightQ']} next stops with their platform")
    b.close()
print("OK")
