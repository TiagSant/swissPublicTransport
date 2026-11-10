# SBB pictograms and timetable icons

The SVG files in this folder are copied **unmodified** from SBB's public design-system repositories:

| Folder | Source | Commit | File licence |
|---|---|---|---|
| `pictograms/` | [sbb-design-systems/picto-library](https://github.com/sbb-design-systems/picto-library) (`pictos/svg-digital`) | `0b59e5c` (2026-09-10) | Apache-2.0 (`LICENSE-picto-library`) |
| `timetable/` | [sbb-design-systems/sbb-icons](https://github.com/sbb-design-systems/sbb-icons) (`icons`) | `00c3380` (2026-10-15) | Apache-2.0 (`LICENSE-sbb-icons`) |

## Brand terms of use (in addition to the file licence)

SBB's rights of use (https://digital.sbb.ch/en/foundation/brand/copyrights) reserve **public transport pictograms and timetable icons** for licensed Swiss transport companies and **projects related to public transport in Switzerland**, under these conditions:

- the elements may be neither changed nor used for other purposes;
- no commercial, political or religious use;
- any other use requires approval from SBB Brand Management (marke@sbb.ch).

This project uses them as a non-commercial Swiss public transport project, unmodified. **If the app ever becomes commercial, approval from SBB Brand Management is required first.**

SBB *UI icons* (e.g. `bus-profile-small`) are reserved for SBB and its subsidiaries and are deliberately **not** used here.

## Adding an icon

Copy the file byte-for-byte from the source repository (never edit it), add its name to `SBB_TIMETABLE_ICONS` in the prototype, and include the `-negative` variant used in dark mode.
