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

## Phase 2 — Real geography (2026-11-24)

### Delivered

- Python 3.13 venv in `tools/.venv` (git-ignored), pinned in `tools/requirements.txt` (pyproj 3.8.0, shapely 2.2.0, osmium 4.3.2, trimesh 5.2.2). Homebrew Python was already installed; nothing new installed system-wide.
- `tools/osm_importer/fetch_osm.py` + query: raw OSM download with provenance, never overwrites.
- `tools/geo_processor/analyze_area.py` + `areas/resistencia_2x2.json`: corners, blocks, measurements, building assignment, GeoJSON/SVG outputs.
- `tests/tools/test_analyze_area.py`: synthetic-grid tests, projection round trip, real-area check.
- `docs/geographic-data.md`: source, license, coordinates, origin, axes, known gaps.

### Validation

| Command | Result |
| --- | --- |
| `fetch_osm.py` | 2,741 elements, 712 KB, SHA-256 recorded |
| `analyze_area.py` | 4 corners, 4 blocks, sides 118.9–121.6 m |
| `tools/.venv/bin/python -m unittest discover -s tests/tools` | 6 tests OK |
| `preview.svg` visual check | 2 × 2 grid and block_s buildings render as expected |

### Missing buildings — decision (2026-11-24)

User chose option A: complete the 3 empty blocks with Overture Maps buildings (release 2026-11-18.0), OSM first.

- Added `tools/overture_importer/fetch_overture.py` (pinned release, provenance, no overwrite) and the `overturemaps` 2.1.1 dependency (official client; needed to read Overture's GeoParquet by bbox).
- `analyze_area.py --extra-buildings`: merges Overture footprints where they do not duplicate OSM; per-building source, dataset and confidence.
- Result: 172 buildings (39 OSM + 133 machine-learned), 0 duplicates dropped. Tests: 9 OK. Preview checked visually.

### Remaining known gaps

- No height data in any source; street widths missing; ML footprints are approximate. See `docs/geographic-data.md`.

## Phase 3 — 3D scenario generation (2026-11-24)

- `tools/geometry_generator/generate_scene.py` + config → `generated/resistencia/` (terrain, streets, sidewalks, buildings GLB + `scenario.json`). Details: `docs/geographic-data.md`.
- Godot: `GeoReference`, `ResistanceWorld` (`scenes/world/resistance_world.tscn`), `BuildingManager` with overrides layer. Architecture: `docs/architecture.md`.
- Added dependency `mapbox-earcut` (polygon triangulation required by trimesh extrusion).

| Check | Result |
| --- | --- |
| `unittest discover -s tests/tools` | 16 tests OK (blocks match cells, one connected roadway, sidewalks closed without holes, buildings inside lots, estimated heights flagged, GLB nodes = ids, metadata fields) |
| Godot `--import` | exit 0, no errors |
| Godot tests (Phase 3 part) | geo round trip error 0.000012 m, 172 buildings loaded with collisions, overrides remove/recolor/replace/add, `buildings.glb` hash unchanged |

## Phase 4 — Player in the real scenario (2026-11-24)

- `main.tscn` now loads `resistance_world.tscn`; the placeholder world moved to `tests/scenes/` (used by movement tests via `tests/scenes/test_main.tscn`).
- Spawn on the `block_s` sidewalk, 20 m from the Pueyrredón × Santa Fe corner.
- Curb step-up added to `PlayerController` (the capsule could not climb the 0.15 m curb: test failed at y = 0.001, passes at y = 0.151 after the fix).
- Tests now run with `--fixed-fps 60` (≈ 5 s instead of ≈ 10 min of real-time waiting).

| Check | Result |
| --- | --- |
| `Godot --headless --fixed-fps 60 --path . -s tests/run_tests.gd` | 44 checks, 0 failures: spawn on sidewalk, all 12 street segments run end to end, all 4 sidewalks walked around at curb level, curb climb, 5 buildings approached and never entered |
| `Godot --headless --path . --quit-after 120` | exit 0, no errors or warnings |

### Pending manual verification (`Godot --path .`)

- [x] The city looks coherent: streets, sidewalks, building volumes, attribution text at the bottom-left (user, 2026-11-24).
- [x] Scale feels right when walking and running (user, 2026-11-24).
- [x] The camera behaves well between buildings (user, 2026-11-24).

## Phase 5 — Minimal save (2026-11-24)

- `scripts/world/player_save.gd` + `WorldManager`: player position and camera saved to `user://save/player.json` on window close and every 10 s, restored on start. Format: `docs/persistence.md`.
- Also added `README.md` and `docs/decisions.md`.

| Check | Result |
| --- | --- |
| Godot test suite | 54 checks, 0 failures: position restored after restart (0.000 m error), camera yaw restored, invalid/foreign saves ignored, save stores EPSG:32721 and survives an origin change, sources and generated files unchanged (raw OSM still matches its download SHA-256) |
| `unittest discover -s tests/tools` | 16 tests OK |
| `Godot --headless --path . --quit-after 120` | exit 0, no errors or warnings |

### Pending manual verification

- [x] Close the game window and open it again: the player appears where it was (user, 2026-11-24).

## Fix — curb could not be climbed in manual play (2026-11-24)

- User report: "hay un problema con la acera que no puedo subir".
- Reproduced with a new test (4 blocks × walk/run × straight/45°): only 4/16 approaches climbed the curb. The earlier single test passed by chance.
- Cause: the capsule's rounded bottom rests on the curb edge (contact normal ~50°), so `is_on_floor()` is false and the step-up never ran. Also the step check used the velocity, which `move_and_slide` cancels against the curb.
- Fix: step-up uses the intended motion, probes 2 cm above the floor, and accepts "ground within 10 cm below" instead of `is_on_floor()`.
- Result: 16/16 approaches; Godot suite 55 checks, 0 failures.

## Procedural facades (2026-11-24)

- User feedback: scale OK, building footprints coherent, "todavía no tienen la forma o el color de los edificios". User chose procedural facades.
- Generator: cornice ledge + deterministic facade colour per building (`appearance`, flagged estimated). Godot: facade shader, `BuildingManager` applies it; colour overrides now change the facade colour.
- Checks: pipeline 17 tests OK; Godot suite 56 checks, 0 failures; `tests/render_snapshot.gd` screenshots reviewed (street level and overview render windows, shopfronts, cornices, varied colours; no shader errors).
- Limits: stylized only; ML footprints have stair-stepped outlines; all buildings are 2 levels (no height data).

## Trees and street lamps (2026-11-24)

- User: "agregá los árboles y las farolas" (manual tests reported as working).
- OSM has no trees or lamps inside the 4 blocks; 29 lie in the 40 m margin beyond Alvear and Mitre: 15 broadleaf trees, 6 palms (by OSM `genus`), 8 street lamps. 3 fall on the modelled roadway of Alvear (warning in metadata; the real avenue may have a median, not verified).
- Generator: `props` in `scenario.json` (OSM position, species, surface, estimated height, lamp facing to nearest street). Godot: `PropManager` + generic models in `assets/vegetation/` and `assets/props/` with trunk/pole collisions.
- Regression found while testing: curb climb failed 1/16 (block_w, walking). Cause: the capsule rides the curb edge with contact normals oscillating around the 45° floor limit. Fix: step detection by contact height (3–30 cm) instead of normal angle. Curb matrix widened to 80 approaches (2 sides × 4 blocks × walk/run × 5 angles): 80/80.
- Checks: pipeline 18 tests OK; Godot suite 60 checks, 0 failures; render snapshot `trees_and_lamps.png` reviewed.

## Fix — could not step down from the curb in some places (2026-11-24)

- User report: "hay lugares donde subo al cordón y luego no puedo bajar".
- Not reproduced by mid-side, corner or shallow-angle tests (122/122 each way). Reproduced from the user's autosave position (23.73, 0.15, -17.86), sidewalk of block_e near Pueyrredón × Santa Fe: 5 of 16 directions blocked.
- Cause: the capsule's centre 5 mm inside the kerb; its rounded bottom rests on the edge (floor normal tilted ~8° outward) and floor snapping pulled it back onto the edge every frame.
- Fix: `PlayerController._release_edge_snap` turns floor snapping off for the frame when the floor normal is tilted and the player moves towards the side it falls to.
- Regression test: standing on the kerb edge every 7 m around every block (+ the reported spot), 3 directions each: old controller 645/669, fixed 669/669. Descend matrix (122 approaches) added too.

## Street trees and photo-based buildings (2026-11-24)

- Survey of 16 block sides delegated to an agent using Mapillary (see `docs/geographic-data.md`). Author name corrected after checking the viewer caption (`federicopertile`).
- Generator `--reference`: 91 street trees on sidewalks; 73 buildings with observed levels/colour/ground floor; facade shader supports shopfront / residential / garage ground floors. First attempt matched only 4 buildings (band of 4 m from the kerb line); widened to the first 15 m of the lot → 73.
- Attribution label now spans the screen width and wraps (it was cut off).
- Checks: pipeline 21 tests OK (incl. synthetic reference observations, faces in sync); Godot suite 62 checks, 0 failures; render snapshots reviewed.
