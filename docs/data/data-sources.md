# Data sources and licences

## Timetable and real time

**opentransportdata.swiss — OJP 2.0** (official source from Sprint 7 on). The Swiss open-data platform's journey-planner API, with real time and platforms. It needs a personal API key (free plan: 50 requests per minute, 20,000 per day).

- **The key is never in the code.** In the prototype, the rider pastes it in Settings ⚙; it is checked with one small request, stored only in the browser (`localStorage`, key `tpp:ojpKey`) and sent only to `api.opentransportdata.swiss` in the `Authorization` header. The service allows browser calls (CORS). In the Android app, the relay holds the key ([ADR-0002](../architecture/decisions/0002-relay-server.md)).
- [`assets/ojp.js`](../../assets/ojp.js) builds the XML requests and turns the answers into the transport.opendata.ch shape below, so every prototype screen works with either source. Stop ids: OJP's `ch:1:sloid:87387` ↔ the app's `8587387`.
- Requests used: `LocationInformationRequest` (stop search by name; stops in a rectangle around a point; addresses and places of interest), `StopEventRequest` (departures) and `TripRequest` (journeys, leaving at or arriving by).
- Departures with their next stops are heavy (≈ 9 KB each, gzip-compressed on the wire). They are asked once per stop (40 departures) and remembered per run pattern (line, direction, terminus) for a day; the 30-second refreshes ask without them (≈ 2 KB each). A run not yet known is asked again at most every 5 minutes.
- Real answers for Geneva are recorded in [`tests/fixtures/ojp/`](../../tests/fixtures/ojp/) by the `OJP probe` workflow ([`scripts/ojp_probe.mjs`](../../scripts/ojp_probe.mjs)), using the `OJP_TOKEN` repository secret; it also sends the requests exactly as the app builds them.

**transport.opendata.ch** (prototype without a key): open API, no key, CORS enabled, official Swiss timetable with real time when available. `/v1/locations` (stop search), `/v1/stationboard` (departures, `passList` gives the direction), `/v1/connections` (journeys). A free community service with outages and daily limits (about 1,000 journey and 10,080 board queries per user); the prototype times out after 10 s and shows a banner. Not used by the Android app.

Real-data findings (category codes, operators, fields): [`real-data-validation.md`](real-data-validation.md).

## Static data

| Data | File | Source and licence | Rebuilt by |
|---|---|---|---|
| Platform positions, Geneva area | [`assets/quays.js`](../../assets/quays.js) | ATLAS traffic points, opentransportdata.swiss (open use with attribution) | [`scripts/build_quays.py`](../../scripts/build_quays.py), workflow `update-quays.yml`, every Monday |
| Platform positions, all of Switzerland (one file per block of stop numbers, loaded for the stops of a journey only) | [`assets/quays-ch/`](../../assets/quays-ch/) | same | same |
| Line colours, Geneva (tpg, Léman Express, Mouettes) | [`assets/line-colors.js`](../../assets/line-colors.js) | surveyed from tpg.ch, lemanexpress.com, mouettesgenevoises.ch; validated by the PO | by hand |
| Line colours, rest of Switzerland (≈ 80 operators: bus, tram, metro, boat, funicular, cable car) | [`assets/line-colors-ch.js`](../../assets/line-colors-ch.js) | OpenStreetMap route relations (`colour` tag, © OpenStreetMap contributors, ODbL 1.0) linked to ATLAS business organisations | [`scripts/build_line_colors.py`](../../scripts/build_line_colors.py), workflow `update-line-colors.yml`, monthly |
| Pictograms and timetable icons | [`assets/sbb/`](../../assets/sbb/) | SBB design system, files under Apache-2.0, **brand terms: unmodified, Swiss public transport project, non-commercial** — see [`NOTICE.md`](../../assets/sbb/NOTICE.md). A commercial release needs prior approval from SBB Brand Management. | copied unmodified |

Line colour rules: Geneva first; a number used in several regions with different colours gets none; PostAuto lines without a colour of their own get PostAuto yellow; trains keep the SBB timetable icons; text is white unless it would read below 3:1; unknown lines get a neutral badge. All colours can be checked on [`tools/line-colors.html`](../../tools/line-colors.html).

## Maps and walking

- **Maps** (prototype): [Leaflet](https://leafletjs.com) with © OpenStreetMap tiles — fine for a prototype; a distributed app needs its own tile provider ([ADR-0004](../architecture/decisions/0004-maps-and-walking.md)).
- **Walking routes**: the OpenStreetMap routing server of FOSSGIS ([routing.openstreetmap.de](https://routing.openstreetmap.de/about.html), OSRM, foot profile; © OpenStreetMap contributors). Only the start and end of each walk are sent; routes are cached on the device; a setting turns it off (straight line × 1.3).

## Rider data

Preferences (visited stops, hidden lines and directions, usage scores per direction, places, settings, learned walking speed) are stored on the device only — `localStorage` under the `tpp:` prefix in the prototype.
