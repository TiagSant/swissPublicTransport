# MVP functional specification

The MVP is the web prototype ([`prototype/`](../../prototype/index.html)) rebuilt as a native Android app. This page lists **what the app must do**, area by area. Each behaviour points to the prototype issue where it was specified and validated; that issue's acceptance criteria and the prototype's tests ([`docs/prototype.md`](../prototype.md)) are the detailed reference. When this page and the prototype disagree, the prototype wins until the PO decides otherwise.

Android stories that rebuild each area are listed in the [roadmap](roadmap.md).

## 1. Departures

| Behaviour | Reference |
|---|---|
| Search a stop by name, across Switzerland. The rider's own stops come first, then stops in the towns of those stops (Geneva for a new rider), then the rest. | US-01 #1, US-43 #85 |
| Stops near me (📍), from the phone's position. | US-01 #1 |
| Real-time departures, refreshed every 30 s, countdown every 15 s. A late departure stays listed until one minute after it really left. | US-02 #2, BUG-01 #19 |
| Each departure shows line (colour, pictogram), destination, platform, delay, cancellation and traffic messages. | US-12 #16, US-61 #131, US-67 #149 |
| Live data is matched by line **and** direction; only announced platform changes are shown as changes. | BUG-07 #83 |
| Choose the lines shown (all / none / per line). | US-03 #3 |
| Filter by direction (line + next stop); a partial chip shows `12 · 1/2`; unchecking every direction hides the line. | US-05 #5 |
| "Your stops": one-tap chips of the stops used, remove one or all with undo; removing the stop on screen shows the next most-used one. | US-04 #4, US-20 #34, US-27 #49 |
| **Usual lines preselected** per stop and direction from usage (see parameters); "See all" peeks at every line; manual choice overrides habits, "Back to habits" resets. | US-06 #6 |
| Tap a departure to see its next stops. | Sprint 3, onward stops from OJP |
| Tap a platform letter / track to see it on a map with every platform of the stop, the rider's position and distance, and "Walk there" (phone's maps app). Stops without a platform are shown by the stop's position. | US-13 #20, US-48 #92 |

## 2. Journey planning

| Behaviour | Reference |
|---|---|
| From / To: a stop, my position, a point on the map, an address or a place of interest; swap. | US-14 #23, US-15 #24, US-23 #44 |
| Leave at / arrive by a chosen time. | US-14 #23 |
| Priority **Fastest** (the journey that lasts the least; arriving earlier breaks a tie) or **Least walking**; the choice is remembered. | US-07 #7, US-08 #8, US-09 #9, BUG-20 #162 |
| A map point or my position is linked to its nearest stops (within 1.2 km); every combination is searched; walks at the rider's speed. | US-15 #24 |
| **My places**: Home, Work and named places, saved from an address, a stop, my position or the map; one-tap chips on the Journey page ordered by use; also suggested while typing; rename, remove, undo. | US-21 #42, US-22 #43 |
| Stopover of a chosen length; round trip with a chosen time there; adjusted when the stay is shorter or longer. | US-45 #87, US-46 #88 |

## 3. Journey results and details

| Behaviour | Reference |
|---|---|
| The details of a journey open inside the result, one at a time. | US-28 #50 |
| Each ride in its line colour; ride time; clear arrival stop; intermediate stops with their times. | US-29 #51, US-30 #52, US-34 #59 |
| Each walk on a map; consecutive walks merged; a change on the same platform is a wait, not a walk; a walk ends on the live platform of the next ride. | US-32 #54, BUG-03 #55, BUG-06 #81, BUG-05 #79, BUG-08 #105 |
| Walking and waiting at each change shown when planning. | US-47 #90 |
| Journeys whose change is missed at the current times are not suggested; cancelled vehicles are not suggested. | US-57 #122, US-61 #131 |
| One card per journey: identical journeys once; the same walk from different buses is one card with each bus offered; the same vehicles boarded at another nearby stop or left at the same stops count once. | US-58 #124, US-59 #126, BUG-13 #128, BUG-21 #163 |
| Trains that split: where the train splits and which part to be in (OJP notice). | US-54 #118 |
| Walks follow the streets (OSM routing), cached on the device; can be turned off (straight line × 1.3). | US-52 #99 |

## 4. Smarter changes

Computed **on the relay** in the app (PO decision of 14.11.2026, [TECH-08](https://github.com/TiagSant/swissPublicTransport/issues/41)); the prototype's `bestChange` and its tests are the reference.

| Behaviour | Reference |
|---|---|
| Stay on to the change's stop, or a later stop, when it saves walking. | US-50 #97, US-51 #98 |
| Board the next vehicle earlier instead of walking to its stop. | US-53 #109 |
| Get off earlier when a stop already passed is closer to the next ride. | BUG-11 #113 |
| Change places checked on real data across Switzerland: the same walk estimate for every place, at least 1 min saved, the change kept comfortable. | BUG-12 #115 |
| Finish on foot instead of the last ride, start on foot instead of the first one; learned per place; the vehicle always stays as an alternative. | US-36 #64, US-37 #66 |
| Get off earlier and finish on foot without the next ride; walk to a stop a later ride passes and board it there — each a journey of its own. The earliest and the least-walking stops are kept. | US-64 #139, US-65 #143, BUG-18 #155 |

## 5. Alarms

| Behaviour | Reference |
|---|---|
| "Get ready" and "Leave now" alarms from the first vehicle's departure (live when available): leave = departure − (walk + margin); get ready = leave − preparation time. | US-16 #25, US-17 #26 |
| Alarms follow live data; they adapt when set late (on board: cancelled; less time: ring at once with the time left). | US-17 #26, US-33 #57 |
| Leaving early: the position adjusts alarms and journey. | US-44 #86 |
| Reminder one stop before each stop where the rider gets off (switch in Settings); follows the live time of each ride and the position. | US-31 #53, US-35 #61 |
| **Android:** alarms ring like the phone's alarm clock (exact alarm, alarm audio channel, full screen over the lock screen), survive a restart. | US-60 #130 |

## 6. Following a journey

| Behaviour | Reference |
|---|---|
| Every step live: delays, platforms, progress, stops and time on board; stops passed placed along the line by GPS, kept once seen passed. | US-38 #70, US-41 #75, BUG-19 #158 |
| A late vehicle's stops without live times take its delay. | BUG-15 #145 |
| Tight connection said plainly, with options that have a comfortable margin; live waiting time at each change. | US-39 #72 |
| Missed connection → alternatives (next run, another route, finish on foot); an alternative keeps the walk between platforms. | US-38 #70, BUG-22 #165 |
| A missed change, a cancelled vehicle or a late start is notified only once its alternatives are found, with the best one (line, departure, arrival), so opening the app shows them at once. With none, or after 20 s without an answer, the notification goes anyway and says so; it is never sent twice. | US-89 #196 (PO, 23.11.2026) |
| Cancelled vehicle replaced in one tap; late start or first ride missed → other departures from where the rider is, alarms moved. | US-61 #131, US-62 #133 |
| Keeps up with what really happens: earlier run boarded, on board after all, stopped in traffic, a faster vehicle, a vehicle outside the plan, off at the change before the announced time. | US-63 #135, BUG-17 #153, BUG-23 #167 |
| The followed journey has the better change place: "Follow" waits for the check; changes ahead are checked on the way. | BUG-14 #141 |
| Traffic messages on the ride valid now, in the app's language; a new one told once. | US-67 #149 |
| Walking or riding from the phone's own motion sensors (no Google service, nothing sent). GPS only when it helps (boarding, approach of the get-off stop, doubts, a check every 5 min). | US-66 #147, US-69 #160 |

## 7. Settings

Preparation time, walking speed (learned from measured walks, can be reset), safety margin, get-off reminder (on/off), finish on foot up to N minutes, walks along the streets (on/off), motion sensors (on/off), notifications. Reference: US-18 #27, US-19 #28. In the app, the OJP key setting disappears (the relay holds the key).

## 8. Identity and languages

- English by default; French, German, Italian, Romansh following the phone's language. (US-10 #14, US-40 #73)
- Official Swiss public transport pictograms and SBB timetable icons, unmodified. (US-11 #15)
- Every line in its operator's colour, for every Swiss operator; PostAuto yellow; metro m1/m2 with the metro pictogram; white text unless below 3:1 contrast. (US-12 #16, US-42 #77)
- The app is named **swissPublicTransport** everywhere. (US-49 #95)

## Reference parameters (from the prototype)

| Parameter | Value |
|---|---|
| Departures refresh / countdown | 30 s / 15 s |
| Departure kept after it left | 1 min |
| Departures shown | 25 |
| Habit half-life / "usual" threshold / debounce | 30 days / score ≥ 1.5 / 10 min |
| Default preparation / walking speed / margin | 10 min / 4.8 km/h / 1 min |
| Walk detour without street routing | straight line × 1.3 |
| Stops tried around a map point | within 1.2 km |
| Finish on foot offered | walking ≤ 5 min later than the vehicle; first after 3 times chosen; not offered after 6 times ignored |
| Comfortable change | ≥ 3 min to spare |
| Followed journey refresh | 60 s |
| GPS: fix accuracy / freshness | ≤ 50 m / ≤ 30 s |
| Walking speed learning | moving average (α = 0.3) of walks ≥ 150 m and ≥ 90 s, 2.5–7.5 km/h, accuracy ≤ 35 m |
| Next stops of runs (OJP) | 40 departures asked with their stops, kept 1 day, unknown run retried every 5 min |

The full list of constants is at the top of the prototype's script.
