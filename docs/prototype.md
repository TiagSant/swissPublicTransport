# Web prototype (functional reference)

The prototype in [`prototype/`](../prototype/index.html) is a single web page that runs in a browser with no server or install. It is **frozen** ([ADR-0005](architecture/decisions/0005-prototype-is-the-reference.md)): it is the reference for the Android MVP and is not extended.

- **Live:** https://tiagsant.github.io/swissPublicTransport/prototype/
- **Locally:** open `prototype/index.html` in a browser, or serve the repository root (`python -m http.server`) and open `/prototype/`.
- **Data:** without a key, transport.opendata.ch; with a personal opentransportdata.swiss key pasted in Settings ⚙, the official OJP 2.0 API.
- **Web limits:** alarms ring only while the page is open; the position and motion sensors stop when the screen is off. Settings ⚙ has test buttons and a simulated walk.

## Tests

End-to-end tests with Playwright. The APIs are mocked with fixtures and the browser clock is frozen, so they run without a network.

```bash
pip install -r tests/requirements.txt
python -m playwright install chromium        # or CHROME_PATH=/path/to/chrome
# optional: LEAFLET_DIR (a folder with leaflet.js / leaflet.css) and TILE_PNG serve the map offline
for t in tests/test_*.py; do python "$t" || echo "FAILED: $t"; done
```

| Test | Covers |
|---|---|
| `test_build_quays.py` | platform data builder (synthetic CSV) |
| `test_my_places.py` | my places, address search, next stop after removal, alarms set late |
| `test_alight_gps.py` | get-off reminders: live time of each ride, position, tunnel fallback |
| `test_finish_on_foot.py` | finish / start on foot: offer, switch both ways, learning, limits |
| `test_followed_journey.py` | followed journey: live steps, platform change, missed / tight connection, alternatives |
| `test_languages.py` | English, French, German, Italian, Romansh |
| `test_line_colors.py` | line colours and pictograms of every Swiss operator |
| `test_onward_ojp.py` | next stops of each run rebuilt from OJP |
| `test_run_direction.py` | a followed ride matched by line and direction |
| `test_walk_platform.py` | a walk ends on the platform of the next ride |
| `test_change_walk.py` | changing platform means walking |
| `test_stops_and_order.py` | intermediate stops: credible times, passed stops greyed out |
| `test_trip_parts.py` | leaving early, stopovers, round trips |
| `test_plan_waits.py` | walking and waiting at each change, when planning |
| `test_stop_without_platform.py` | a stop without platform shown like a platform |
| `test_departures_stop_chip.py` | "Stop" button on the Departures tab |
| `test_smarter_walking.py` | stay on to the change's stop, finish on foot later, walking along streets |
| `test_get_off_earlier.py` | get off earlier when it is closer to the next ride |
| `test_change_place.py` | change place checked on real data across Switzerland |
| `test_hide_missed.py` | a journey whose change is missed is not suggested |
| `test_dedupe_journeys.py` | same journeys shown once, alternatives grouped |
| `test_cancelled_run.py` | a cancelled vehicle: not suggested; replaced in one tap when following |
| `test_late_start.py` | late start / first ride missed: GPS, "I'm leaving later", "I'm on board after all" |
| `test_follow_changes.py` | earlier run boarded, finish on foot, other ways from here |
| `test_split_train.py` | trains that split (OJP notice A__FL) |
| `test_shortcut_on_foot.py` | get off earlier and finish on foot, as a journey of its own |
| `test_shortcut_start.py` | walk to a stop a later ride passes (also with a late tram, BUG-15) |
| `test_shortcut_best_stop.py` | get off earlier: the least-walking stop kept |
| `test_follow_best_change.py` | the followed journey has the better change place |
| `test_walking_sensors.py` | walking or riding from the motion sensors |
| `test_traffic_info.py` | traffic messages: on the ride valid now, in the app's language |
| `test_follow_real_events.py` | the PO's trip of 17.11.2026 replayed |
| `test_passed_stops.py` | stops passed: GPS along the line, by time without GPS |
| `test_gps_when_needed.py` | GPS only when it helps; stops served sensed by the motion sensors |
| `test_fastest_and_duplicates.py` | "fastest" = shortest; one card for the same vehicles |
| `test_alternative_change_walk.py` | missed change, another bus chosen: the walk between platforms kept |
| `test_off_at_change.py` | off at the change before the time announced; steps inside the tram |

**Audit of changes on real data** (manual workflow `audit-changes.yml`, needs the `OJP_TOKEN` secret): the prototype plans real journeys in about twenty Swiss cities with both data sources, and [`tools/audit/audit_changes.py`](../tools/audit/audit_changes.py) checks each change against the best place the same two vehicles allow.

## History

| Sprint (Nov 2026) | Main content |
|---|---|
| 1 | Stop search, real-time departures, line selection, frequent stops (US-01…04) |
| 2 | Filter by direction (US-05) |
| 3 | Usual lines preselected (US-06); next stops of a departure; hosting, real-data validation |
| 4 | English/French, SBB pictograms, operators' colours (US-10…12) |
| 5 | Platform on a map, walk there (US-13) |
| 6 | Journey planner, fastest / least walking, alarms, learned walking speed (US-07…09, US-14…19) |
| 7 | Official data OJP 2.0 with the rider's key (TECH-05…07), remove one stop (US-20) |
| 8 | Journey details, line colours, intermediate stops, get-off reminder, walks on a map, following live, DE/IT/RM (US-28…41) |
| 9 | My places, addresses, Switzerland-wide stops and colours, stopovers, smarter changes, sensors, traffic messages (US-21…23, US-27, US-33, US-42…69, BUG-05…23) |

Earlier prototypes are kept under the tag [`prototypes-sprint-01-09`](https://github.com/TiagSant/swissPublicTransport/tree/prototypes-sprint-01-09).
