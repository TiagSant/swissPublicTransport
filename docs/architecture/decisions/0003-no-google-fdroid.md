# ADR-0003 — No Google services; distribution on F-Droid

**Status:** Accepted (PO rules)

## Decision

- No Google API, service or SDK: no Play Services, Fused Location Provider, Activity Recognition API, Firebase, FCM, Crashlytics, Google Maps.
- Location from Android's `LocationManager`; walking or riding from `SensorManager` (accelerometer, step detector); notifications are local only.
- Walking directions are handed to the rider's maps app with a `geo:` intent (OsmAnd, Organic Maps…).
- The app is published on **F-Droid**: free licence (PO choice, TECH-13), build from source with FLOSS dependencies only, metadata (fastlane) in the repository.

## Consequences

- CI fails the build when a `com.google.android.gms` or `com.google.firebase` dependency appears.
- Expected F-Droid anti-features: *NonFreeNet* (opentransportdata.swiss), possibly *NonFreeAssets* (SBB pictograms: approval to ask from SBB Brand Management, see `assets/sbb/NOTICE.md`).
- `ACTIVITY_RECOGNITION` permission is still needed for the step detector on Android 10+; it is an Android permission, not a Google service.
