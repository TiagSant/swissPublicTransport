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
      return { full: withPos(a), light: withPos(l), patterns: pat.size };
    }""", [(FX / "app_ser_esserts_full.xml").read_text(), (FX / "app_ser_esserts_light.xml").read_text()])
    assert r["patterns"] > 0 and r["full"] and all(r["full"]), r
    assert r["light"] and all(r["light"]), r
    print(f"ojp         → {len(r['light'])} runs on the light board with their next stops' times and positions")
    b.close()
print("OK")
