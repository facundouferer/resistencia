class_name WorldManager
extends Node3D
## Loads the active world, places the player at its spawn point and
## respawns the player when it falls below the world.

@export var world_path: NodePath = ^"World"
@export var player_path: NodePath = ^"Player"
## Name of the Marker3D inside the world scene that defines the spawn.
@export var spawn_point_name := "SpawnPoint"
## Below this height (metres) the player is returned to the spawn point.
@export var fall_limit_y := -50.0

var world: Node3D
var player: CharacterBody3D
var spawn_transform := Transform3D.IDENTITY


func _ready() -> void:
	world = get_node(world_path) as Node3D
	player = get_node(player_path) as CharacterBody3D
	var spawn := world.find_child(spawn_point_name, true, false) as Node3D
	if spawn == null:
		push_error("WorldManager: spawn point '%s' not found in %s" % [spawn_point_name, world.name])
	else:
		spawn_transform = spawn.global_transform
	respawn_player()


func _physics_process(_delta: float) -> void:
	if player.global_position.y < fall_limit_y:
		respawn_player()


func respawn_player() -> void:
	player.global_position = spawn_transform.origin
	player.velocity = Vector3.ZERO


func get_debug_info() -> Dictionary:
	return {
		"world": world.name,
		"spawn": spawn_transform.origin,
		"player_position": player.global_position,
	}
