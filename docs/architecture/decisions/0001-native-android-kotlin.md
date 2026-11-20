# ADR-0001 — Native Android app in Kotlin and Jetpack Compose

**Status:** Accepted (PO, 20.11.2026, [TECH-13 #172](https://github.com/TiagSant/swissPublicTransport/issues/172))

## Context

TECH-03 (#12) left the choice open: wrap the web prototype (Capacitor, or a PWA in a Trusted Web Activity) or build a native app. The MVP needs:
- alarms that ring like the alarm clock, on silent and over the lock screen (US-60);
- following a journey with the screen off: position and motion sensors in a foreground service (US-66, US-69);
- no Google service (a TWA depends on a browser, often Chrome);
- F-Droid inclusion, which refuses apps that are only a website wrapper (TECH-09).

## Decision

Build a native app in **Kotlin** with **Jetpack Compose**. The domain rules are rewritten in a pure Kotlin module (`:core`) shared with the relay, and checked against the prototype's scenarios and the recorded OJP answers.

## Baseline (Sprint 10, TECH-10)

Kotlin 2.4, Jetpack Compose (BOM 2026.08) with Material 3, Android Gradle plugin 9.4 (Kotlin built in) on Gradle 9.6, minSdk 26 (Android 8.0), compileSdk and targetSdk 37. Application ID `io.github.tiagsant.spt` (TECH-13: from the PO's GitHub Pages domain, final once published).

## Consequences

- More work than a wrapper (≈ 11 one-week sprints for parity), but every Android feature is available and the app is accepted by F-Droid.
- The prototype's 5,400 lines of JavaScript are a specification, not code to reuse; its tests become the parity checklist (TECH-21).
- Rejected: Capacitor (background work and alarms through plugins, web code hard to test against Android lifecycles); TWA (needs a browser, no background work).
