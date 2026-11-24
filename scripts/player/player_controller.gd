class_name PlayerController
extends CharacterBody3D
## Third-person character. Movement is relative to the camera yaw:
## "forward" is where the camera looks, projected on the ground plane.
## The body never rotates; only the Visual node turns to face the
## movement direction, so the camera yaw stays independent.

@export var walk_speed := 2.0 ## m/s
@export var run_speed := 6.0 ## m/s
@export var acceleration := 20.0 ## m/s²
@export var turn_speed := 10.0
## Highest obstacle (m) climbed automatically, e.g. a curb. Walls are taller.
@export var max_step_height := 0.3
@export var camera_path: NodePath = ^"CameraPivot"
@export var visual_path: NodePath = ^"Visual"

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")

@onready var _camera: CameraController = get_node(camera_path)
@onready var _visual: Node3D = get_node(visual_path)


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta

	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := _camera.get_planar_basis() * Vector3(input.x, 0.0, input.y)
	var speed := run_speed if Input.is_action_pressed("run") else walk_speed

	var horizontal := Vector3(velocity.x, 0.0, velocity.z)
	horizontal = horizontal.move_toward(direction * speed, acceleration * delta)
	velocity.x = horizontal.x
	velocity.z = horizontal.z
	var stepped := _try_step_up(delta)
	move_and_slide()
	if stepped:
		# Land on top of the step instead of floating for a few frames.
		move_and_collide(Vector3.DOWN * max_step_height)
		velocity.y = 0.0

	if direction.length_squared() > 0.0001:
		# Model front is -Z: yaw that rotates -Z onto the movement direction.
		var target_yaw := atan2(-direction.x, -direction.z)
		_visual.rotation.y = lerp_angle(_visual.rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))


## Raises the body when a low obstacle (curb) blocks horizontal movement and
## there is free space above it. Returns true when the body was raised.
func _try_step_up(delta: float) -> bool:
	var motion := Vector3(velocity.x, 0.0, velocity.z) * delta
	if motion.length_squared() < 1e-8 or not is_on_floor():
		return false
	var hit := KinematicCollision3D.new()
	if not test_move(global_transform, motion, hit) or hit.get_normal().y >= cos(floor_max_angle):
		return false  # free, or touching walkable floor
	var up := Vector3.UP * max_step_height
	if test_move(global_transform, up):
		return false  # ceiling
	if test_move(global_transform.translated(up), motion):
		return false  # still blocked: a wall, not a step
	global_position += up
	return true
