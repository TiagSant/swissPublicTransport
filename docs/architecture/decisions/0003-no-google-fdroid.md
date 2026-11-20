# ADR-0003 — No Google services; distribution on F-Droid

**Status:** Accepted (PO rules)

## Decision

- No Google API, service or SDK: no Play Services, Fused Location Provider, Activity Recognition API, Firebase, FCM, Crashlytics, Google Maps.
- Location from Android's `LocationManager`; walking or riding from `SensorManager` (accelerometer, step detector); notifications are local only.
- Walking directions are handed to the rider's maps app with a `geo:` intent (OsmAnd, Organic Maps…).
- The app is published on **F-Droid**: licence **GPL-3.0-or-later** (PO, 20.11.2026, TECH-13; [`LICENSE`](../../../LICENSE)), build from source with FLOSS dependencies only, metadata (fastlane) in the repository.

## Consequences

- The build fails when a `com.google.android.gms` or `com.google.firebase` dependency appears, direct or transitive (`android/build.gradle.kts`); CI checks this guard on every pull request.
- Expected F-Droid anti-features: *NonFreeNet* (opentransportdata.swiss), possibly *NonFreeAssets* (SBB pictograms: approval to ask from SBB Brand Management, see `assets/sbb/NOTICE.md`).
- `ACTIVITY_RECOGNITION` permission is still needed for the step detector on Android 10+; it is an Android permission, not a Google service.
