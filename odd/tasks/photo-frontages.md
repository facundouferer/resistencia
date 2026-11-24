# Feature: photo-based building frontages
Objective: make buildings look more like the real ones using the Mapillary observations (option A). Branch: `feat/photo-frontages`. Delivery: single PR when done. Tests: `unittest discover -s tests/tools`, Godot `tests/run_tests.gd`.

## Specs

- S1: "me gustaría que los edificios sean más parecidos a los reales" — option A as proposed: rebuild each observed frontage on the property line ("línea municipal") with the observed widths, levels and colours, as continuous party-wall rows.
- S2: Add pitched tile roofs, brick bases, balconies, and towers with their own window grid where the photos show them.
- S3: Keep data honesty: OSM surveyed footprints are not replaced; photo-derived geometry is flagged as estimated with its source; entries with unknown levels or no building (levels 0) do not create volumes.

## Tasks

| ID | Specs | Route | Status | Commit |
| --- | --- | --- | --- | --- |
| T1 | S1, S3 | inline | done | this commit |
| T2 | S2 | inline | done | this commit |
| T3 | S1–S3 | inline | done | this commit |

T1: generator builds frontage volumes from observations, replaces overlapping Overture ML footprints, fills gaps next to OSM footprints, resolves corners by levels.
T2: gable roofs, roof colour, brick base, balconies, tower window grid (generator flags + shader).
T3: tests, docs, render review, commit.

## Log

- L1 (2026-11-24, user): "me gustaría que los edificios sean más parecidos a los reales" → after proposal: "sí, avanzá con la A".
- L2: Feature vocabulary in observations is free text; matched by keywords (pitched, balcon, brick+base/bands). Levels: 14×2, 10, 6, 5×2, 4×2, 3×2, 2×14, 1×6, unknown×5, 0×2.
- L3: Results: 29 frontages, 29 Overture replaced, 39 OSM kept, 9 tile roofs, 12 balconies, 2 brick bases, 7 towers. Pipeline 25 OK, Godot 62/62, renders reviewed.
