# Real-data validation — transport.opendata.ch (survey of 10 Nov 2026)

TECH-01 (#10), run from a browser against 12 stops: Bel-Air, Cornavin, Molard, Eaux-Vives (tram and station), Petit-Lancy Les Esserts, Genève-Aéroport, Nyon, Lancy-Pont-Rouge, Champel, Annemasse, and the Pâquis and Jardin-Anglais piers.

## Observed categories → mode in the app

| `category` | `number` (examples) | Operator | Mode | Label shown |
|---|---|---|---|---|
| `T` | 12, 14, 15, 17, 18 | TPG | tram | `12` |
| `B` | 1, 2, 3 … 92, 23, 28 | TPG | bus | `3` |
| `B` | L1, L2, C33, C43 | SNCF | bus (rail replacement / TER coach) | `L1` |
| `BAT` | M1, M2, M3 | MGsa (Mouettes) | boat | `M2` |
| `R` | L1, L2, L3, L4 | SBB | train (Léman Express) | `L4` |
| `TER` | L2, L3, C33, C43 | SNCF | train | `L2` (merged with `R L2`) |
| `R` | 55 | NStCM | train | `R 55` |
| `RE` | 33 | SBB | train | `RE 33` |
| `IR` / `IC` | 15, 57, 90, 95 / 1 | SBB | train | `IR 90`, `IC 1` |
| `IR` | 001943 (run number) | SBB | train | `IR` (planned fallback) |

All these codes were already covered by the `CATS` mapping; no change needed.

## Other fields
- **`passList` present everywhere**, boats included (2 entries). Direction filtering (US-05) works: the 2nd entry is taken as the next stop.
- **`stop.platform`**: TPG stop letter (A–Z), SBB track number, `null` for boats and at Annemasse.
- **`stop.delay` and `prognosis.departure`**: filled for TPG, Mouettes and most trains; `null` on some IR and RE.
- **Search**: a short name also returns stops outside the area ("Bel-Air" → "Bel-Air LEB" in Lausanne); they are correctly filtered out by the area.
- **`null` stop icon** on some piers and on "Bains des Pâquis". Fix: names ending in "(lac)" are treated as boats.
- CGN piers (e.g. Jardin-Anglais) had no departures at survey time (probably the winter timetable). To be re-checked in season.
