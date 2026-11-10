# swissPublicTransport

An Android public transport app: Geneva first (Unireso / TPG, Léman Express, Mouettes, CGN), then Lausanne, then the whole of Switzerland.

Before moving to an APK, each sprint ships a **standalone prototype**: a web page that runs in a browser with no server or install.

## Guiding principle (product requirements)

The app adapts to its user:
- the most-used lines and stops are preselected and shown first;
- upcoming departures are reachable in as few gestures as possible;
- routes follow the user's priority (fastest, least walking, …).

## Prototypes

Live on GitHub Pages: https://tiagsant.github.io/swissPublicTransport/

| Sprint | Folder | Content |
|---|---|---|
| 1 | [`prototypes/sprint-01-departs`](prototypes/sprint-01-departs/index.html) | Stop search (Unireso area), real-time departures, line selection, frequent stops |
| 2 | [`prototypes/sprint-02-directions`](prototypes/sprint-02-directions/index.html) | Filter by direction (line + next stop), compatible with Sprint 1 preferences |
| 3 | [`prototypes/sprint-03-habitudes`](prototypes/sprint-03-habitudes/index.html) | Automatic preselection of usual lines (US-06); tap a departure to see its next stops |

> **Language policy.** From Sprint 4 on, everything on GitHub is in English: code, comments, docs, issues and pull requests. The app UI is English by default and French when the phone is set to French. Prototypes 1–3 predate this rule and are kept as historical snapshots, unchanged.

## Data

[transport.opendata.ch](https://transport.opendata.ch): open API, no key, CORS enabled, covering the official Swiss timetable with real-time data when available.
- `/v1/locations`: stop search (by name or by coordinates)
- `/v1/stationboard`: upcoming departures at a stop (`passList` is used to identify the direction)

Real-data findings (category codes, operators, fields) are in [`docs/real-data-validation.md`](docs/real-data-validation.md).

Preferences (visited stops, hidden lines and directions, usage scores per direction) are stored in the device's `localStorage` under the `tpp:` prefix.

## Tests

End-to-end tests with Playwright. The API is mocked with fixtures, so tests are reproducible without a network.

```bash
pip install -r tests/requirements.txt
python -m playwright install chromium   # or CHROME_PATH=/path/to/chrome
python tests/test_sprint01.py
python tests/test_sprint02.py
python tests/test_sprint03.py            # screenshots in tests/out/
```

## Workflow

- Backlog and user stories: [GitHub Issues](https://github.com/TiagSant/swissPublicTransport/issues), one milestone per sprint (conventions in [`docs/backlog.md`](docs/backlog.md))
- One branch and one pull request per sprint, code-reviewed by the product owner
