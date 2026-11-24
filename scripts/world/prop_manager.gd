class_name PropManager
extends Node3D
## Vegetation and street furniture layer. Places one generic model per OSM
## tree / street lamp listed in scenario.json "props", scaled uniformly to
## its (usually estimated) height. Models live in assets/ and can be
## swapped without touching the geographic data.

## type -> [scene, nominal height in metres]
@export var models := {
	"tree": [preload("res://assets/vegetation/tree_broadleaf.tscn"), 8.0],
	"palm": [preload("res://assets/vegetation/tree_palm.tscn"), 6.0],
	"street_lamp": [preload("res://assets/props/street_lamp.tscn"), 6.0],
}

var props: Dictionary = {}  # id -> Node3D


func load_props(metadata: Dictionary) -> void:
	for entry in metadata.get("props", []):
		var model: Array = models.get(entry["type"], [])
		if model.is_empty():
			push_warning("PropManager: no model for prop type '%s'" % entry["type"])
			continue
		var node := (model[0] as PackedScene).instantiate() as Node3D
		node.name = entry["id"]
		node.position = GeoReference.local_to_godot(entry["position"], float(entry["base_y"]))
		node.scale = Vector3.ONE * (float(entry["height_m"]) / float(model[1]))
		var facing: Array = entry.get("facing", [])
		if entry["type"] == "street_lamp" and facing.size() == 2 and Vector2(facing[0], facing[1]).length() > 0.01:
			# Model arm points to -Z; local [x, y] maps to Godot (x, -y).
			node.rotation.y = atan2(-facing[0], facing[1])
		add_child(node)
		props[entry["id"]] = node
