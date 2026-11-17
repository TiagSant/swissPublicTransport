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
| 9 | [`prototypes/sprint-09-my-places`](prototypes/sprint-09-my-places/index.html) | My places (Home, Work, named places) as one-tap chips on the Journey page, ordered by use; address search; removing the stop on screen shows the next most-used one; alarms that adapt when set late or on board (US-21…23, US-27, US-33); line colours of every Swiss operator, PostAuto and the Lausanne metro (US-42); walks end on the live platform of the next ride, platforms tappable while following (BUG-05); a change on the same platform is a wait, not a walk (BUG-06); live data matched by direction, only announced platform changes (BUG-07); stop search across Switzerland (US-43); leaving early adjusts alarms and journey by position (US-44); stopovers of a chosen length and round trips, adjusted when the stay is shorter or longer (US-45, US-46); walking and waiting at each change shown when planning (US-47); stops without a platform shown by their position, "Stop" button and walks (US-48); the app name (US-49); staying on to the change's stop or a later stop to walk less (US-50, US-51); walking along the streets (US-52); boarding the next vehicle earlier (US-53); getting off earlier when a stop already passed is closer to the next ride (BUG-11); change places checked on real data across Switzerland: same estimate for every place, boarding later where both vehicles go on together, platforms for all of Switzerland, tracks with sectors (BUG-12); trains with several destinations: where the train splits and which part to be in, from the OJP notice (US-54); journeys with a change missed at the current times not suggested (US-57); identical journeys shown once (same route and same alternative, US-58); the same walk reached from different buses: one card, each bus offered (US-59); the same vehicles boarded at another nearby stop counted once (BUG-13); cancelled vehicles not suggested, and replaced in one tap when following (US-61); late start or first ride missed: other departures from where the rider is, alarms moved (US-62); the followed journey keeps up: earlier run boarded (GPS), finish on foot offered, other ways from here (US-63); getting off earlier and finishing on foot, without the next ride, as a journey of its own (US-64), the earliest and the least-walking stops kept, a beaten one left out once walks follow the streets (BUG-18); walking to a stop a later ride passes and boarding it there, also as a journey of its own (US-65); a late vehicle's stops without live times of their own take its delay (BUG-15); walking or riding from the phone's own motion sensors (no Google service, nothing sent): still walking a minute after the first vehicle left → other ways from there (US-66); traffic messages (OJP) on departures, journeys and followed rides, a new one told once while following (US-67); following what really happens: leaving now (no alarm), on board after all (the run where the rider is), still in a vehicle when stopped in traffic, a vehicle faster than the last walk offered, a vehicle taken outside the plan followed (BUG-17); stops passed from the GPS placed along the line, kept once seen passed (BUG-19); the journey followed has the better change place: "Follow" waits for the check, and changes still ahead are checked on the way (BUG-14) |

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
- **Platform positions**: [`assets/quays.js`](assets/quays.js) (Geneva area) and [`assets/quays-ch/`](assets/quays-ch) (all of Switzerland, one small file per block of stop numbers, loaded for the stops of a journey only), built from the official **ATLAS traffic points** (opentransportdata.swiss, open use with attribution) by [`scripts/build_quays.py`](scripts/build_quays.py). A GitHub Actions workflow ([`update-quays.yml`](.github/workflows/update-quays.yml)) rebuilds it every Monday and commits any change.
- **Maps**: [Leaflet](https://leafletjs.com) with © OpenStreetMap tiles. Fine for prototypes; a public release needs its own tile provider (OSM's tile usage policy).
- **Journeys**: `/v1/connections` between stops. A map point or the rider's position is linked to its 2 nearest stops (within 1.2 km); every combination is searched and the walk is added at the rider's speed (straight line × 1.3 for the street detour).
- **Alarms (web prototype)**: they ring only while the page is open (service-worker notification, sound, vibration, banner). Background alarms need the Android app (alarm manager).
- **Line colours**: Geneva first, from [`assets/line-colors.js`](assets/line-colors.js) (surveyed from tpg.ch, lemanexpress.com and mouettesgenevoises.ch). The rest of Switzerland from [`assets/line-colors-ch.js`](assets/line-colors-ch.js): bus, tram, metro, boat, funicular and cable-car lines of about 80 operators, taken from **OpenStreetMap** route relations (`colour` tag; © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright)) and linked to the official company numbers of the **ATLAS business organisations** (opentransportdata.swiss), so both data sources find them. [`scripts/build_line_colors.py`](scripts/build_line_colors.py) builds it; the [`update-line-colors.yml`](.github/workflows/update-line-colors.yml) workflow rebuilds it monthly. A number used in several regions with different colours gets none; PostAuto lines without a colour of their own get the PostAuto yellow; trains keep the SBB timetable icons. The text is white unless that would read below 3:1. Unknown lines fall back to a neutral badge. All colours can be checked on [`tools/line-colors.html`](tools/line-colors.html).
- **Walking routes**: the OpenStreetMap routing server of FOSSGIS ([routing.openstreetmap.de](https://routing.openstreetmap.de/about.html), OSRM, foot profile; © OpenStreetMap contributors). Only the start and end of each walk are sent; routes are cached on the device; the setting can turn it off (straight line × 1.3).
- **Metro**: Lausanne's m1 and m2 are shown as metro lines, with the SBB metro pictogram ("M").

Preferences (visited stops, hidden lines and directions, usage scores per direction) are stored in the device's `localStorage` under the `tpp:` prefix.

## Tests

End-to-end tests with Playwright, on the current prototype only (Sprint 9); the tests of earlier sprints were removed. The API is mocked with fixtures, so tests are reproducible without a network.

```bash
pip install -r tests/requirements.txt
python -m playwright install chromium   # or CHROME_PATH=/path/to/chrome
# optional: LEAFLET_DIR / TILE_PNG serve Leaflet and map tiles locally
python tests/test_build_quays.py         # platform data builder, synthetic CSV
python tests/test_sprint09.py            # my places, address search, next stop after removal, alarms set late
python tests/test_alight_gps.py          # get-off reminders: live time of each ride, position, tunnel fallback
python tests/test_finish_on_foot.py      # finish / start on foot: offer, switch both ways, learning, limits
python tests/test_followed_journey.py    # followed journey: live steps, platform change, missed / tight connection, alternatives
python tests/test_languages.py           # English, French, German, Italian, Romansh
python tests/test_line_colors.py         # line colours and pictograms of every Swiss operator
python tests/test_onward_ojp.py          # next stops of each run rebuilt from official data (OJP)
python tests/test_run_direction.py       # a followed ride matched by line and direction
python tests/test_walk_platform.py       # a walk ends on the platform of the next ride
python tests/test_change_walk.py         # changing platform means walking
python tests/test_stops_and_order.py     # intermediate stops: credible times, passed stops greyed out
python tests/test_trip_parts.py          # leaving early, stopovers, round trips
python tests/test_plan_waits.py          # walking and waiting at each change, when planning
python tests/test_stop_without_platform.py   # a stop without platform shown like a platform
python tests/test_departures_stop_chip.py    # "Stop" button on the Departures tab
python tests/test_smarter_walking.py     # stay on to the change's stop, finish on foot later, walking along streets
python tests/test_get_off_earlier.py     # get off earlier when it is closer to the next ride
python tests/test_change_place.py        # change place checked on real data across Switzerland
python tests/test_hide_missed.py         # a journey whose change is missed is not suggested
python tests/test_dedupe_journeys.py     # same journeys shown once, alternatives grouped
python tests/test_cancelled_run.py       # a cancelled vehicle: not suggested; replaced in one tap when following
python tests/test_late_start.py          # late start / first ride missed: GPS, “I'm leaving later”, “I'm on board after all”
python tests/test_follow_changes.py      # earlier run boarded, finish on foot, other ways from here
python tests/test_split_train.py         # trains that split (OJP notice A__FL): notice, same train, get-off reminder
python tests/test_shortcut_on_foot.py    # get off earlier and finish on foot, without the second bus: a journey of its own
python tests/test_shortcut_start.py      # walk to a stop a later ride passes (Stand instead of tram 12 to Bel-Air): a journey of its own; also with a late tram (BUG-15)
python tests/test_shortcut_best_stop.py  # get off earlier: the least-walking stop kept (Stand), a stop beaten once walks follow the streets left out
python tests/test_follow_best_change.py  # the followed journey has the better change place (Follow waits for it; checked on the way)
python tests/test_walking_sensors.py     # walking or riding from the motion sensors: first vehicle gone without the rider, on board, setting off
python tests/test_traffic_info.py        # traffic messages (OJP): on the ride valid now only, in the app's language; departures' parser
python tests/test_follow_real_events.py  # the PO's trip of 17.11.2026 replayed: leaving now, late, earlier tram, traffic stop, bus 19 at Jonction
python tests/test_passed_stops.py        # stops passed: the GPS along the line wins, a stop seen passed stays so; by time without GPS
```

**Audit of changes on real data** (manual GitHub Actions workflow, needs the `OJP_TOKEN` secret): the Sprint 9 prototype plans real journeys in about twenty Swiss cities with both data sources, and [`tools/audit/audit_changes.py`](tools/audit/audit_changes.py) checks each change against the best place the same two vehicles allow (full runs of both vehicles from OJP). It reports changes moved to a worse place, missed improvements and why.

## Workflow

- Backlog and user stories: [GitHub Issues](https://github.com/TiagSant/swissPublicTransport/issues), one milestone per sprint (conventions in [`docs/backlog.md`](docs/backlog.md))
- One branch and one pull request per sprint. Prototype pull requests are merged once their tests pass; the product owner reviews the Android app (APK) releases
