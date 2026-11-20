# swissPublicTransport

An Android public transport app for Switzerland **that adapts to its rider**: usual lines and places first, next departures in one tap, journeys that follow the rider's priority (fastest or least walking), and a journey that follows the rider with alarms, live changes and alternatives.

The first release (MVP) covers **Geneva** (Unireso: TPG, Léman Express, Mouettes, CGN) and **Lausanne** (tl, including the metro). Stop search, departures and journeys work across Switzerland, with official data from [opentransportdata.swiss](https://opentransportdata.swiss). No Google service; to be published on F-Droid.

## Status

| | |
|---|---|
| **Web prototype** (functional reference, frozen) | [Open it](https://tiagsant.github.io/swissPublicTransport/prototype/) · [`prototype/`](prototype/index.html) · [docs](docs/prototype.md) |
| **Android MVP** | Sprints 10–20, from 23.11.2026 to 05.02.2027 · [roadmap](docs/product/roadmap.md) · [backlog](https://github.com/TiagSant/swissPublicTransport/milestones) |

## Repository

| Path | Content |
|---|---|
| [`prototype/`](prototype/) | The web prototype (single page, no build). MVP reference. |
| [`assets/`](assets/) | Shared data: OJP adapter, line colours, platform positions (ATLAS), SBB pictograms. |
| [`scripts/`](scripts/) | Builders for platform positions and line colours; OJP probe. |
| [`tests/`](tests/) | Playwright tests of the prototype and tests of the scripts, with recorded API answers. |
| [`tools/`](tools/) | Line colours check page; audit of change places on real data. |
| [`docs/`](docs/) | Product, architecture, data and process documentation. |
| [`.github/`](.github/) | Workflows (data updates, OJP probe, audit), issue and PR templates. |
| `android/`, `relay/` | *Coming in Sprints 10–11* — the Android app and the relay ([architecture](docs/architecture/overview.md)). |

## Documentation

- [Product vision and requirements](docs/product/vision.md)
- [MVP functional specification](docs/product/mvp-spec.md)
- [Roadmap: sprints, priorities, points](docs/product/roadmap.md)
- [Target architecture](docs/architecture/overview.md) and [decision records](docs/architecture/decisions/)
- [Data sources and licences](docs/data/data-sources.md)
- [How we work](docs/process/workflow.md)
- [Web prototype: run and test](docs/prototype.md)

## Quick start (prototype)

```bash
python -m http.server 8000      # from the repository root
# open http://localhost:8000/prototype/
```

Tests: see [docs/prototype.md](docs/prototype.md#tests).

## Licences

No licence has been chosen yet for the code (PO decision, [TECH-13](https://github.com/TiagSant/swissPublicTransport/issues/172)). Data and pictograms keep their own terms: SBB pictograms may only be used unmodified and non-commercially ([`assets/sbb/NOTICE.md`](assets/sbb/NOTICE.md)); ATLAS data from opentransportdata.swiss; line colours © OpenStreetMap contributors (ODbL). Details in [data sources](docs/data/data-sources.md).

Everything in this repository is written in English. The app speaks English, French, German, Italian and Romansh.
