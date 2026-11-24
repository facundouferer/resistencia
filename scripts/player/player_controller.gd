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
	move_and_slide()

	if direction.length_squared() > 0.0001:
		# Model front is -Z: yaw that rotates -Z onto the movement direction.
		var target_yaw := atan2(-direction.x, -direction.z)
		_visual.rotation.y = lerp_angle(_visual.rotation.y, target_yaw, clampf(turn_speed * delta, 0.0, 1.0))
