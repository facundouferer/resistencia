class_name BuildingManager
extends Node3D
## Loads the generated buildings, keeps them addressable by persistent id and
## applies player/designer modifications stored in a separate overrides file.
## Generated resources and geographic sources are never modified.
##
## Overrides file (JSON):
## {
##   "version": 1,
##   "buildings": {
##     "<id>": {"removed": true}
##     "<id>": {"color": "#rrggbb"}          (facade colour)
##     "<id>": {"replacement_scene": "res://path/to/model.tscn"}
##   },
##   "added": [{"id": "custom_1", "scene": "res://...", "position": [x, y, z]}]
## }

const OVERRIDES_VERSION := 1

@export var buildings_scene: PackedScene
## Stylized facade (windows, shopfront, cornice). Per-building colour comes
## from scenario.json "appearance"; it is estimated, not the real colour.
@export var facade_material: Material = preload("res://assets/materials/facade_material.tres")
@export var overrides_path := "user://overrides/buildings.json"

## id -> MeshInstance3D (generated) or Node3D (replacement / added)
var buildings: Dictionary = {}
## id -> metadata entry from scenario.json
var building_data: Dictionary = {}
var applied_overrides: Array[String] = []


func load_buildings(metadata: Dictionary) -> void:
	for entry in metadata.get("buildings", []):
		building_data[entry["id"]] = entry
	var instance := buildings_scene.instantiate()
	instance.name = "Generated"
	add_child(instance)
	for mesh in instance.find_children("*", "MeshInstance3D", true, false):
		var id := String(mesh.name)
		if not building_data.has(id):
			push_warning("BuildingManager: mesh '%s' has no metadata" % id)
		buildings[id] = mesh
		(mesh as MeshInstance3D).create_trimesh_collision()
		apply_appearance(mesh, building_data.get(id, {}))
	apply_overrides(load_overrides(overrides_path))


static func load_overrides(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not data is Dictionary or int(data.get("version", 0)) != OVERRIDES_VERSION:
		push_warning("BuildingManager: ignoring invalid overrides file %s" % path)
		return {}
	return data


func apply_overrides(overrides: Dictionary) -> void:
	var changes: Dictionary = overrides.get("buildings", {})
	for id in changes:
		if not buildings.has(id):
			push_warning("BuildingManager: override for unknown building '%s'" % id)
			continue
		var change: Dictionary = changes[id]
		if change.get("removed", false):
			remove_building(id)
		elif change.has("replacement_scene"):
			replace_building(id, load(change["replacement_scene"]))
		elif change.has("color"):
			set_building_color(id, Color(change["color"]))
		applied_overrides.append(id)
	for added in overrides.get("added", []):
		var node := (load(added["scene"]) as PackedScene).instantiate() as Node3D
		var p: Array = added["position"]
		node.name = added["id"]
		node.position = Vector3(p[0], p[1], p[2])
		add_child(node)
		buildings[added["id"]] = node
		applied_overrides.append(added["id"])


func remove_building(id: String) -> void:
	buildings[id].queue_free()
	buildings.erase(id)


func apply_appearance(mesh: MeshInstance3D, data: Dictionary) -> void:
	if facade_material == null:
		return
	mesh.material_override = facade_material
	var appearance: Dictionary = data.get("appearance", {})
	if appearance.has("facade_color"):
		mesh.set_instance_shader_parameter("facade_color", Color(appearance["facade_color"]))
	var base_y := float(data.get("base_y", 0.0))
	mesh.set_instance_shader_parameter("base_y", base_y)
	mesh.set_instance_shader_parameter("top_y", base_y + float(data.get("height_m", 0.0)))


func set_building_color(id: String, color: Color) -> void:
	(buildings[id] as MeshInstance3D).set_instance_shader_parameter("facade_color", color)


## Replaces a generated building by a custom model placed on its footprint centroid.
func replace_building(id: String, scene: PackedScene) -> void:
	var data: Dictionary = building_data.get(id, {})
	var node := scene.instantiate() as Node3D
	node.name = id
	node.position = footprint_centroid(data)
	buildings[id].queue_free()
	add_child(node)
	buildings[id] = node


static func footprint_centroid(data: Dictionary) -> Vector3:
	var rings: Array = data.get("footprint", [])
	if rings.is_empty():
		return Vector3.ZERO
	var sum := Vector2.ZERO
	var ring: Array = rings[0]
	for i in ring.size() - 1:  # last point repeats the first
		sum += Vector2(ring[i][0], ring[i][1])
	var c := sum / (ring.size() - 1)
	return GeoReference.local_to_godot([c.x, c.y], float(data.get("base_y", 0.0)))
