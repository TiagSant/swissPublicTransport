# ADR-0004 — Maps with MapLibre and OSM data; walking routes through the relay

**Status:** Accepted (PO, 20.11.2026, TECH-13). The tile provider is still chosen in Sprint 13 (US-78).

## Context

The prototype uses Leaflet with `tile.openstreetmap.org` tiles, which OSM's tile usage policy does not allow for a distributed app, and calls the FOSSGIS OSRM server for walking routes directly from the browser.

## Decision

- **MapLibre Native Android** (BSD licence) for maps: platform map, walks, map point picking.
- Tiles from an OSM-based provider that allows app use without a proprietary SDK; the provider is chosen in a spike in Sprint 13 (US-78) and recorded here.
- **Walking routes** go through the relay, which calls an OSRM foot profile (FOSSGIS or our own instance) and caches routes; the app keeps its own cache (as the prototype: 200 routes, 30 days). Without routing: straight line × 1.3.

## Consequences

- No direct dependency on community servers from every phone; their usage policies are respected by the relay's cache.
- Attribution "© OpenStreetMap contributors" shown on every map.
