class_name PlayerSave
extends RefCounted
## Player position persistence. Saves live in user://, never next to the
## geographic sources or generated resources.
##
## Format (JSON, version 1):
## {
##   "version": 1,
##   "scenario": "resistencia_2x2",
##   "saved_at_utc": "2026-11-24T01:00:00",
##   "position": {"projection": "EPSG:32721", "easting": 0.0, "northing": 0.0, "height": 0.0},
##   "godot_position": [x, y, z],
##   "camera": {"yaw": 0.0, "pitch": 0.0}
## }
## "position" is present only in geographic worlds; it is preferred on load so
## a save survives a change of the scenario's local origin.

const VERSION := 1


static func write(path: String, scenario: String, position: Vector3, yaw: float, pitch: float,
		geo: GeoReference = null) -> Error:
	var data := {
		"version": VERSION,
		"scenario": scenario,
		"saved_at_utc": Time.get_datetime_string_from_system(true),
		"godot_position": [position.x, position.y, position.z],
		"camera": {"yaw": yaw, "pitch": pitch},
	}
	if geo:
		var projected := geo.godot_to_projected(position)
		projected["projection"] = geo.projection
		data["position"] = projected
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(data, "  "))
	file.close()
	return OK


## Returns {} when there is no valid save for this scenario, otherwise
## {"position": Vector3, "yaw": float, "pitch": float}.
static func read(path: String, scenario: String, geo: GeoReference = null) -> Dictionary:
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	var json := JSON.new()
	var data = json.data if json.parse(FileAccess.get_file_as_string(path)) == OK else null
	if not data is Dictionary or int(data.get("version", 0)) != VERSION or data.get("scenario") != scenario:
		push_warning("PlayerSave: ignoring invalid or foreign save at %s" % path)
		return {}
	var position: Vector3
	var projected = data.get("position")
	if geo and projected is Dictionary and projected.get("projection") == geo.projection:
		position = geo.projected_to_godot(projected["easting"], projected["northing"], projected["height"])
	elif data.get("godot_position") is Array and data["godot_position"].size() == 3:
		var p: Array = data["godot_position"]
		position = Vector3(p[0], p[1], p[2])
	else:
		return {}
	var camera: Dictionary = data.get("camera", {})
	return {"position": position, "yaw": float(camera.get("yaw", 0.0)), "pitch": float(camera.get("pitch", 0.0))}
