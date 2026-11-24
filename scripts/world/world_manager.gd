class_name WorldManager
extends Node3D
## Loads the active world, places the player at its spawn point (or at the
## saved position), respawns the player when it falls below the world and
## saves the player position on close and periodically.

@export var world_path: NodePath = ^"World"
@export var player_path: NodePath = ^"Player"
## Name of the Marker3D inside the world scene that defines the spawn.
@export var spawn_point_name := "SpawnPoint"
## Below this height (metres) the player is returned to the spawn point.
@export var fall_limit_y := -50.0
## Player save file; empty disables saving and loading.
@export var save_path := "user://save/player.json"
@export var autosave_interval_s := 10.0

var world: Node3D
var player: CharacterBody3D
var spawn_transform := Transform3D.IDENTITY
var _since_autosave := 0.0


func _ready() -> void:
	world = get_node(world_path) as Node3D
	player = get_node(player_path) as CharacterBody3D
	var spawn := world.find_child(spawn_point_name, true, false) as Node3D
	if spawn == null:
		push_error("WorldManager: spawn point '%s' not found in %s" % [spawn_point_name, world.name])
	else:
		spawn_transform = spawn.global_transform
	respawn_player()
	restore_player()


func _physics_process(delta: float) -> void:
	if player.global_position.y < fall_limit_y:
		respawn_player()
	_since_autosave += delta
	if autosave_interval_s > 0.0 and _since_autosave >= autosave_interval_s:
		save_player()


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		save_player()


func scenario_name() -> String:
	var metadata = world.get("metadata")
	return metadata.get("name", world.name) if metadata is Dictionary else String(world.name)


func _geo() -> GeoReference:
	return world.get("geo") as GeoReference


func save_player() -> Error:
	_since_autosave = 0.0
	if save_path.is_empty():
		return OK
	var camera := player.get_node("CameraPivot") as CameraController
	return PlayerSave.write(save_path, scenario_name(), player.global_position, camera.yaw, camera.pitch, _geo())


## Moves the player to the saved position. Returns true if a save was applied.
func restore_player() -> bool:
	var saved := PlayerSave.read(save_path, scenario_name(), _geo())
	if saved.is_empty() or saved["position"].y < fall_limit_y:
		return false
	player.global_position = saved["position"]
	player.velocity = Vector3.ZERO
	var camera := player.get_node("CameraPivot") as CameraController
	camera.yaw = saved["yaw"]
	camera.pitch = saved["pitch"]
	camera.apply_look(Vector2.ZERO)
	return true


func respawn_player() -> void:
	player.global_position = spawn_transform.origin
	player.velocity = Vector3.ZERO


func get_debug_info() -> Dictionary:
	return {
		"world": world.name,
		"spawn": spawn_transform.origin,
		"player_position": player.global_position,
		"save_path": save_path,
	}
