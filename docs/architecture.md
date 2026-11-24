# Architecture

City data and game are decoupled:

1. **Sources** (`data/source/`): raw downloads, never modified, each with a provenance file.
2. **Pipeline** (`tools/`, Python, runs outside Godot): analysis (`geo_processor`) and 3D generation (`geometry_generator`) write `data/processed/` and `generated/`.
3. **Godot** loads `generated/` resources.
4. **Player changes** live in `user://` (save game, building overrides), separate from sources and generated files.

## Godot scenes

```text
main.tscn (WorldManager)          spawn, respawn, save/load of the player
├── WorldEnvironment, Sun
├── World: resistance_world.tscn  (ResistanceWorld) metadata, collisions, spawn point, attribution
│   ├── Terrain    terrain.glb
│   ├── Streets    streets.glb
│   ├── Sidewalks  sidewalks.glb
│   ├── Buildings  (BuildingManager) buildings.glb + overrides
│   └── SpawnPoint
└── Player: player.tscn           (PlayerController + CameraController)
```

The proposed `streets.tscn` / `sidewalks.tscn` / `buildings.tscn` are the generated GLB scenes themselves; a wrapper scene per layer adds nothing yet. The test world used by movement tests lives in `tests/scenes/`.

## Scripts

| Script | Responsibility |
| --- | --- |
| `scripts/world/world_manager.gd` | Finds the world's `SpawnPoint`, places/respawns the player, saves and restores the player position |
| `scripts/world/geo_reference.gd` | Only place that converts EPSG:32721 ↔ Godot (`x = E - E0`, `y = h`, `z = -(N - N0)`); 64-bit floats for projected values |
| `scripts/world/resistance_world.gd` | Loads `scenario.json`, adds trimesh collisions to terrain/streets/sidewalks, places spawn, shows attribution |
| `scripts/buildings/building_manager.gd` | Loads buildings by persistent id, adds collisions, applies the facade material and colour, applies overrides (remove, recolor, replace model, add) |
| `assets/materials/facade.gdshader` | Stylized windows, shopfront and cornice in world space (meshes have no UVs); per-building colour via instance uniforms |
| `scripts/player/player_controller.gd` | `CharacterBody3D` movement relative to camera yaw, walk/run, gravity, curb step-up (≤ 0.3 m) |
| `scripts/player/camera_controller.gd` | Third-person orbit camera, pitch limits, `SpringArm3D` wall avoidance, mouse capture |

No streaming yet: the scenario is small. A future streaming layer would load per-sector GLBs listed in `scenario.json` `resources`.

## Tests

- `Godot --path . -s tests/render_snapshot.gd -- OUTPUT_DIR`: renders `street_level.png` and `overview.png` (needs a window; for visual review).

- `Godot --headless --fixed-fps 60 --path . -s tests/run_tests.gd`: input, movement, camera, collisions, geo conversion, world loading, overrides, street/sidewalk traversal, persistence.
- `tools/.venv/bin/python -m unittest discover -s tests/tools`: geographic analysis and 3D generation.
