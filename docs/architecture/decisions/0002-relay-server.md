# ADR-0002 — A relay holds the OJP key, caches data and computes change places

**Status:** Accepted (PO): the relay and its scope on 14.11.2026 ([TECH-08 #41](https://github.com/TiagSant/swissPublicTransport/issues/41)); Kotlin with Ktor and hosting at Infomaniak on 20.11.2026 ([TECH-13 #172](https://github.com/TiagSant/swissPublicTransport/issues/172)). The domain name is chosen with TECH-08 (Sprint 11).

## Context

- An API key shipped in an APK can be extracted, and every rider would share one quota (free plan: 50 requests/min, 20,000/day).
- The audit of changes on real data showed that one journey search in the prototype sends 30–56 OJP requests (journeys, boards, runs): too many for one key without a cache.
- F-Droid publishes any key found in the source.

## Decision

1. A **relay** holds the key and is the app's only data source. It caches boards (per stop, ≈ 20–30 s), runs (a day), journeys and walking routes; rounds request times so identical requests share the cache; limits each app instance and answers `429` with a clear message.
2. The relay **computes the change places** (stay on, get off earlier, board earlier, finish or start on foot) with the prototype's rules and the ATLAS platform positions, and returns journeys already improved.
3. Written in **Kotlin with Ktor**, sharing the `:core` module with the app (one implementation of the rules, tested once).
4. Hosted in Switzerland at **Infomaniak** (PO, 20.11.2026), deployed as a Docker image by GitHub Actions. The domain name is chosen in Sprint 11 (TECH-08).

## Consequences

- The app needs no key; the rider's own key (prototype Settings) disappears from the app.
- A server to run and pay for; its availability becomes the app's availability → health check and a clear message in the app when it is down (as BUG-02 #32 in the prototype).
- The relay code is in this repository (`relay/`), under the same licence.
