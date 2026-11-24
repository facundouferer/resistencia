# Decisions

Decisions fixed by the briefing (engine, language, OSM, EPSG:32721, 1 unit = 1 m, glTF) are not repeated here.

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-11-23 | Movement relative to camera yaw; only the `Visual` node rotates | Camera and character facing stay independent and predictable |
| 2026-11-24 | Python venv in `tools/.venv` (Homebrew Python 3.13), pinned `tools/requirements.txt` | System Python 3.9 is outdated; no system-wide installs |
| 2026-11-24 | Local origin = Pueyrredón × Santa Fe intersection, rounded to 1 m | Real, central, stable point of the area |
| 2026-11-24 | Overture Maps buildings (release 2026-11-18.0) where OSM has none; OSM always wins | 3 of 4 blocks had no OSM buildings (user chose option A) |
| 2026-11-24 | Street layout from measured OSM sidewalk offset (6.1 m) + estimated 3 m sidewalk | No street width tags in OSM |
| 2026-11-24 | Default building height 2 levels × 3 m, flagged `height_is_estimated` | No height data in any source |
| 2026-11-24 | Collisions generated in Godot (`create_trimesh_collision`) instead of import hints | Testable in code, independent of node naming |
| 2026-11-24 | Curb step-up in `PlayerController` (≤ 0.3 m) | `CharacterBody3D` cannot climb the 0.15 m curb |
| 2026-11-24 | Save in projected coordinates in `user://` | Survives origin changes; keeps sources/generated untouched |
