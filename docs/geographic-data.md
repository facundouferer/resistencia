# Geographic data

## Sources

### Primary: OpenStreetMap

| Item | Value |
| --- | --- |
| Source | OpenStreetMap via Overpass API (`overpass-api.de`) |
| License | Open Database License (ODbL) 1.0 — attribution: "© OpenStreetMap contributors" |
| Raw file (never modified) | `data/source/osm/resistencia_2x2.osm.json` |
| Provenance (query, date, SHA-256) | `data/source/osm/resistencia_2x2.osm.provenance.json` |
| Query | `tools/osm_importer/queries/resistencia_2x2.overpassql` |
| Download | 2026-11-24 00:48 UTC, OSM base 2026-11-24T00:47:18Z |

Re-download (refuses to overwrite existing raw data):

```bash
tools/.venv/bin/python -I tools/osm_importer/fetch_osm.py \
  tools/osm_importer/queries/resistencia_2x2.overpassql data/source/osm/<new-file>.osm.json
```

### Secondary: Overture Maps buildings (only where OSM has no footprint)

| Item | Value |
| --- | --- |
| Source | Overture Maps Foundation, theme `buildings`, type `building`, release **2026-11-18.0** |
| Datasets used | Google Open Buildings, Microsoft ML Buildings (machine-learned footprints). Overture features derived from OSM are ignored: OSM is read from the raw OSM file. |
| License | ODbL 1.0 (per feature `sources[].license`) |
| Raw file (never modified) | `data/source/overture/resistencia_2x2.buildings.geojson` |
| Provenance | `data/source/overture/resistencia_2x2.buildings.provenance.json` |
| Client | `overturemaps` 2.1.1 (official CLI) |

Re-download:

```bash
tools/.venv/bin/python -I tools/overture_importer/fetch_overture.py \
  --bbox=-58.9890,-27.4503,-58.9840,-27.4458 2026-11-18.0 data/source/overture/<new-file>.geojson
```

Merge rule: OSM buildings always win. An Overture footprint overlapping OSM buildings by more than 20 % of its own area is dropped as a duplicate. Each building keeps `source` (`openstreetmap` / `overture_maps`), `source_id` (OSM `way/<id>` or Overture GERS id), `source_dataset` and, for machine-learned footprints, `confidence` (min 0.65 in this area).

## Study area

Identified from OSM street geometry, not assumed:

- Boundary streets: Remedios de Escalada, Marcelo Torcuato de Alvear (OSM name of "Av. Marcelo T. de Alvear"), Bartolomé Mitre, Corrientes.
- Inner streets splitting the 2 × 2 grid: Pueyrredón and Santa Fe.
- The grid is rotated about 45° from north; blocks are named by direction from the center: `block_n`, `block_e`, `block_s`, `block_w`.
- Note: OSM also has "Avenida Carlos María de Alvear", a different street; it is not used.

| Corner | Easting | Northing | Lat | Lon |
| --- | --- | --- | --- | --- |
| Escalada × Alvear | 303502.41 | 6962369.43 | -27.4480153 | -58.9882289 |
| Alvear × Mitre | 303674.88 | 6962201.94 | -27.4495514 | -58.9865117 |
| Mitre × Corrientes | 303842.32 | 6962375.44 | -27.4480101 | -58.9847903 |
| Corrientes × Escalada | 303667.47 | 6962542.27 | -27.4464797 | -58.9865317 |

Measurements (between street centerlines): outer sides 239.0–241.7 m; each block cell 118.9–121.6 m per side, 14,365–14,602 m². Real block size (kerb or property line) is smaller by half a street width plus the sidewalk; OSM has no street `width` tags here, so that must be estimated in Phase 3.

## Coordinates

- Work projection: WGS 84 / UTM zone 21S, **EPSG:32721**, metres.
- Local origin: intersection of Pueyrredón and Santa Fe centerlines, rounded to 1 m: **E 303672, N 6962373** (lat -27.4480076, lon -58.9865132).
- Godot axes (1 unit = 1 m): `x = E - 303672`, `y = height`, `z = -(N - 6962373)`. North is -Z, east is +X.
- Round-trip WGS 84 ↔ UTM error is below 1 mm (tested).

## Processing

```bash
tools/.venv/bin/python -I tools/geo_processor/analyze_area.py \
  tools/geo_processor/areas/resistencia_2x2.json \
  data/source/osm/resistencia_2x2.osm.json data/processed/resistencia_2x2 \
  --extra-buildings data/source/overture/resistencia_2x2.buildings.geojson
```

Outputs in `data/processed/resistencia_2x2/`:

- `area.geojson`: boundary, blocks, street centerlines, corners, origin and buildings (WGS 84). Opens in QGIS or geojson.io.
- `area_report.json`: measurements, origin, per-block statistics, warnings.
- `preview.svg`: quick visual check.

## Known data gaps (2026-11-24)

- **Buildings in OSM**: only `block_s` has footprints (39 buildings, ~53 % coverage). `block_n`, `block_e` and `block_w` have none in OSM, only address interpolation lines (missing mapping, not a download issue).
- **Buildings from Overture** fill those three blocks: 133 machine-learned footprints, 27–31 % coverage per block. They are detached, approximate shapes. The OSM-mapped `block_s` shows continuous building rows at 53 % coverage, so the ML blocks probably underestimate the built area (not verified on the ground). Refining them in OSM remains a future improvement.

| Block | Buildings | Datasets | Coverage |
| --- | --- | --- | --- |
| block_n | 45 | Google 27, Microsoft 18 | 29.7 % |
| block_e | 43 | Google 33, Microsoft 10 | 30.6 % |
| block_s | 39 | OpenStreetMap 39 | 52.9 % |
| block_w | 45 | Google 26, Microsoft 19 | 26.9 % |

- **Heights**: none of the 172 buildings has height or levels in any source. All heights will be estimated and flagged as such.
- **Street widths**: no `width` or `lanes` tags on the six streets (all `oneway=yes`).
- 7 `building:part` ways exist in the download; not used yet.

## 3D generation (Phase 3)

```bash
tools/.venv/bin/python -I tools/geometry_generator/generate_scene.py \
  tools/geometry_generator/config/resistencia_2x2.json \
  tools/geo_processor/areas/resistencia_2x2.json \
  data/source/osm/resistencia_2x2.osm.json generated/resistencia \
  --extra-buildings data/source/overture/resistencia_2x2.buildings.geojson
```

Outputs in `generated/resistencia/` (Godot imports them; never edit by hand, regenerate instead):

| File | Content |
| --- | --- |
| `terrain.glb` | Flat ground over the area + 40 m margin, top at y = -0.02 |
| `streets.glb` | Roadway: street centerlines buffered to the kerb, top at y = 0 |
| `sidewalks.glb` | Per block: `Sidewalk_<block>` ring and `Lot_<block>` interior, top at the curb height |
| `buildings.glb` | One mesh per building, node name = persistent building id |
| `scenario.json` | Metadata: sources, license, projection, origin, bounds, estimation rules, resource hashes, spawn, blocks, street segments, buildings, warnings |

Street layout rule (`tools/geometry_generator/config/resistencia_2x2.json`):

- Sidewalk centerline offset from the street centerline: **6.1 m, measured** (median of 50 samples from OSM `footway=sidewalk` ways).
- Sidewalk width: **3.0 m, estimated** → kerb at 4.6 m (roadway ≈ 9.2 m), property line at 7.6 m from the centerline.
- Curb height: 0.15 m (estimated). Terrain: flat (no elevation data used).
- Corners are square (mitre); real chamfered corners ("ochavas") are not in the data.

Facades (`procedural_facade_v1`): a 0.25 m cornice ledge in the geometry plus `assets/materials/facade.gdshader` drawing windows per 3 m level and 3.2 m bay, a shopfront ground floor and a darker cornice band. Facade colour is picked from `facade_palette` by a hash of the building id (deterministic) and stored as `appearance.facade_color` with `is_estimated: true`. **This is a stylized look, not the real appearance of each building.**

Building height rule: source `height` if present, else `building:levels × 3.0 m`, else **2 levels × 3.0 m = 6 m**. Today all 172 heights are estimated (`height_is_estimated: true`, `height_rule` says which rule). Building footprints are clipped to their lot; none needed dropping.

## Trees and street lamps

From OSM nodes `natural=tree` and `highway=street_lamp` inside the scenario extent (area + 40 m). Palms are trees whose `genus` is in `props.palm_genera` (config). No height tags exist: heights are estimated (tree 8 m, palm 6 m, lamp 6 m). Lamp arm direction is derived (towards the nearest street centerline). None are mapped inside the four blocks.
