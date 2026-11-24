extends SceneTree
## Headless test runner.
## Usage: Godot --headless --path . -s tests/run_tests.gd
## Exit code 0 when every check passes, 1 otherwise.

const TEST_MAIN_SCENE := "res://tests/scenes/test_main.tscn"
const REAL_MAIN_SCENE := "res://scenes/main/main.tscn"
const REAL_WORLD_SCENE := "res://scenes/world/resistance_world.tscn"
const METADATA := "res://generated/resistencia/scenario.json"
const TEST_OVERRIDES := "user://test_building_overrides.json"
const TEST_SAVE := "user://test_player_save.json"
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
	# Phase 3: geographic world
	_test_geo_reference_round_trip()
	await _test_world_loads_buildings_with_collisions()
	await _test_building_overrides_do_not_touch_generated_files()
	await _test_props_are_placed_with_collisions()
	# Phase 4: player in the geographic world
	await _test_real_spawn_on_sidewalk()
	await _test_walk_every_street_segment()
	await _test_walk_every_sidewalk()
	await _test_step_from_roadway_onto_sidewalk()
	await _test_curb_climb_matrix()
	await _test_curb_descend_matrix()
	await _test_step_down_from_curb_edge()
	await _test_buildings_block_the_player()
	await _test_tree_trunk_blocks_the_player()
	# Phase 5: persistence
	await _test_position_survives_restart()
	await _test_invalid_saves_fall_back_to_spawn()
	_test_save_uses_projected_coordinates()
	DirAccess.remove_absolute(TEST_SAVE)
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


# --- Phase 3: geographic world ------------------------------------------

func _test_geo_reference_round_trip() -> void:
	var metadata := ResistanceWorld.load_metadata(METADATA)
	_check(not metadata.is_empty(), "scenario metadata loads")
	var geo := GeoReference.from_metadata(metadata)
	_check(geo.projection == "EPSG:32721", "projection is EPSG:32721")
	_check(geo.projected_to_godot(geo.origin_easting, geo.origin_northing).is_zero_approx(), "origin maps to Godot (0,0,0)")
	var worst := 0.0
	for e in [303502.41, 303842.32, 303667.47]:
		for n in [6962201.94, 6962542.27]:
			var v := geo.projected_to_godot(e, n, 1.5)
			var back := geo.godot_to_projected(v)
			worst = maxf(worst, absf(back["easting"] - e) + absf(back["northing"] - n) + absf(back["height"] - 1.5))
	_check(worst < 0.01, "projected -> Godot -> projected error < 1 cm (%.6f m)" % worst)
	var east := geo.projected_to_godot(geo.origin_easting + 10.0, geo.origin_northing + 20.0)
	_check(east.is_equal_approx(Vector3(10, 0, -20)), "east is +X and north is -Z")


func _test_world_loads_buildings_with_collisions() -> void:
	var world := await _spawn_world()
	var manager := world.get_node("Buildings") as BuildingManager
	var expected: int = world.metadata["buildings"].size()
	_check(expected == 172 and manager.buildings.size() == expected,
		"all %d generated buildings are loaded by id" % manager.buildings.size())
	var without := 0
	for id in manager.buildings:
		if manager.buildings[id].find_children("*", "StaticBody3D", true, false).is_empty():
			without += 1
	_check(without == 0, "every building has a collision body (%d missing)" % without)
	for part in ["Terrain", "Streets", "Sidewalks"]:
		_check(not world.get_node(part).find_children("*", "StaticBody3D", true, false).is_empty(),
			"%s has collision" % part)
	_check(manager.building_data[manager.building_data.keys()[0]].has("height_is_estimated"),
		"building metadata keeps the estimated-height flag")
	var first_id: String = manager.buildings.keys()[0]
	var first := manager.buildings[first_id] as MeshInstance3D
	_check(first.material_override == manager.facade_material
		and first.get_instance_shader_parameter("facade_color") == Color(manager.building_data[first_id]["appearance"]["facade_color"]),
		"buildings use the facade material with their metadata colour")
	await _free(world)


func _test_building_overrides_do_not_touch_generated_files() -> void:
	var before := FileAccess.get_sha256("res://generated/resistencia/buildings.glb")
	var metadata := ResistanceWorld.load_metadata(METADATA)
	var ids: Array = metadata["buildings"].map(func(b): return b["id"])
	var overrides := {
		"version": 1,
		"buildings": {
			ids[0]: {"removed": true},
			ids[1]: {"color": "#ff0000"},
			ids[2]: {"replacement_scene": "res://tests/scenes/replacement_box.tscn"},
		},
		"added": [{"id": "custom_test", "scene": "res://tests/scenes/replacement_box.tscn", "position": [0, 0.15, 0]}],
	}
	var file := FileAccess.open(TEST_OVERRIDES, FileAccess.WRITE)
	file.store_string(JSON.stringify(overrides))
	file.close()
	var world := await _spawn_world(TEST_OVERRIDES)
	var manager := world.get_node("Buildings") as BuildingManager
	_check(not manager.buildings.has(ids[0]), "override removes a building")
	var colored := manager.buildings[ids[1]] as MeshInstance3D
	_check(colored.get_instance_shader_parameter("facade_color") == Color("#ff0000"), "override recolors a building facade")
	_check(manager.buildings[ids[2]].scene_file_path == "res://tests/scenes/replacement_box.tscn",
		"override replaces a building model")
	_check(manager.buildings.has("custom_test"), "override adds a building")
	_check(FileAccess.get_sha256("res://generated/resistencia/buildings.glb") == before,
		"generated buildings.glb is unchanged")
	await _free(world)
	DirAccess.remove_absolute(TEST_OVERRIDES)


func _test_props_are_placed_with_collisions() -> void:
	var world := await _spawn_world()
	var manager := world.get_node("Props") as PropManager
	var entries: Array = world.metadata["props"]
	_check(entries.size() > 0 and manager.props.size() == entries.size(),
		"all %d OSM trees and street lamps are placed" % manager.props.size())
	var bad := 0
	for entry in entries:
		var node: Node3D = manager.props[entry["id"]]
		var expected := GeoReference.local_to_godot(entry["position"], float(entry["base_y"]))
		if node.position.distance_to(expected) > 0.01 or node.find_children("*", "StaticBody3D", true, false).is_empty():
			bad += 1
	_check(bad == 0, "props sit at their OSM position with a collision body (%d wrong)" % bad)
	var lamps_ok := true
	for entry in entries:
		if entry["type"] != "street_lamp":
			continue
		var arm := -(manager.props[entry["id"]] as Node3D).global_transform.basis.z
		var to_street := Vector3(entry["facing"][0], 0, -entry["facing"][1]).normalized()
		lamps_ok = lamps_ok and Vector2(arm.x, arm.z).normalized().dot(Vector2(to_street.x, to_street.z)) > 0.99
	_check(lamps_ok, "street lamp arms point to the nearest street")
	await _free(world)


# --- Phase 4: player in the geographic world -----------------------------

func _test_real_spawn_on_sidewalk() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	await _frames(30)
	var player := _player(main)
	var curb: float = main.get_node("World").metadata["estimation_rules"]["curb_height_m"]
	_check(player.is_on_floor(), "player stands on the floor in the real world")
	_check(absf(player.global_position.y - curb) < 0.05, "player spawns on the sidewalk (y=%.3f)" % player.global_position.y)
	await _free(main)


func _test_walk_every_street_segment() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var segments: Array = main.get_node("World").metadata["street_segments"]
	var failed: Array[String] = []
	for segment in segments:
		var start := GeoReference.local_to_godot(segment["from"], 0.1)
		var target := GeoReference.local_to_godot(segment["to"])
		if not await _walk_path(main, start, [target]):
			failed.append("%s %s" % [segment["street"], segment["from"]])
	_check(segments.size() == 12 and failed.is_empty(),
		"player runs along all %d street segments without getting stuck %s" % [segments.size(), failed])
	await _free(main)


func _test_walk_every_sidewalk() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var curb: float = world.metadata["estimation_rules"]["curb_height_m"]
	for block in world.metadata["blocks"]:
		var path: Array = world.metadata["blocks"][block]["sidewalk_path"]
		var points: Array[Vector3] = []
		for p in path:
			points.append(GeoReference.local_to_godot(p))
		var ok := await _walk_path(main, points[0] + Vector3(0, curb + 0.1, 0), points.slice(1), curb)
		_check(ok, "player walks around the whole sidewalk of %s on the curb level" % block)
	await _free(main)


func _test_step_from_roadway_onto_sidewalk() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var spawn := Vector3(world.metadata["spawn"]["x"], 0, world.metadata["spawn"]["z"])
	# The nearest roadway is outward from the block_s sidewalk, i.e. away from the block centre.
	var center := _ring_center(world.metadata["blocks"]["block_s"]["lot"][0])
	var outward := (spawn - center)
	outward.y = 0
	var start := spawn + outward.normalized() * 4.0 + Vector3(0, 0.1, 0)
	var ok := await _walk_path(main, start, [spawn])
	var player := _player(main)
	await _frames(10)
	_check(ok and absf(player.global_position.y - 0.15) < 0.05,
		"player climbs the 0.15 m curb from the roadway (y=%.3f)" % player.global_position.y)
	await _free(main)


## Two sides of every block, walking and running, at five angles, up and down.
func _test_curb_climb_matrix() -> void:
	await _curb_matrix(true)


func _test_curb_descend_matrix() -> void:
	await _curb_matrix(false)


func _curb_matrix(climbing: bool) -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var failed: Array[String] = []
	var total := 0
	for block in world.metadata["blocks"]:
		var path: Array = world.metadata["blocks"][block]["sidewalk_path"]
		var center := _ring_center(world.metadata["blocks"][block]["lot"][0])
		for side in 2:
			var a := GeoReference.local_to_godot(path[side])
			var b := GeoReference.local_to_godot(path[side + 1])
			var tangent := (b - a).normalized()
			var on_sidewalk := _clear_of_props(world, (a + b) / 2.0, tangent, 3.5)
			var outward := on_sidewalk - center
			outward = (outward - tangent * outward.dot(tangent)).normalized()
			for running in [false, true]:
				for angle_deg in [-45.0, -20.0, 0.0, 20.0, 45.0]:
					var dir := outward.rotated(Vector3.UP, deg_to_rad(angle_deg))
					var on_road := on_sidewalk + dir * (4.0 / cos(deg_to_rad(angle_deg)))
					var start := (on_road if climbing else on_sidewalk) + Vector3(0, 0.3, 0)
					var target := on_sidewalk if climbing else on_road
					var reached := await _walk_path(main, start, [target], -1.0, 600, running)
					await _frames(5)
					var y := _player(main).global_position.y
					var expected_y := 0.15 if climbing else 0.0
					total += 1
					if not reached or absf(y - expected_y) > 0.05:
						failed.append("%s side%d %s %d° y=%.2f" % [block, side, "run" if running else "walk", angle_deg, y])
	# Corners: leave/enter each sidewalk corner diagonally, through the intersection.
	for block in world.metadata["blocks"]:
		var center := _ring_center(world.metadata["blocks"][block]["lot"][0])
		var path: Array = world.metadata["blocks"][block]["sidewalk_path"]
		for i in path.size() - 1:
			var corner := GeoReference.local_to_godot(path[i])
			var out_dir := corner - center
			out_dir.y = 0
			var on_road := corner + out_dir.normalized() * 4.0
			for running in [false, true]:
				var start := (on_road if climbing else corner) + Vector3(0, 0.3, 0)
				var target := corner if climbing else on_road
				var reached := await _walk_path(main, start, [target], -1.0, 600, running)
				await _frames(5)
				var y := _player(main).global_position.y
				total += 1
				if not reached or absf(y - (0.15 if climbing else 0.0)) > 0.05:
					failed.append("%s corner%d %s y=%.2f" % [block, i, "run" if running else "walk", y])
	# Shallow angles: almost parallel to the kerb.
	for block in world.metadata["blocks"]:
		var path: Array = world.metadata["blocks"][block]["sidewalk_path"]
		var center := _ring_center(world.metadata["blocks"][block]["lot"][0])
		var a := GeoReference.local_to_godot(path[0])
		var b := GeoReference.local_to_godot(path[1])
		var tangent := (b - a).normalized()
		var on_sidewalk := _clear_of_props(world, (a + b) / 2.0, tangent, 6.0)
		var outward := on_sidewalk - center
		outward = (outward - tangent * outward.dot(tangent)).normalized()
		for angle_deg in [-75.0, 75.0]:
			var dir := outward.rotated(Vector3.UP, deg_to_rad(angle_deg))
			var on_road := on_sidewalk + dir * (4.0 / cos(deg_to_rad(angle_deg)))
			var start := (on_road if climbing else on_sidewalk) + Vector3(0, 0.3, 0)
			var target := on_sidewalk if climbing else on_road
			var reached := await _walk_path(main, start, [target], -1.0, 900, false)
			await _frames(5)
			var y := _player(main).global_position.y
			total += 1
			if not reached or absf(y - (0.15 if climbing else 0.0)) > 0.05:
				failed.append("%s shallow %d° y=%.2f" % [block, angle_deg, y])
	_check(failed.is_empty(), "curb %s in %d/%d approaches %s" % [
		"climbed" if climbing else "descended", total - failed.size(), total, failed])
	await _free(main)


## Regression: standing right on the kerb edge (capsule half over the road),
## floor snapping kept the player on the edge (user report, saved position
## (23.73, 0.15, -17.86) next to Pueyrredón x Santa Fe). Samples every 7 m
## along every side of every block, plus the reported position.
func _test_step_down_from_curb_edge() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var half_width: float = world.metadata["estimation_rules"]["sidewalk_width_m"] / 2.0
	var cases: Array = []  # [edge position, outward direction]
	for block in world.metadata["blocks"]:
		var path: Array = world.metadata["blocks"][block]["sidewalk_path"]
		var center := _ring_center(world.metadata["blocks"][block]["lot"][0])
		for side in path.size() - 1:
			var a := GeoReference.local_to_godot(path[side])
			var b := GeoReference.local_to_godot(path[side + 1])
			var tangent := (b - a).normalized()
			var outward := (a + b) / 2.0 - center
			outward = (outward - tangent * outward.dot(tangent)).normalized()
			var d := 7.0
			while d < a.distance_to(b) - 7.0:
				if _distance_to_props(world, a + tangent * d) < 1.5:
					d += 7.0
					continue
				cases.append([a + tangent * d + outward * (half_width - 0.005) + Vector3(0, 0.15, 0), outward])
				d += 7.0
	cases.append([Vector3(23.7290554046631, 0.149513557553291, -17.8599338531494), Vector3(-0.7071, 0, -0.7071)])
	var failed: Array[String] = []
	var total := 0
	var player := _player(main)
	var camera := _camera(main)
	for c in cases:
		for angle_deg in [-45.0, 0.0, 45.0]:
			player.global_position = c[0]
			player.velocity = Vector3.ZERO
			await _frames(3)
			var dir: Vector3 = c[1].rotated(Vector3.UP, deg_to_rad(angle_deg))
			camera.yaw = atan2(-dir.x, -dir.z)
			camera.apply_look(Vector2.ZERO)
			Input.action_press("move_forward")
			await _frames(90)
			Input.action_release("move_forward")
			await _frames(5)
			total += 1
			var pos := player.global_position
			if pos.y > 0.05 or _horizontal(pos - c[0]).length() < 1.5:
				failed.append("%s %d° y=%.2f" % [c[0].snapped(Vector3.ONE * 0.1), angle_deg, pos.y])
	_check(failed.is_empty(), "player steps down from the kerb edge in %d/%d cases %s" % [total - failed.size(), total, failed.slice(0, 5)])
	await _free(main)


func _test_buildings_block_the_player() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var footprints: Array = []
	for b in world.metadata["buildings"]:
		var poly := PackedVector2Array()
		for p in b["footprint"][0]:
			poly.append(Vector2(p[0], -p[1]))
		footprints.append(poly)
	var inside := 0
	var tried := 0
	for b in world.metadata["buildings"]:
		if b["block"] != "block_s" or b["footprint_area_m2"] < 150.0:
			continue
		var target := _ring_center(b["footprint"][0])
		var path: Array = world.metadata["blocks"]["block_s"]["sidewalk_path"]
		var nearest := GeoReference.local_to_godot(path[0])
		for p in path:
			var v := GeoReference.local_to_godot(p)
			if v.distance_to(target) < nearest.distance_to(target):
				nearest = v
		await _walk_path(main, nearest + Vector3(0, 0.3, 0), [target], -1.0, 180)
		var pos := _player(main).global_position
		tried += 1
		for poly in footprints:
			if Geometry2D.is_point_in_polygon(Vector2(pos.x, pos.z), poly):
				inside += 1
				break
		if tried == 5:
			break
	_check(tried == 5 and inside == 0, "player cannot enter buildings (%d/%d ended inside)" % [inside, tried])
	await _free(main)


func _test_tree_trunk_blocks_the_player() -> void:
	var main := await _spawn_main(REAL_MAIN_SCENE)
	var world: ResistanceWorld = main.get_node("World")
	var tree: Dictionary = {}
	for entry in world.metadata["props"]:
		if entry["type"] == "tree" and entry["surface"] == "terrain":
			tree = entry
			break
	var trunk := GeoReference.local_to_godot(tree["position"], float(tree["base_y"]))
	var player := _player(main)
	var camera := _camera(main)
	player.global_position = trunk + Vector3(5, 0.3, 0)
	await _frames(10)
	camera.yaw = atan2(1.0, 0.0)  # face -X, straight through the trunk
	camera.apply_look(Vector2.ZERO)
	var closest := 100.0
	Input.action_press("move_forward")
	for i in 240:
		await physics_frame
		closest = minf(closest, _horizontal(player.global_position - trunk).length())
	Input.action_release("move_forward")
	var trunk_radius := 0.22 * float(tree["height_m"]) / 8.0
	_check(closest > trunk_radius + 0.3, "tree trunk blocks the player (closest %.2f m)" % closest)
	await _free(main)


# --- Phase 5: persistence ----------------------------------------------

func _test_position_survives_restart() -> void:
	DirAccess.remove_absolute(TEST_SAVE)
	var hashes_before := _protected_hashes()
	var main := await _spawn_main(REAL_MAIN_SCENE, TEST_SAVE)
	var world: ResistanceWorld = main.get_node("World")
	var target := GeoReference.local_to_godot(world.metadata["blocks"]["block_n"]["sidewalk_path"][1])
	await _walk_path(main, target + Vector3(0, 0.3, 0), [target + Vector3(3, 0, 0)])
	await _frames(20)
	var saved_position := _player(main).global_position
	_camera(main).yaw = 1.0
	_check(main.save_player() == OK, "save_player writes the save file")
	await _free(main)

	main = await _spawn_main(REAL_MAIN_SCENE, TEST_SAVE)
	var restored := _player(main).global_position
	_check(restored.distance_to(saved_position) < 0.05,
		"position restored after restart (%.3f m error)" % restored.distance_to(saved_position))
	_check(is_equal_approx(_camera(main).yaw, 1.0), "camera yaw restored")
	await _frames(30)
	_check(_player(main).is_on_floor(), "restored player stands on the floor")
	await _free(main)
	_check(_protected_hashes() == hashes_before, "sources and generated resources unchanged by saving")
	_check(_protected_hashes()["res://data/source/osm/resistencia_2x2.osm.json"] == _provenance_sha(
		"res://data/source/osm/resistencia_2x2.osm.provenance.json"), "raw OSM file still matches its download hash")


func _test_invalid_saves_fall_back_to_spawn() -> void:
	for content in ["not json", JSON.stringify({"version": 1, "scenario": "other_city", "godot_position": [50, 0, 50]})]:
		var file := FileAccess.open(TEST_SAVE, FileAccess.WRITE)
		file.store_string(content)
		file.close()
		var main := await _spawn_main(REAL_MAIN_SCENE, TEST_SAVE)
		var spawn: Vector3 = main.spawn_transform.origin
		_check(_horizontal(_player(main).global_position - spawn).length() < 0.05,
			"invalid or foreign save is ignored (%s)" % content.left(20))
		await _free(main)


func _test_save_uses_projected_coordinates() -> void:
	var metadata := ResistanceWorld.load_metadata(METADATA)
	var geo := GeoReference.from_metadata(metadata)
	PlayerSave.write(TEST_SAVE, "resistencia_2x2", Vector3(10, 0.15, -20), 0.0, 0.0, geo)
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(TEST_SAVE))
	_check(is_equal_approx(data["position"]["easting"], geo.origin_easting + 10.0)
		and is_equal_approx(data["position"]["northing"], geo.origin_northing + 20.0), "save stores EPSG:32721 coordinates")
	var moved := GeoReference.from_metadata(metadata)
	moved.origin_easting += 100.0
	var loaded := PlayerSave.read(TEST_SAVE, "resistencia_2x2", moved)
	_check(loaded["position"].is_equal_approx(Vector3(-90, 0.15, -20)), "save survives a change of local origin")


func _protected_hashes() -> Dictionary:
	var hashes := {}
	for path in ["res://data/source/osm/resistencia_2x2.osm.json", "res://data/source/overture/resistencia_2x2.buildings.geojson",
			"res://generated/resistencia/scenario.json", "res://generated/resistencia/buildings.glb"]:
		hashes[path] = FileAccess.get_sha256(path)
	return hashes


func _provenance_sha(path: String) -> String:
	return JSON.parse_string(FileAccess.get_file_as_string(path))["sha256"]


# --- helpers -----------------------------------------------------------

func _spawn_main(scene := TEST_MAIN_SCENE, save_path := "") -> Node:
	var main: Node = load(scene).instantiate()
	main.save_path = save_path  # tests never touch the real player save
	root.add_child(main)
	await _frames(30) # let the player settle on the floor
	return main


func _spawn_world(overrides_path := "user://__no_overrides__.json") -> ResistanceWorld:
	var world := load(REAL_WORLD_SCENE).instantiate() as ResistanceWorld
	(world.get_node("Buildings") as BuildingManager).overrides_path = overrides_path
	root.add_child(world)
	await _frames(2)
	return world


## Teleports the player to start and runs through the points, steering the
## camera yaw towards each one. Returns false if a point is not reached.
## When floor_y >= 0, also fails if the player leaves that height while on the floor.
func _walk_path(main: Node, start: Vector3, points: Array, floor_y := -1.0, max_frames := 1500, running := true) -> bool:
	var player := _player(main)
	var camera := _camera(main)
	player.global_position = start
	player.velocity = Vector3.ZERO
	await _frames(5)
	Input.action_press("move_forward")
	if running:
		Input.action_press("run")
	var ok := true
	for target in points:
		var frames := 0
		while _horizontal(target - player.global_position).length() > 1.0:
			var d := _horizontal(target - player.global_position)
			camera.yaw = atan2(-d.x, -d.z)
			camera.apply_look(Vector2.ZERO)
			await physics_frame
			frames += 1
			if floor_y >= 0.0 and player.is_on_floor() and absf(player.global_position.y - floor_y) > 0.05:
				ok = false
			if frames > max_frames:
				ok = false
				break
		if not ok:
			break
	Input.action_release("move_forward")
	Input.action_release("run")
	return ok


## Horizontal distance from a point to the nearest prop (tree, lamp).
func _distance_to_props(world: ResistanceWorld, point: Vector3) -> float:
	var best := INF
	for entry in world.metadata.get("props", []):
		best = minf(best, _horizontal(GeoReference.local_to_godot(entry["position"]) - point).length())
	return best


## Moves a test point along the sidewalk until no prop is within `clearance` metres.
func _clear_of_props(world: ResistanceWorld, point: Vector3, tangent: Vector3, clearance: float) -> Vector3:
	var p := point
	for i in 20:
		if _distance_to_props(world, p) >= clearance:
			return p
		p += tangent * 1.0
	return p


func _ring_center(ring: Array) -> Vector3:
	var sum := Vector2.ZERO
	for i in ring.size() - 1:
		sum += Vector2(ring[i][0], ring[i][1])
	var c := sum / (ring.size() - 1)
	return GeoReference.local_to_godot([c.x, c.y])


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
