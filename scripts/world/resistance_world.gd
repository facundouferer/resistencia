class_name ResistanceWorld
extends Node3D
## Geographic world: loads scenario metadata, gives static collisions to the
## generated terrain, street and sidewalk meshes and places the spawn point.
## Buildings are loaded through the BuildingManager child, after metadata
## (children run _ready before their parent, so the parent drives loading).

@export_file("*.json") var metadata_path := "res://generated/resistencia/scenario.json"
@export var collision_roots: Array[NodePath] = [^"Terrain", ^"Streets", ^"Sidewalks"]
@export var spawn_point_path: NodePath = ^"SpawnPoint"

var metadata: Dictionary = {}
var geo: GeoReference


func _ready() -> void:
	metadata = load_metadata(metadata_path)
	if metadata.is_empty():
		push_error("ResistanceWorld: cannot load scenario metadata at %s" % metadata_path)
		return
	geo = GeoReference.from_metadata(metadata)
	for path in collision_roots:
		add_static_collisions(get_node(path))
	($Buildings as BuildingManager).load_buildings(metadata)
	var spawn := metadata["spawn"] as Dictionary
	(get_node(spawn_point_path) as Node3D).position = Vector3(spawn["x"], spawn["y"], spawn["z"])
	$Attribution/Label.text = "Map data: %s (%s)" % [metadata.get("attribution", ""), metadata.get("license", "")]


static func load_metadata(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	if text.is_empty():
		return {}
	var data = JSON.parse_string(text)
	return data if data is Dictionary else {}


## Adds a trimesh StaticBody3D to every mesh under root. Returns the count.
static func add_static_collisions(root: Node) -> int:
	var count := 0
	for mesh in root.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).create_trimesh_collision()
		count += 1
	return count


func get_debug_info() -> Dictionary:
	return {
		"scenario": metadata.get("name", ""),
		"projection": metadata.get("projection", ""),
		"buildings": ($Buildings as BuildingManager).buildings.size(),
	}
