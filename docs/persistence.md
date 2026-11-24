# Persistence

Player data and game modifications are stored in Godot's `user://` directory, never in `data/` or `generated/`.

| Data | Path | Written by |
| --- | --- | --- |
| Player position | `user://save/player.json` | `WorldManager` (window close + autosave every 10 s) |
| Building modifications | `user://overrides/buildings.json` | Not written by the game yet; read by `BuildingManager` |

`user://` on macOS: `~/Library/Application Support/Godot/app_userdata/Resistencia 3D/`.

## Player save (`PlayerSave`, version 1)

```json
{
  "version": 1,
  "scenario": "resistencia_2x2",
  "saved_at_utc": "2026-11-24T01:00:00",
  "position": {"projection": "EPSG:32721", "easting": 303686.29, "northing": 6962349.93, "height": 0.15},
  "godot_position": [14.29, 0.15, 23.07],
  "camera": {"yaw": 1.0, "pitch": -0.26}
}
```

- `position` (projected coordinates) is preferred on load, so a save survives a change of the scenario's local origin. `godot_position` is the fallback for non-geographic worlds.
- A save from another scenario, another version, or an unreadable file is ignored and the player starts at the spawn point.
- To reset: delete `user://save/player.json`.

## Building overrides (version 1)

```json
{
  "version": 1,
  "buildings": {
    "<building id>": {"removed": true},
    "<building id>": {"color": "#rrggbb"},
    "<building id>": {"replacement_scene": "res://assets/buildings/custom.tscn"}
  },
  "added": [{"id": "custom_1", "scene": "res://assets/buildings/custom.tscn", "position": [0, 0.15, 0]}]
}
```

Building ids are the persistent ids from `generated/resistencia/scenario.json` (`osm_way_<id>`, `osm_relation_<id>`, `overture_<GERS id>`). Unknown ids are reported and skipped. Replacement models are placed on the footprint centroid at curb level.
