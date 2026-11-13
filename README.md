# swissPublicTransport

An Android public transport app for Switzerland. The first release (MVP) covers **Geneva** (Unireso: TPG, Léman Express, Mouettes, CGN) and **Lausanne** (tl, including the metro); the rest of Switzerland follows.

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
| 7 | [`prototypes/sprint-07-official-data`](prototypes/sprint-07-official-data/index.html) | Official data from opentransportdata.swiss (OJP 2.0) with the rider's own key, entered in Settings (TECH-05, TECH-06); remove a single saved stop (US-20) |
| 8 | [`prototypes/sprint-08-journey-details`](prototypes/sprint-08-journey-details/index.html) | Journey details open inside the result, rides in their line colour, intermediate stops with times, reminder one stop before getting off (switch in Settings), each walk on a map, merged walks (US-28…32, BUG-03) |
| 9 | [`prototypes/sprint-09-my-places`](prototypes/sprint-09-my-places/index.html) | My places (Home, Work, named places) as one-tap chips on the Journey page, ordered by use; address search; removing the stop on screen shows the next most-used one; alarms that adapt when set late or on board (US-21…23, US-27, US-33); line colours of every Swiss operator, PostAuto and the Lausanne metro (US-42); walks end on the live platform of the next ride, platforms tappable while following (BUG-05); a change on the same platform is a wait, not a walk (BUG-06); live data matched by direction, only announced platform changes (BUG-07); stop search across Switzerland (US-43); leaving early adjusts alarms and journey by position (US-44); stopovers of a chosen length and round trips, adjusted when the stay is shorter or longer (US-45, US-46); walking and waiting at each change shown when planning (US-47) |

> **Language policy.** From Sprint 4 on, everything on GitHub is in English: code, comments, docs, issues and pull requests. The app UI is English by default and French when the phone is set to French. Prototypes 1–3 predate this rule and are kept as historical snapshots, unchanged.

## Data

**Official source (Sprint 7 on): [opentransportdata.swiss](https://opentransportdata.swiss), OJP 2.0.** The Swiss open-data platform's journey-planner API, with real time and platforms. It needs a personal API key (free plan: 50 requests per minute).
- **The key is never in the code.** In the prototype, the rider pastes it in Settings ⚙; it is checked with one small request, stored only in the browser (`localStorage`, key `tpp:ojpKey`) and sent only to `api.opentransportdata.swiss` in the `Authorization` header. The service allows browser calls (CORS), so no server is needed for personal testing. Before the APK is distributed, a small relay will hold the key and cache answers (TECH-06).
- [`assets/ojp.js`](assets/ojp.js) builds the XML requests and turns the answers into the transport.opendata.ch shape below, so every screen works with either source. Stop ids: OJP's `ch:1:sloid:87387` ↔ the app's `8587387`.
- Requests used: `LocationInformationRequest` (stop search by name; stops in a rectangle around a point), `StopEventRequest` (departures), `TripRequest` (journeys, leaving at or arriving by).
- Departures with their next stops are heavy (≈ 9 KB each, gzip-compressed on the wire). They are asked once per stop (40 departures) and remembered per run pattern (line, direction, terminus) for a day; the 30-second refreshes ask without them (≈ 2 KB each). A run not yet known is asked again at most every 5 minutes.
- Stop search is Switzerland-wide (US-43). The rider's own stops come first, then stops in the towns of those stops (Geneva for a new rider), then the rest.
- Real answers for Geneva are recorded in [`tests/fixtures/ojp/`](tests/fixtures/ojp/) by the `OJP probe` workflow ([`scripts/ojp_probe.mjs`](scripts/ojp_probe.mjs)), using the `OJP_TOKEN` repository secret; it also sends the requests exactly as the app builds them.

**Without a key: [transport.opendata.ch](https://transport.opendata.ch)**: open API, no key, CORS enabled, covering the official Swiss timetable with real-time data when available.
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
- **Line colours**: Geneva first, from [`assets/line-colors.js`](assets/line-colors.js) (surveyed from tpg.ch, lemanexpress.com and mouettesgenevoises.ch). The rest of Switzerland from [`assets/line-colors-ch.js`](assets/line-colors-ch.js): bus, tram, metro, boat, funicular and cable-car lines of about 80 operators, taken from **OpenStreetMap** route relations (`colour` tag; © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright)) and linked to the official company numbers of the **ATLAS business organisations** (opentransportdata.swiss), so both data sources find them. [`scripts/build_line_colors.py`](scripts/build_line_colors.py) builds it; the [`update-line-colors.yml`](.github/workflows/update-line-colors.yml) workflow rebuilds it monthly. A number used in several regions with different colours gets none; PostAuto lines without a colour of their own get the PostAuto yellow; trains keep the SBB timetable icons. The text is white unless that would read below 3:1. Unknown lines fall back to a neutral badge. All colours can be checked on [`tools/line-colors.html`](tools/line-colors.html).
- **Metro**: Lausanne's m1 and m2 are shown as metro lines, with the SBB metro pictogram ("M").

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
python tests/test_favorites.py           # remove one stop / clear all, with undo
python tests/test_sprint07_ojp.py        # OJP key in Settings, departures / search / journeys from recorded real answers
python tests/test_sprint08.py            # journey details, line colours, intermediate stops, get-off reminders, walk map
python tests/test_sprint09.py            # my places, address search, next stop after removal, alarms set late
python tests/test_alight_gps.py          # get-off reminders: live time of each ride, position, tunnel fallback
python tests/test_finish_on_foot.py      # finish / start on foot: offer, switch both ways, learning, limits
python tests/test_followed_journey.py    # followed journey: live steps, platform change, missed / tight connection, alternatives
python tests/test_languages.py           # English, French, German, Italian, Romansh
```

## Workflow

- Backlog and user stories: [GitHub Issues](https://github.com/TiagSant/swissPublicTransport/issues), one milestone per sprint (conventions in [`docs/backlog.md`](docs/backlog.md))
- One branch and one pull request per sprint. Prototype pull requests are merged once their tests pass; the product owner reviews the Android app (APK) releases
