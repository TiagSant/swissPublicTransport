# ADR-0005 — The web prototype is frozen and is the MVP's functional reference

**Status:** Accepted (PO, 20.11.2026)

## Context

Nine one-week sprints of web prototypes (November 2026) validated the product with the PO. The PO decided that earlier sprints are not revisited and that the latest prototype is the reference for the MVP.

## Decision

- The Sprint 9 prototype moves to [`prototype/`](../../../prototype/index.html) and stays usable on GitHub Pages. Its behaviour is frozen: only fixes that keep it running (paths, data source changes) are allowed.
- Prototypes of Sprints 1–8 are removed from `main`; they stay available under the git tag [`prototypes-sprint-01-09`](https://github.com/TiagSant/swissPublicTransport/tree/prototypes-sprint-01-09) (commit `5b92173`, created by the `repo-cleanup.yml` workflow).
- The prototype's Playwright tests stay in `tests/` and keep passing; each Android story ports the scenarios of its area (parity).

## Consequences

- New features go to the Android app only; the prototype is not extended.
- The prototype keeps calling OJP with the rider's own key until the relay exists; it can then be pointed at the relay for the audit tool.

## Exceptions decided by the PO

- **23.11.2026 — warnings sent with their alternatives** (US-89 #196). A missed change, a cancelled vehicle or a late start is notified once its alternatives are found, with the best one (after 20 s at most), instead of first notifying and then searching. Changed in the prototype too, so that the PO has it in the field and the Android parity tests replay the same behaviour (`test_warn_with_alternatives`).
