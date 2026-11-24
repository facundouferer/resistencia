extends SceneTree
## Renders the main scene from fixed viewpoints and saves PNG screenshots.
## Needs a real renderer (not --headless).
## Usage: Godot --path . -s tests/render_snapshot.gd -- OUTPUT_DIR

func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	var out_dir: String = args[0] if args.size() > 0 else "user://snapshots"
	DirAccess.make_dir_recursive_absolute(out_dir)
	var main: Node = load("res://scenes/main/main.tscn").instantiate()
	main.save_path = ""
	root.add_child(main)
	var camera: CameraController = main.get_node("Player/CameraPivot")
	var player: Node3D = main.get_node("Player")
	var spawn: Vector3 = player.global_position
	# [yaw, pitch, distance, player position or null = spawn]
	var views := {
		"street_level": [0.6, -0.12, 4.0, null],
		"overview": [0.8, -0.6, 40.0, null],
		"trees_and_lamps": [2.6, -0.25, 22.0, Vector3(5, 0.2, 175)],
		"houses_escalada": [-2.33, -0.12, 9.0, Vector3(-45.2, 0.2, -125.8)],
	}
	for name in views:
		var v: Array = views[name]
		player.global_position = spawn if v[3] == null else v[3]
		camera.yaw = v[0]
		camera.pitch = v[1]
		camera.distance = v[2]
		camera.apply_look(Vector2.ZERO)
		for i in 30:
			await process_frame
		root.get_viewport().get_texture().get_image().save_png(out_dir.path_join(name + ".png"))
	quit()
