extends SceneTree
## Headless test runner.
## Usage: Godot --headless --path . -s tests/run_tests.gd
## Exit code 0 when every check passes, 1 otherwise.

const MAIN_SCENE := "res://scenes/main/main.tscn"
const REQUIRED_ACTIONS := [
	"move_forward", "move_back", "move_left", "move_right",
	"run", "mouse_capture", "mouse_release",
]

var _checks := 0
var _failures := 0


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	_test_input_actions()
	await _test_spawn_on_floor()
	await _test_walk()
	await _test_run()
	await _test_camera_relative_movement()
	_test_pitch_is_clamped()
	await _test_wall_blocks_player()
	await _test_respawn_after_fall()
	print("\n%d checks, %d failures" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


# --- tests -------------------------------------------------------------

func _test_input_actions() -> void:
	for action in REQUIRED_ACTIONS:
		_check(InputMap.has_action(action) and not InputMap.action_get_events(action).is_empty(),
			"input action '%s' exists with an event" % action)


func _test_spawn_on_floor() -> void:
	var main := await _spawn_main()
	await _frames(60)
	var player := _player(main)
	var spawn: Vector3 = main.spawn_transform.origin
	_check(player.is_on_floor(), "player rests on the floor after spawn")
	_check(_horizontal(player.global_position - spawn).length() < 0.05, "player stays at spawn point")
	_check(absf(player.global_position.y) < 0.05, "player feet at ground level (y=%.3f)" % player.global_position.y)
	await _free(main)


func _test_walk() -> void:
	var main := await _spawn_main()
	var player := _player(main)
	var start := player.global_position
	await _hold(["move_forward"], 60)
	var moved := _horizontal(player.global_position - start)
	_check(moved.length() > 1.6 and moved.length() <= player.walk_speed + 0.01,
		"walking 1 s covers ~walk_speed (%.2f m)" % moved.length())
	_check(moved.normalized().dot(Vector3.FORWARD) > 0.99, "W moves towards camera forward (-Z)")
	await _free(main)


func _test_run() -> void:
	var main := await _spawn_main()
	var player := _player(main)
	var start := player.global_position
	await _hold(["move_forward", "run"], 60)
	var moved := _horizontal(player.global_position - start).length()
	_check(moved > 5.0 and moved <= player.run_speed + 0.01, "running 1 s covers ~run_speed (%.2f m)" % moved)
	await _free(main)


func _test_camera_relative_movement() -> void:
	var main := await _spawn_main()
	var player := _player(main)
	_camera(main).apply_look(Vector2(-PI / 2.0, 0.0)) # turn 90° left
	var start := player.global_position
	await _hold(["move_forward"], 30)
	var moved := _horizontal(player.global_position - start).normalized()
	_check(moved.dot(Vector3.LEFT) > 0.99, "after turning camera left, W moves towards -X")
	await _hold(["move_right"], 30)
	await _free(main)


func _test_pitch_is_clamped() -> void:
	var camera := CameraController.new()
	var arm := SpringArm3D.new()
	arm.name = "SpringArm3D"
	camera.add_child(arm)
	root.add_child(camera)
	camera.apply_look(Vector2(0.0, 100.0))
	_check(is_equal_approx(camera.pitch, deg_to_rad(camera.min_pitch_deg)), "pitch clamped at min looking down")
	camera.apply_look(Vector2(0.0, -100.0))
	_check(is_equal_approx(camera.pitch, deg_to_rad(camera.max_pitch_deg)), "pitch clamped at max looking up")
	camera.free()


func _test_wall_blocks_player() -> void:
	# The test world has a 1 m thick wall whose near face is at z = -9.5.
	var main := await _spawn_main()
	var player := _player(main)
	await _hold(["move_forward", "run"], 240) # could travel 24 m without the wall
	var z := player.global_position.z
	_check(z > -9.5, "wall stops the player (z=%.2f)" % z)
	_check(z < -8.5, "player actually reached the wall (z=%.2f)" % z)
	await _free(main)


func _test_respawn_after_fall() -> void:
	var main := await _spawn_main()
	var player := _player(main)
	player.global_position = Vector3(0.0, -100.0, 0.0)
	await _frames(2)
	_check(player.global_position.distance_to(main.spawn_transform.origin) < 0.5,
		"player below fall limit returns to spawn")
	await _free(main)


# --- helpers -----------------------------------------------------------

func _spawn_main() -> Node:
	var main: Node = load(MAIN_SCENE).instantiate()
	root.add_child(main)
	await _frames(30) # let the player settle on the floor
	return main


func _free(node: Node) -> void:
	node.queue_free()
	await _frames(1)


func _player(main: Node) -> PlayerController:
	return main.get_node("Player") as PlayerController


func _camera(main: Node) -> CameraController:
	return main.get_node("Player/CameraPivot") as CameraController


func _hold(actions: Array, frames: int) -> void:
	for action in actions:
		Input.action_press(action)
	await _frames(frames)
	for action in actions:
		Input.action_release(action)


func _frames(count: int) -> void:
	for i in count:
		await physics_frame


func _horizontal(v: Vector3) -> Vector3:
	return Vector3(v.x, 0.0, v.z)


func _check(condition: bool, label: String) -> void:
	_checks += 1
	if condition:
		print("PASS  ", label)
	else:
		_failures += 1
		printerr("FAIL  ", label)
