class_name CameraController
extends Node3D
## Third-person orbit camera. Yaw and pitch are applied to this pivot;
## a SpringArm3D child keeps the camera from going through walls.
## Left click captures the mouse, Escape releases it.

@export var mouse_sensitivity := 0.003 ## radians per pixel
@export var min_pitch_deg := -70.0
@export var max_pitch_deg := 30.0
@export var initial_pitch_deg := -15.0
@export var distance := 4.0: ## metres
	set(value):
		distance = value
		if is_node_ready():
			_spring_arm.spring_length = value
@export var spring_arm_path: NodePath = ^"SpringArm3D"

var yaw := 0.0
var pitch := 0.0

@onready var _spring_arm: SpringArm3D = get_node(spring_arm_path)


func _ready() -> void:
	pitch = deg_to_rad(initial_pitch_deg)
	_spring_arm.spring_length = distance
	var body := get_parent() as CollisionObject3D
	if body:
		_spring_arm.add_excluded_object(body.get_rid())
	_apply_rotation()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("mouse_release"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	elif event.is_action_pressed("mouse_capture"):
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		apply_look(event.relative * mouse_sensitivity)


## Rotates the camera. x > 0 turns right, y > 0 looks down (radians).
func apply_look(delta: Vector2) -> void:
	yaw = wrapf(yaw - delta.x, -PI, PI)
	pitch = clampf(pitch - delta.y, deg_to_rad(min_pitch_deg), deg_to_rad(max_pitch_deg))
	_apply_rotation()


## Basis containing only the yaw, used for camera-relative movement.
func get_planar_basis() -> Basis:
	return Basis(Vector3.UP, yaw)


func _apply_rotation() -> void:
	rotation = Vector3(pitch, yaw, 0.0)
