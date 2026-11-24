# Progress — Resistencia 3D

## Phase 0 — Environment inspection (2026-11-23)

### Initial repository state

- Git repository on branch `main`, no commits.
- Existing files: `RESISTENCIA_3D_AGENTE_BRIEFING.md` (project briefing), `.atl/skill-registry.md` (agent tooling index, unrelated to the game).
- No Godot project, scenes, scripts, assets, or geographic data existed. Nothing reusable from a previous prototype.

### Environment

| Tool | Status |
| --- | --- |
| OS | macOS 27.2.1 |
| Godot | 4.7.2.stable.official (`/Applications/Godot.app/Contents/MacOS/Godot`, not on `PATH`) |
| Python | 3.9.6 (system); `pyproj` and `shapely` not installed |
| Blender | Not installed |
| QGIS / GDAL (`ogr2ogr`) | Not installed |
| Homebrew | Available |

### Actions

- Created minimal `project.godot` (config_version 5, Forward Plus renderer, name "Resistencia 3D").
- Created `.gitignore` for Godot 4 (`.godot/` cache excluded).

### Validation

| Command | Result |
| --- | --- |
| `Godot --headless --path . --import` | exit 0 |
| `Godot --headless --path . --editor --quit` | exit 0, no errors or warnings |

Phase 0 acceptance criterion met: the repository state is known and the project imports.

### Open items

- Geographic tooling (pyproj/shapely or GDAL/QGIS) and Blender are missing; needed from Phase 2/3. Installation requires user authorization.

## Phase 1 — Executable Godot base (2026-11-23)

### Delivered

- `project.godot`: main scene, 1280×720 window, input actions (see `docs/controls.md`), physics layers `world` (1) and `player` (2).
- `scenes/main/main.tscn` + `scripts/world/world_manager.gd`: sky, sun with shadows, world instance, player, spawn handling, respawn below y = -50.
- `scenes/world/test_world.tscn`: **temporary placeholder**, not geographic data (100×100 m ground, a wall 10 m north of the spawn, two blocks).
- `scenes/player/player.tscn` + `scripts/player/player_controller.gd`: `CharacterBody3D`, capsule 1.8 m, walk/run, gravity.
- `scripts/player/camera_controller.gd`: third-person camera, mouse look with pitch limits, `SpringArm3D` wall avoidance, click capture / Escape release.
- `tests/run_tests.gd`: headless test runner.

### Decisions

- The world scene is `test_world.tscn` (not `resistance_world.tscn`) because it is a placeholder; Phase 4 replaces it.
- Only the player's `Visual` node rotates, so camera yaw and character facing stay independent.

### Validation

| Command | Result |
| --- | --- |
| `Godot --headless --path . --import` | exit 0, no errors |
| `Godot --headless --path . --quit-after 120` | exit 0, no errors |
| `Godot --headless --path . -s tests/run_tests.gd` | 19 checks, 0 failures (input map, spawn on floor, walk 1.92 m in 1 s, run 5.15 m in 1 s, camera-relative movement, pitch clamp, wall collision, respawn) |

### Pending manual verification

Headless mode cannot check rendering or real mouse input. To verify by hand (`Godot --path .`):

- [x] The scene renders with sky, light and shadows (confirmed by user, 2026-11-23).
- [x] Left click captures the mouse and mouse movement rotates the camera (confirmed by user, 2026-11-23).
- [x] Escape releases the cursor (confirmed by user, 2026-11-23).
- [x] The camera does not go through the wall or the blocks (confirmed by user, 2026-11-23).

Phase 1 acceptance criteria met.
