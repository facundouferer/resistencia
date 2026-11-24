"""Generate the 3D scenario (GLB + metadata) from the geographic sources.

Pipeline: raw OSM (+ optional Overture buildings) -> analyze_area -> local
coordinates -> roadway / sidewalk / lot / building geometry -> GLB files and
scenario metadata that Godot loads.

Axes: geographic local (X = E - E0, Y = N - N0, Z = up) is written in Godot
axes (x = X, y = Z, z = -Y). 1 unit = 1 metre.

Usage:
    python tools/geometry_generator/generate_scene.py GEN_CONFIG AREA_CONFIG OSM_JSON OUTPUT_DIR \
        [--extra-buildings OVERTURE_GEOJSON]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np
import shapely
import trimesh
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geo_processor"))
import analyze_area as aa  # noqa: E402

GENERATOR_VERSION = "0.1.0"
# Geographic local (X east, Y north, Z up) -> Godot (x east, y up, z south).
TO_GODOT = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)
MITRE = shapely.BufferJoinStyle.mitre
FLAT = shapely.BufferCapStyle.flat


def to_local(geometry, origin: tuple[float, float]):
    return shapely.transform(geometry, lambda c: c - np.array(origin))


def polygons(geometry) -> list[Polygon]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Polygon):
        return [geometry]
    return [g for g in getattr(geometry, "geoms", []) if isinstance(g, Polygon) and not g.is_empty]


def measure_sidewalk_offset(osm: aa.OsmData, streets: dict, area: Polygon) -> tuple[float, int]:
    """Median distance (m) from OSM sidewalk ways to the nearest street centerline.

    Samples near intersections (two streets within 8 m of each other) are skipped.
    """
    samples = []
    for way in osm.ways.values():
        if way.get("tags", {}).get("footway") != "sidewalk":
            continue
        line = aa.way_line(osm, way)
        for i in range(0, 101, 5):
            point = line.interpolate(i / 100, normalized=True)
            if not area.contains(point):
                continue
            distances = sorted(lines.distance(point) for lines in streets.values())
            if distances[1] - distances[0] > 8.0:
                samples.append(distances[0])
    if len(samples) < 10:
        raise ValueError(f"not enough sidewalk samples to measure street layout ({len(samples)})")
    return statistics.median(samples), len(samples)


def slab(geometry, bottom: float, top: float, name: str) -> trimesh.Trimesh | None:
    parts = []
    for poly in polygons(geometry):
        mesh = trimesh.creation.extrude_polygon(poly, top - bottom)
        mesh.apply_translation([0, 0, bottom])
        parts.append(mesh)
    if not parts:
        return None
    mesh = trimesh.util.concatenate(parts)
    mesh.apply_transform(TO_GODOT)
    mesh.metadata["name"] = name
    return mesh


def material(rgb: list[int]) -> trimesh.visual.material.PBRMaterial:
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[*rgb, 255], metallicFactor=0.0, roughnessFactor=0.9
    )


def export(meshes: list[tuple[str, trimesh.Trimesh, list[int]]], path: Path) -> None:
    scene = trimesh.Scene()
    for name, mesh, rgb in meshes:
        mesh.visual = trimesh.visual.TextureVisuals(material=material(rgb))
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    path.write_bytes(scene.export(file_type="glb"))


def ring_coords(geometry) -> list[list[list[float]]]:
    """Exterior rings of a (multi)polygon in local metres, 3 decimals."""
    return [[[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords] for poly in polygons(geometry)]


def street_segments(streets_local: dict, intersections: list[Point]) -> list[dict]:
    """Centerline pieces between consecutive intersections, for traversal checks."""
    segments = []
    for name, lines in streets_local.items():
        merged = shapely.line_merge(lines)
        for line in getattr(merged, "geoms", [merged]):
            stops = sorted(line.project(p) for p in intersections if line.distance(p) < 0.5)
            for start, end in zip(stops, stops[1:]):
                a, b = line.interpolate(start), line.interpolate(end)
                segments.append({"street": name, "from": [round(a.x, 3), round(a.y, 3)],
                                 "to": [round(b.x, 3), round(b.y, 3)], "length_m": round(end - start, 2)})
    return segments


def generate(gen: dict, area_config: dict, osm: aa.OsmData, extra, extra_source, out: Path) -> dict:
    report, _, _, buildings, boundary, extra_geo = aa.analyze(area_config, osm, extra, extra_source)
    origin = (report["local_origin"]["easting"], report["local_origin"]["northing"])
    blocks = extra_geo["blocks"]
    streets = extra_geo["streets"]

    sidewalk_offset, samples = measure_sidewalk_offset(osm, streets, boundary.buffer(5))
    half_sidewalk = gen["sidewalk_width_m"] / 2
    kerb_offset = sidewalk_offset - half_sidewalk
    property_offset = sidewalk_offset + half_sidewalk
    curb = gen["curb_height_m"]

    boundary_l = to_local(boundary, origin)
    extent = boundary_l.buffer(gen["extent_margin_m"], join_style=MITRE)
    streets_l = {name: to_local(lines, origin) for name, lines in streets.items()}
    platforms, lots, sidewalks = {}, {}, {}
    for name, cell in blocks.items():
        cell_l = to_local(cell, origin)
        platforms[name] = cell_l.buffer(-kerb_offset, join_style=MITRE)
        lots[name] = cell_l.buffer(-property_offset, join_style=MITRE)
        sidewalks[name] = platforms[name].difference(lots[name])
    all_platforms = unary_union(list(platforms.values()))
    roadway = (unary_union([lines.buffer(kerb_offset, cap_style=FLAT, join_style=MITRE) for lines in streets_l.values()])
               .intersection(extent).difference(all_platforms))

    warnings = list(report["warnings"])
    building_meta, building_meshes = [], []
    for b in sorted((b for b in buildings if b.block), key=lambda b: b.id):
        footprint = to_local(b.footprint, origin)
        clipped = footprint.intersection(lots[b.block])
        if clipped.area < gen["min_building_area_m2"]:
            warnings.append(f"{b.id}: dropped, {clipped.area:.1f} m² left inside its lot")
            continue
        if b.height_m is not None:
            height, estimated, rule = b.height_m, False, "source height"
        elif b.levels is not None:
            height, estimated, rule = b.levels * gen["level_height_m"], True, "source levels x level_height_m"
        else:
            height = gen["default_levels"] * gen["level_height_m"]
            estimated, rule = True, "default_levels x level_height_m"
        mesh = slab(clipped, 0.0, curb + height, b.id)
        rgb = gen["colors"]["building_surveyed" if b.source == "openstreetmap" else "building_machine_learned"]
        building_meshes.append((b.id, mesh, rgb))
        building_meta.append({
            "id": b.id,
            "source": b.source,
            "source_id": b.source_id,
            "source_dataset": b.source_dataset,
            "confidence": b.confidence,
            "block": b.block,
            "footprint": ring_coords(clipped),
            "footprint_area_m2": round(clipped.area, 2),
            "clipped_to_lot": round(1 - clipped.area / footprint.area, 3) if footprint.area else 0.0,
            "base_y": curb,
            "height_m": round(height, 2),
            "levels": b.levels,
            "height_is_estimated": estimated,
            "height_rule": rule,
            "building_type": b.tags.get("building", "unknown") if b.source == "openstreetmap" else "unknown",
            "model": "generic_building",
        })

    out.mkdir(parents=True, exist_ok=True)
    colors = gen["colors"]
    export([("Terrain", slab(extent, -0.3, -0.02, "Terrain"), colors["terrain"])], out / "terrain.glb")
    export([("Roadway", slab(roadway, -0.3, 0.0, "Roadway"), colors["roadway"])], out / "streets.glb")
    sidewalk_meshes = []
    for name in blocks:
        sidewalk_meshes.append((f"Sidewalk_{name}", slab(sidewalks[name], -0.3, curb, f"Sidewalk_{name}"), colors["sidewalk"]))
        sidewalk_meshes.append((f"Lot_{name}", slab(lots[name], -0.3, curb - 0.01, f"Lot_{name}"), colors["lot"]))
    export(sidewalk_meshes, out / "sidewalks.glb")
    export(building_meshes, out / "buildings.glb")

    intersections = []
    names = list(streets_l)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            x = streets_l[a].intersection(streets_l[b])
            intersections += [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]

    # Spawn: on the sidewalk centerline of block_s, 20 m from its corner
    # nearest to the local origin (Pueyrredón x Santa Fe).
    sidewalk_paths = {name: platforms[name].buffer(-half_sidewalk, join_style=MITRE).exterior for name in blocks}
    ring = sidewalk_paths["block_s"]
    spawn_center = ring.interpolate((ring.project(Point(0, 0)) + 20.0) % ring.length)

    resources = {}
    for file in ("terrain.glb", "streets.glb", "sidewalks.glb", "buildings.glb"):
        resources[file] = hashlib.sha256((out / file).read_bytes()).hexdigest()

    lon_min, lat_min = aa._to_geo.transform(*boundary.bounds[:2])
    lon_max, lat_max = aa._to_geo.transform(*boundary.bounds[2:])
    metadata = {
        "name": gen["scenario"],
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": f"tools/geometry_generator/generate_scene.py {GENERATOR_VERSION}",
        "sources": [report["source"]] + ([report["secondary_source"]] if report["secondary_source"] else []),
        "license": "Open Database License (ODbL) 1.0",
        "attribution": "© OpenStreetMap contributors"
                       + ("; Overture Maps Foundation (Google Open Buildings, Microsoft ML Buildings)" if extra_source else ""),
        "projection": report["projection"],
        "units": "metres",
        "origin": report["local_origin"],
        "axes": "godot.x = easting - origin.easting; godot.y = height; godot.z = -(northing - origin.northing)",
        "bounds": {
            "wgs84": {"lat_min": round(lat_min, 7), "lon_min": round(lon_min, 7),
                      "lat_max": round(lat_max, 7), "lon_max": round(lon_max, 7)},
            "utm": report["boundary_bounds_utm"],
        },
        "estimation_rules": {
            "sidewalk_centerline_offset_m": round(sidewalk_offset, 2),
            "sidewalk_centerline_offset_source": f"{gen['sidewalk_offset_source']} ({samples} samples)",
            "sidewalk_width_m": gen["sidewalk_width_m"],
            "sidewalk_width_is_estimated": gen["sidewalk_width_is_estimated"],
            "kerb_offset_from_centerline_m": round(kerb_offset, 2),
            "curb_height_m": curb,
            "level_height_m": gen["level_height_m"],
            "default_levels": gen["default_levels"],
            "terrain": "flat at y = 0 (no elevation data used)",
        },
        "resources": resources,
        "spawn": {"x": round(spawn_center.x, 3), "y": curb + 0.05, "z": round(-spawn_center.y, 3)},
        "blocks": {
            name: {"cell": ring_coords(to_local(blocks[name], origin)), "platform": ring_coords(platforms[name]),
                   "lot": ring_coords(lots[name]), "sidewalk_area_m2": round(sidewalks[name].area, 1),
                   "sidewalk_path": [[round(x, 3), round(y, 3)] for x, y in shapely.simplify(sidewalk_paths[name], 0.5).coords]}
            for name in blocks
        },
        "street_segments": street_segments(streets_l, intersections),
        "buildings": building_meta,
        "warnings": warnings,
    }
    (out / "scenario.json").write_text(json.dumps(metadata, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"metadata": metadata, "roadway": roadway, "platforms": platforms, "sidewalks": sidewalks,
            "lots": lots, "extent": extent}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gen_config", type=Path)
    parser.add_argument("area_config", type=Path)
    parser.add_argument("osm_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--extra-buildings", type=Path)
    args = parser.parse_args()

    gen = json.loads(args.gen_config.read_text(encoding="utf-8"))
    area_config = json.loads(args.area_config.read_text(encoding="utf-8"))
    osm = aa.load_osm(args.osm_json)
    extra, extra_source = None, None
    if args.extra_buildings:
        extra = aa.load_overture_buildings(args.extra_buildings)
        prov = args.extra_buildings.with_name(args.extra_buildings.name.removesuffix(".geojson") + ".provenance.json")
        data = json.loads(prov.read_text(encoding="utf-8")) if prov.exists() else {"file": args.extra_buildings.name}
        extra_source = {k: data.get(k) for k in ("source", "release", "licenses", "attribution", "sha256", "file")}
    result = generate(gen, area_config, osm, extra, extra_source, args.output_dir)
    meta = result["metadata"]
    estimated = sum(1 for b in meta["buildings"] if b["height_is_estimated"])
    print(f"buildings: {len(meta['buildings'])} ({estimated} estimated heights); "
          f"street segments: {len(meta['street_segments'])}; spawn: {meta['spawn']}; "
          f"sidewalk offset: {meta['estimation_rules']['sidewalk_centerline_offset_m']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
