# swissPublicTransport

An Android public transport app: Geneva first (Unireso / TPG, Léman Express, Mouettes, CGN), then Lausanne, then the whole of Switzerland.

Before moving to an APK, each sprint ships a **standalone prototype**: a web page that runs in a browser with no server or install.

## Guiding principle (product requirements)

The app adapts to its user:
- the most-used lines and stops are preselected and shown first;
- upcoming departures are reachable in as few gestures as possible;
- routes follow the user's priority (fastest, least walking, …).

## Prototypes

Live on GitHub Pages: https://tiagsant.github.io/swissPublicTransport/

| Sprint | Folder | Content |
|---|---|---|
| 1 | [`prototypes/sprint-01-departs`](prototypes/sprint-01-departs/index.html) | Stop search (Unireso area), real-time departures, line selection, frequent stops |
| 2 | [`prototypes/sprint-02-directions`](prototypes/sprint-02-directions/index.html) | Filter by direction (line + next stop), compatible with Sprint 1 preferences |
| 3 | [`prototypes/sprint-03-habitudes`](prototypes/sprint-03-habitudes/index.html) | Automatic preselection of usual lines (US-06); tap a departure to see its next stops |
| 4 | [`prototypes/sprint-04-identity`](prototypes/sprint-04-identity/index.html) | English/French UI (US-10), official SBB pictograms (US-11), operators' line colours (US-12) |
| 5 | [`prototypes/sprint-05-platforms`](prototypes/sprint-05-platforms/index.html) | Platform map with the rider's position and walking directions (US-13) |
| 6 | [`prototypes/sprint-06-journeys`](prototypes/sprint-06-journeys/index.html) | Journey planner (stops, my position, map points; fastest / least walking), get-ready and leave alarms following live data, learned walking speed (US-07…09, US-14…19, TECH-04) |

> **Language policy.** From Sprint 4 on, everything on GitHub is in English: code, comments, docs, issues and pull requests. The app UI is English by default and French when the phone is set to French. Prototypes 1–3 predate this rule and are kept as historical snapshots, unchanged.

## Data

[transport.opendata.ch](https://transport.opendata.ch): open API, no key, CORS enabled, covering the official Swiss timetable with real-time data when available.
- `/v1/locations`: stop search (by name or by coordinates)
- `/v1/stationboard`: upcoming departures at a stop (`passList` is used to identify the direction)

Real-data findings (category codes, operators, fields) are in [`docs/real-data-validation.md`](docs/real-data-validation.md).

**Availability.** transport.opendata.ch is a free community service: it has outages and per-user daily limits (reported as about 1,000 journey and 10,080 departure-board queries). The Sprint 6 prototype times out after 10 s and shows a banner explaining the problem until a call succeeds again. A production app needs its own backend with caching, or a direct opentransportdata.swiss access.

## Visual identity

- **Pictograms**: Swiss public transport pictograms and SBB timetable icons, copied unmodified into [`assets/sbb/`](assets/sbb/). They may only be used by a Swiss public transport project, unmodified and non-commercially — see [`assets/sbb/NOTICE.md`](assets/sbb/NOTICE.md). **A commercial release requires prior approval from SBB Brand Management.**
- **Platform positions**: [`assets/quays.js`](assets/quays.js), built from the official **ATLAS traffic points** (opentransportdata.swiss, open use with attribution) by [`scripts/build_quays.py`](scripts/build_quays.py). A GitHub Actions workflow ([`update-quays.yml`](.github/workflows/update-quays.yml)) rebuilds it every Monday and commits any change.
- **Maps**: [Leaflet](https://leafletjs.com) with © OpenStreetMap tiles. Fine for prototypes; a public release needs its own tile provider (OSM's tile usage policy).
- **Journeys**: `/v1/connections` between stops. A map point or the rider's position is linked to its 2 nearest stops (within 1.2 km); every combination is searched and the walk is added at the rider's speed (straight line × 1.3 for the street detour).
- **Alarms (web prototype)**: they ring only while the page is open (service-worker notification, sound, vibration, banner). Background alarms need the Android app (alarm manager).
- **Line colours**: [`assets/line-colors.js`](assets/line-colors.js), surveyed from tpg.ch, lemanexpress.com and mouettesgenevoises.ch. Unknown lines fall back to a neutral badge.

Preferences (visited stops, hidden lines and directions, usage scores per direction) are stored in the device's `localStorage` under the `tpp:` prefix.

## Tests

End-to-end tests with Playwright. The API is mocked with fixtures, so tests are reproducible without a network.

```bash
pip install -r tests/requirements.txt
python -m playwright install chromium   # or CHROME_PATH=/path/to/chrome
python tests/test_sprint01.py
python tests/test_sprint02.py
python tests/test_sprint03.py
python tests/test_sprint04.py            # screenshots in tests/out/
python tests/test_delayed_departures.py  # BUG-01 regression (reproduces the bug on Sprint 3)
python tests/test_sprint05.py            # LEAFLET_DIR / TILE_PNG serve Leaflet and tiles locally (optional)
python tests/test_build_quays.py         # platform data builder, synthetic CSV
python tests/test_sprint06.py            # journeys and alarms, with a frozen browser clock
python tests/test_api_outage.py          # API down / 503 / 429 / no answer → banner, 10 s timeout
```

## Workflow

- Backlog and user stories: [GitHub Issues](https://github.com/TiagSant/swissPublicTransport/issues), one milestone per sprint (conventions in [`docs/backlog.md`](docs/backlog.md))
- One branch and one pull request per sprint, code-reviewed by the product owner
