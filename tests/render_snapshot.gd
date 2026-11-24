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
	var views := {"street_level": [0.6, -0.12, 4.0], "overview": [0.8, -0.6, 40.0]}
	for name in views:
		var v: Array = views[name]
		camera.yaw = v[0]
		camera.pitch = v[1]
		camera.distance = v[2]
		camera.apply_look(Vector2.ZERO)
		for i in 30:
			await process_frame
		root.get_viewport().get_texture().get_image().save_png(out_dir.path_join(name + ".png"))
	quit()
