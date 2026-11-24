# Resistencia 3D

Free-roam 3D prototype of four blocks of Resistencia, Chaco, Argentina, built with Godot 4 from open geographic data.

## Run

```bash
/Applications/Godot.app/Contents/MacOS/Godot --path .
```

Controls: see `docs/controls.md` (WASD, Shift to run, click to capture the mouse, Escape to release it).

## Test

```bash
/Applications/Godot.app/Contents/MacOS/Godot --headless --fixed-fps 60 --path . -s tests/run_tests.gd
tools/.venv/bin/python -m unittest discover -s tests/tools
```

## Regenerate the city

```bash
/opt/homebrew/bin/python3.13 -m venv tools/.venv && tools/.venv/bin/pip install -r tools/requirements.txt
```

Then follow `docs/geographic-data.md`.

## Documentation

`docs/architecture.md`, `docs/decisions.md`, `docs/geographic-data.md`, `docs/persistence.md`, `docs/controls.md`, `docs/progress.md`.

## Data attribution

Map data © OpenStreetMap contributors, available under the Open Database License (ODbL) 1.0.
Additional building footprints from Overture Maps Foundation (Google Open Buildings, Microsoft ML Building Footprints), ODbL 1.0.
Street-level reference photos from Mapillary contributor federicopertile, CC BY-SA 4.0.
Material textures from Poly Haven (CC0).
