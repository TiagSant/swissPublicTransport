# How we work

## Roles

- **Product owner (PO):** Tiago. Writes requirements, sets priorities, accepts stories at the sprint review, reviews every APK.
- **Developer:** Claude. Writes the code, the tests and the docs, keeps the backlog up to date, proposes estimates and technical decisions.

## Sprints

- **One week**, Monday to Friday. Sprint 10 starts on 23.11.2026 (Sprints 1–9 were the web prototypes).
- **Planning** (Monday): the PO confirms the sprint's stories, in priority order; stories that are not *ready* stay out.
- **Review** (Friday): demo on an APK (from Sprint 12) or on the relay; the PO accepts or reopens each story. Code review happens on the sprint's pull requests.
- **Capacity:** about **20 points** per sprint. Unfinished stories go back to the top of the next sprint and are not re-estimated.

## Backlog in GitHub

- **Issues** hold the stories; one **milestone** per sprint (with its Friday as due date), plus *Later (after MVP)*.
- Title prefixes: `US-xx` user story, `TECH-xx` technical task, `BUG-xx` bug. Numbers continue those of the prototype (next free: US-96, TECH-22, BUG-26).
- User story format: *As a … I want … so that …*, then acceptance criteria as checkboxes, the **prototype reference** (issues and tests) and dependencies. Templates in `.github/ISSUE_TEMPLATE/`.

### Labels

| Group | Labels | Meaning |
|---|---|---|
| Type | `user-story`, `tech`, `bug`, `documentation` | Kind of item |
| Scope | `mvp` | In the first Android release |
| Priority | `P0` · `P1` · `P2` · `P3` | **P0** MVP blocker, nothing ships without it · **P1** needed for parity with the prototype · **P2** after the MVP · **P3** idea, to refine |
| Size | `pts: 1` `pts: 2` `pts: 3` `pts: 5` `pts: 8` `pts: 13` | Story points (Fibonacci), relative effort and risk |
| Area | `area: foundation` `area: relay` `area: departures` `area: journeys` `area: alarms` `area: following` `area: release` | Part of the product |
| Other | `po-decision`, `accessibility`, `duplicate`, `wontfix` | A decision the PO must take; closing reasons |

### Story points

| Points | Typical size |
|---|---|
| 1 | A setting, a text, a decision recorded |
| 2 | A small screen element or rule with its tests |
| 3 | One screen or one rule set, well known from the prototype |
| 5 | A feature with several screens or Android services |
| 8 | A feature with live data, background work or many cases |
| 13 | Too big for comfort: split it if possible before the sprint starts |

## Definition of ready

- Written as a story with acceptance criteria, prototype references and dependencies; estimated; prioritised; dependencies done or in the same sprint before it.

## Definition of done

- Acceptance criteria met and checked by tests: unit tests in `:core`, UI tests for screens, and the **prototype scenarios of the area replayed** (same inputs, same results).
- No Google dependency; strings in the 5 languages; light and dark themes; TalkBack labels on controls.
- CI green; docs updated (README, spec or ADR when a behaviour or decision changes).
- Merged into `main` through a pull request that closes its issues (`Closes #n`).
- Shown to the PO at the sprint review; APK attached to the GitHub release when the sprint ships one.

## Branches and pull requests

- `main` is always buildable; it is what GitHub Pages serves (`prototype/`, `docs/`).
- One branch per story or bug: `us-72-stop-search`, `tech-10-android-skeleton`, `bug-24-…`. Branches are deleted after merge (repository setting *Automatically delete head branches*; the manual workflow `repo-cleanup.yml` removes any merged branch left over, after checking its commit was merged).
- Pull requests reference their issues and the sprint milestone; they are merged once CI passes. The PO reviews APK releases.
- Commits and PRs in English. No rewrite of published history.

## Releases

- From Sprint 12, each sprint ends with a tagged pre-release `v0.<sprint>.0` and its APK (signed with the project's release key, stored as a repository secret).
- The MVP is `v1.0.0`, published on GitHub and submitted to F-Droid.
