# Product vision and requirements

## Vision

**swissPublicTransport** is an Android public transport app for Switzerland that adapts to its rider. The first release (MVP) covers **Geneva** (Unireso: TPG, Léman Express, Mouettes, CGN) and **Lausanne** (tl, including the metro); stop search, departures and journeys already work across all of Switzerland.

## Requirements from the product owner

The app adapts to its user:

1. **Habits first.** The most-used stops, lines, directions and places are preselected and shown first.
2. **Fast access to the next departures.** Upcoming departures are reachable in as few gestures as possible.
3. **Routes that follow the rider's priority.** Fastest (the journey that lasts the least) or least walking; the choice is remembered.
4. **A journey that follows the rider.** Alarms to get ready, leave and get off; live delays, platform changes, missed connections and alternatives.

New requirements are added by the product owner (PO) as issues.

## Constraints

| Constraint | Source |
|---|---|
| No Google API or service (no Play Services, Firebase, Fused Location, activity recognition). Only Android and the phone's own sensors. | PO rule |
| Distributed on **F-Droid**: free licence, FLOSS build, no proprietary SDK. | PO decision, [TECH-09](https://github.com/TiagSant/swissPublicTransport/issues/63) |
| Official data: **opentransportdata.swiss (OJP 2.0)**. The API key never ships in the app: a relay holds it, caches answers and computes change places. | PO decisions, [TECH-08](https://github.com/TiagSant/swissPublicTransport/issues/41) |
| GPS on only when it helps; the motion sensors follow the ride in between (battery). | PO decision, US-69 |
| UI in the phone's language: English (default), French, German, Italian, Romansh. | PO decision |
| Official SBB pictograms (unmodified, non-commercial) and the operators' own line colours. | PO decision |
| Nothing about the rider leaves the phone (habits, places, positions), except the requests needed to answer them. | Prototype rule |
| **A behaviour validated earlier is never changed** without a PO decision. | PO rule |
| Everything on GitHub (code, docs, issues, PRs) is written in English. | PO rule |

## MVP scope

The MVP is the **web prototype** in [`prototype/`](../../prototype/index.html), rebuilt as a native Android app: every behaviour the prototype has is in the MVP, with the Android features the browser could not offer (alarms like the alarm clock, background following, sensors while the screen is off). The functional reference is [`mvp-spec.md`](mvp-spec.md); the plan is [`roadmap.md`](roadmap.md).

**Out of the MVP** (backlog milestone *Later*): usual journey suggested for the time of day (US-24), where to board along the platform (US-55), class sectors (US-56).

## Success criteria for the MVP

- The PO uses the app for his own daily trips in Geneva and Lausanne for two weeks without going back to another app.
- Every scenario covered by the prototype's tests gives the same result in the app (parity check).
- The app is accepted on F-Droid.
- The relay keeps OJP use under the free plan (50 requests/min, 20,000/day) with the beta testers.
