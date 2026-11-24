# Controls

| Action | Input | Input action |
| --- | --- | --- |
| Move forward | W | `move_forward` |
| Move back | S | `move_back` |
| Move left | A | `move_left` |
| Move right | D | `move_right` |
| Run (hold) | Shift | `run` |
| Capture mouse | Left click | `mouse_capture` |
| Release mouse | Escape | `mouse_release` |
| Look around | Mouse (while captured) | — |

Keys are bound by physical position, so WASD works on any keyboard layout.

## Movement model

- Movement is relative to the **camera yaw**: W moves where the camera looks, projected on the ground.
- The character body does not rotate; its visual model turns to face the movement direction.
- Walk speed: 2 m/s. Run speed: 6 m/s. Both are exported on `PlayerController` (1 Godot unit = 1 m).

## Camera

- Third-person orbit camera with `SpringArm3D`, so it moves closer instead of going through walls.
- Vertical angle limited to -70° (looking down) / +30° (looking up). Distance: 4 m (`CameraController.distance`).
