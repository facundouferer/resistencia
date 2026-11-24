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


def facade_color(building_id: str, palette: list[str]) -> str:
    """Deterministic palette pick: the same building always gets the same colour."""
    return palette[int(hashlib.sha256(building_id.encode()).hexdigest(), 16) % len(palette)]


def extract_props(osm: aa.OsmData, origin, extent, roadway, platforms, streets_l: dict,
                  rules: dict, curb: float) -> tuple[list[dict], list[str]]:
    """OSM trees and street lamps inside the scenario extent, in local metres."""
    props, warnings = [], []
    all_streets = unary_union(list(streets_l.values()))
    for node_id, tags in sorted(osm.node_tags.items()):
        if tags.get("natural") == "tree":
            kind = "palm" if tags.get("genus") in rules["palm_genera"] else "tree"
        elif tags.get("highway") == "street_lamp":
            kind = "street_lamp"
        else:
            continue
        e, n = osm.nodes[node_id]
        point = Point(e - origin[0], n - origin[1])
        if not extent.contains(point):
            continue
        if platforms.contains(point):
            surface, base_y = "sidewalk_or_lot", curb
        elif roadway.contains(point):
            surface, base_y = "roadway", 0.0
            warnings.append(f"osm_node_{node_id}: {kind} lies on the modelled roadway "
                            "(street layout is estimated; the real street may have a median here)")
        else:
            surface, base_y = "terrain", -0.02
        height = rules[f"{kind}_height_m"] if kind != "palm" else rules["palm_height_m"]
        parsed = aa.parse_number(tags.get("height"))
        nearest = shapely.ops.nearest_points(all_streets, point)[0]
        props.append({
            "id": f"osm_node_{node_id}",
            "source": "openstreetmap",
            "source_id": f"node/{node_id}",
            "type": kind,
            "position": [round(point.x, 3), round(point.y, 3)],
            "base_y": base_y,
            "surface": surface,
            "height_m": parsed if parsed is not None else height,
            "height_is_estimated": parsed is None,
            # Lamp arms point to the nearest street centerline (derived, not mapped).
            "facing": [round(nearest.x - point.x, 3), round(nearest.y - point.y, 3)],
            "species": tags.get("species"),
            "genus": tags.get("genus"),
        })
    return props, warnings


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


GROUND_FLOOR_KINDS = ("shopfront", "residential", "garage")
FRONTAGE_REACH_M = 18.0  # sidewalk (3 m) + first 15 m of the lot: buildings in this band face the street
KERB_TREE_INSET_M = 0.7
TREE_CORNER_CLEARANCE_M = 6.0
DEFAULT_TREE_SPACING_M = 9.0


def block_faces(platforms: dict, streets_l: dict) -> dict:
    """Block sides (platform edges) keyed '<block>:<street>', oriented corner to corner.

    Collinear pieces of the same side (a bend in the street) are merged.
    """
    faces = {}
    for block, platform in platforms.items():
        ring = shapely.simplify(platform, 0.5).exterior.coords[:]
        for a, b in zip(ring, ring[1:]):
            mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            street = min(streets_l, key=lambda n: streets_l[n].distance(mid))
            corners = [min((n for n in streets_l if n != street), key=lambda n: streets_l[n].distance(Point(p)))
                       for p in (a, b)]
            key = f"{block}:{street}"
            if key in faces:
                face = faces[key]
                coords = list(face["line"].coords)
                if coords[-1] == a:
                    face["line"], face["to_corner"] = LineString(coords + [b]), f"{street} x {corners[1]}"
                else:
                    face["line"], face["from_corner"] = LineString([a] + coords), f"{street} x {corners[0]}"
            else:
                faces[key] = {"block": block, "street": street, "line": LineString([a, b]),
                              "from_corner": f"{street} x {corners[0]}", "to_corner": f"{street} x {corners[1]}"}
    return faces


def match_frontage(footprint, block: str, faces: dict, reference: dict | None):
    """The observed frontage entry for a building facing a surveyed block side, if any."""
    if not reference:
        return None
    best, best_area = None, 0.0
    for face_id, face in faces.items():
        if face["block"] != block:
            continue
        near = footprint.intersection(face["line"].buffer(FRONTAGE_REACH_M))
        if near.area > best_area:
            best, best_area = (face_id, face, near), near.area
    if best is None:
        return None
    face_id, face, near = best
    observed = reference.get(face_id)
    if not observed or observed.get("visibility") == "none" or not observed.get("buildings"):
        return None
    t = face["line"].project(near.centroid, normalized=True)
    entries = sorted(observed["buildings"], key=lambda e: e.get("order", 0))
    total = sum(float(e.get("frontage_fraction") or 0) for e in entries) or 1.0
    cumulative = 0.0
    for entry in entries:
        cumulative += float(entry.get("frontage_fraction") or 0) / total
        if t <= cumulative + 1e-9:
            return face_id, entry, observed
    return face_id, entries[-1], observed


def ground_floor_kind(features: list[str]) -> str:
    features = [f.lower() for f in features or []]
    if any("shop" in f for f in features):
        return "shopfront"
    if any("garage" in f for f in features):
        return "garage"
    return "residential"


def reference_trees(faces: dict, platforms: dict, reference: dict | None, curb: float) -> list[dict]:
    """Street trees on surveyed sidewalks: evenly spaced along the kerb, count as observed."""
    trees = []
    for face_id, face in sorted(faces.items()):
        observed = (reference or {}).get(face_id) or {}
        info = observed.get("trees") or {}
        if not info.get("present"):
            continue
        line = face["line"]
        usable = line.length - 2 * TREE_CORNER_CLEARANCE_M
        count = info.get("approx_count")
        if not isinstance(count, int) or count < 1:
            count = int(usable // DEFAULT_TREE_SPACING_M) + 1
        for i in range(count):
            d = TREE_CORNER_CLEARANCE_M + (usable * (i + 0.5) / count)
            p = line.interpolate(d)
            q = line.interpolate(min(d + 0.5, line.length))
            r = line.interpolate(max(d - 0.5, 0.0))
            tx, ty = q.x - r.x, q.y - r.y
            n = np.array([-ty, tx]) / max(np.hypot(tx, ty), 1e-9)
            inside = np.array([p.x, p.y]) + n * KERB_TREE_INSET_M
            if not platforms[face["block"]].contains(Point(inside)):
                inside = np.array([p.x, p.y]) - n * KERB_TREE_INSET_M
            trees.append({
                "id": f"ref_tree_{face_id.replace(':', '_').replace(' ', '_')}_{i + 1}",
                "source": "mapillary_reference",
                "source_id": face_id,
                "type": "tree",
                "position": [round(float(inside[0]), 3), round(float(inside[1]), 3)],
                "base_y": curb,
                "surface": "sidewalk_or_lot",
                "height_m": 8.0,
                "height_is_estimated": True,
                "facing": [0.0, 0.0],
                "species": None,
                "genus": None,
                "reference_images": [img.get("pkey") for img in observed.get("images", [])],
            })
    return trees


REPLACED_OVERLAP = 0.2  # Overture footprint dropped when this share lies under a photo frontage
MIN_FRONTAGE_AREA_M2 = 10.0
TILE_ROOF_PITCH_DEG = 25.0
ROOF_EAVE_M = 0.3


def frontage_depth(levels: int, gen: dict) -> float:
    rules = gen["frontage_depth_m"]
    if levels >= 6:
        return rules["tower"]
    if levels >= 3:
        return rules["mid_rise"]
    return rules["house"]


def frontage_volumes(lot_faces: dict, lots: dict, osm_by_block: dict, reference: dict | None,
                     gen: dict, warnings: list) -> list[dict]:
    """Party-wall buildings on the property line, one per observed frontage segment.

    Taller buildings are placed first so they own the corners; OSM footprints
    (surveyed) are never overlapped. Unknown levels or levels 0 create nothing.
    """
    candidates = []
    for face_id, face in sorted(lot_faces.items()):
        observed = (reference or {}).get(face_id) or {}
        entries = sorted(observed.get("buildings") or [], key=lambda e: e.get("order", 0))
        if observed.get("visibility") == "none" or not entries:
            continue
        line = face["line"]
        total = sum(float(e.get("frontage_fraction") or 0) for e in entries) or 1.0
        inward_sign = 1.0
        mid = line.interpolate(0.5, normalized=True)
        (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
        normal = np.array([-(y1 - y0), x1 - x0]) / max(np.hypot(x1 - x0, y1 - y0), 1e-9)
        if not lots[face["block"]].contains(Point(mid.x + normal[0], mid.y + normal[1])):
            inward_sign = -1.0
        start = 0.0
        for entry in entries:
            share = float(entry.get("frontage_fraction") or 0) / total
            end_ = min(start + share, 1.0)
            levels = entry.get("levels")
            if isinstance(levels, int) and levels > 0 and end_ > start:
                segment = shapely.ops.substring(line, start, end_, normalized=True)
                depth = frontage_depth(levels, gen)
                offset = normal * inward_sign * depth
                (ax, ay), (bx, by) = segment.coords[0], segment.coords[-1]
                polygon = Polygon([(ax, ay), (bx, by), (bx + offset[0], by + offset[1]), (ax + offset[0], ay + offset[1])])
                candidates.append({
                    "id": f"ref_{face_id.replace(':', '_').replace(' ', '_')}_{entry.get('order')}",
                    "face_id": face_id, "order": entry.get("order"), "block": face["block"],
                    "levels": levels, "depth": depth, "polygon": polygon.intersection(lots[face["block"]]),
                    "entry": entry, "observed": observed, "front": segment,
                })
            start = end_
    placed, result = [], []
    for c in sorted(candidates, key=lambda c: (-c["levels"], c["id"])):
        poly = c["polygon"].difference(unary_union(osm_by_block[c["block"]] + placed))
        if poly.area < MIN_FRONTAGE_AREA_M2:
            warnings.append(f"{c['id']}: no room left for the photo frontage ({poly.area:.1f} m²)")
            continue
        c["polygon"] = poly
        placed.append(poly)
        result.append(c)
    return result


def feature_flags(features: list[str] | None) -> dict:
    text = " ".join(features or []).lower()
    return {
        "pitched_roof": "pitched" in text,
        "balconies": "balcon" in text,
        "brick_base": "brick" in text and ("base" in text or "band" in text),
    }


def default_appearance(building_id: str, gen: dict) -> dict:
    return {
        "style": gen["facade_style"],
        "facade_color": facade_color(building_id, gen["facade_palette"]),
        "ground_floor": "shopfront",
        "roof": "flat",
        "balconies": False,
        "base_band_color": None,
        "window_grid": "house",
        "source": "palette_by_id",
        "is_estimated": True,
    }


def observed_appearance(entry: dict, observed: dict, face_id: str, levels) -> dict:
    flags = feature_flags(entry.get("features"))
    appearance = {
        "ground_floor": ground_floor_kind(entry.get("features")),
        "roof": "gable_tile" if flags["pitched_roof"] else "flat",
        "balconies": flags["balconies"],
        "base_band_color": "#8a4b35" if flags["brick_base"] else None,
        "window_grid": "tower" if isinstance(levels, int) and levels >= 6 else "house",
        "source": "mapillary_reference",
        "reference_face": face_id,
        "reference_images": [img.get("pkey") for img in observed.get("images", [])],
        "reference_confidence": entry.get("confidence"),
        "reference_features": entry.get("features"),
    }
    color = entry.get("facade_color")
    if isinstance(color, str) and len(color) == 7 and color.startswith("#"):
        appearance["facade_color"] = color.lower()
    return appearance


def gable_roof(polygon, front, top: float, gen: dict) -> trimesh.Trimesh | None:
    """Gable roof with the ridge parallel to the street; None when not a near rectangle."""
    if not isinstance(polygon, Polygon):
        return None
    rect = polygon.minimum_rotated_rectangle
    if rect.area <= 0 or polygon.area / rect.area < 0.9:
        return None
    rect = rect.buffer(ROOF_EAVE_M, join_style=MITRE)
    c = list(rect.exterior.coords)[:4]
    sides = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    if front is not None:
        (fx0, fy0), (fx1, fy1) = front.coords[0], front.coords[-1]
        fdir = np.array([fx1 - fx0, fy1 - fy0])
    else:
        fdir = np.array(sides[0][1]) - np.array(sides[0][0])
    fdir = fdir / max(np.linalg.norm(fdir), 1e-9)

    def parallel(side):
        d = np.array(side[1]) - np.array(side[0])
        return abs(np.dot(d / max(np.linalg.norm(d), 1e-9), fdir))

    i = max(range(4), key=lambda k: parallel(sides[k]))
    a, b = np.array(sides[i][0]), np.array(sides[i][1])
    cc, d = np.array(sides[(i + 2) % 4][0]), np.array(sides[(i + 2) % 4][1])  # cc pairs with b, d with a
    half_depth = np.linalg.norm(d - a) / 2
    rise = half_depth * np.tan(np.radians(gen.get("tile_roof_pitch_deg", TILE_ROOF_PITCH_DEG)))
    m1, m2 = (a + d) / 2, (b + cc) / 2
    v = np.array([[*a, top], [*b, top], [*cc, top], [*d, top], [*m1, top + rise], [*m2, top + rise]])
    f = np.array([[0, 1, 5], [0, 5, 4], [2, 3, 4], [2, 4, 5], [0, 4, 3], [1, 2, 5], [0, 3, 2], [0, 2, 1]])
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=True)
    trimesh.repair.fix_normals(mesh)
    mesh.apply_transform(TO_GODOT)
    return mesh


def generate(gen: dict, area_config: dict, osm: aa.OsmData, extra, extra_source, out: Path,
             reference: dict | None = None) -> dict:
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
    faces = block_faces(platforms, streets_l)
    lot_faces = block_faces(lots, streets_l)
    osm_by_block: dict[str, list] = {name: [] for name in blocks}
    for b in buildings:
        if b.block and b.source == "openstreetmap":
            osm_by_block[b.block].append(to_local(b.footprint, origin).intersection(lots[b.block]))
    frontages = frontage_volumes(lot_faces, lots, osm_by_block, reference, gen, warnings)
    frontage_union = {name: unary_union([f["polygon"] for f in frontages if f["block"] == name]) for name in blocks}

    specs = []  # one entry per building to build, whatever its source
    for b in sorted((b for b in buildings if b.block), key=lambda b: b.id):
        footprint = to_local(b.footprint, origin)
        clipped = footprint.intersection(lots[b.block])
        if b.source != "openstreetmap" and not frontage_union[b.block].is_empty:
            overlap = clipped.intersection(frontage_union[b.block]).area
            if overlap > REPLACED_OVERLAP * clipped.area:
                warnings.append(f"{b.id}: replaced by photo-based frontage ({overlap / clipped.area:.0%} overlap)")
                continue
            clipped = clipped.difference(frontage_union[b.block])
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
        appearance = default_appearance(b.id, gen)
        levels = b.levels
        matched = match_frontage(clipped, b.block, faces, reference)
        if matched:
            face_id, entry, observed = matched
            observed_levels = entry.get("levels")
            if isinstance(observed_levels, int) and observed_levels > 0 and b.height_m is None:
                levels = observed_levels
                height = observed_levels * gen["level_height_m"]
                estimated, rule = True, "reference photo levels x level_height_m (mapillary)"
            elif observed_levels == 0:
                warnings.append(f"{b.id}: reference photo of {face_id} shows no building here "
                                f"({', '.join(entry.get('features') or [])}); footprint kept")
            appearance.update(observed_appearance(entry, observed, face_id, levels))
        specs.append({
            "id": b.id, "source": b.source, "source_id": b.source_id, "source_dataset": b.source_dataset,
            "confidence": b.confidence, "block": b.block, "polygon": clipped,
            "clipped_to_lot": round(1 - clipped.area / footprint.area, 3) if footprint.area else 0.0,
            "height": height, "levels": levels, "height_is_estimated": estimated, "height_rule": rule,
            "geometry_is_estimated": b.source != "openstreetmap",
            "geometry_rule": "source footprint" if b.source == "openstreetmap" else "machine-learned footprint",
            "building_type": b.tags.get("building", "unknown") if b.source == "openstreetmap" else "unknown",
            "appearance": appearance, "front": None,
        })
    for f in frontages:
        specs.append({
            "id": f["id"], "source": "mapillary_reference", "source_id": f"{f['face_id']}#{f['order']}",
            "source_dataset": "Mapillary street-level observation", "confidence": f["entry"].get("confidence"),
            "block": f["block"], "polygon": f["polygon"], "clipped_to_lot": 0.0,
            "height": f["levels"] * gen["level_height_m"], "levels": f["levels"], "height_is_estimated": True,
            "height_rule": "reference photo levels x level_height_m (mapillary)",
            "geometry_is_estimated": True,
            "geometry_rule": f"observed frontage share on the property line x {f['depth']} m estimated depth",
            "building_type": "unknown",
            "appearance": {**default_appearance(f["id"], gen),
                           **observed_appearance(f["entry"], f["observed"], f["face_id"], f["levels"])},
            "front": f["front"],
        })

    building_meta, building_meshes = [], []
    for spec in sorted(specs, key=lambda x: x["id"]):
        clipped, height = spec["polygon"], spec["height"]
        top = curb + height
        appearance = spec["appearance"]
        parts = [slab(clipped, 0.0, top, spec["id"])]
        roof = gable_roof(clipped, spec["front"], top, gen) if appearance.get("roof") == "gable_tile" else None
        if roof is not None:
            parts.append(roof)
        else:
            appearance["roof"] = "flat"
            cornice = gen["cornice"]
            parts.append(slab(clipped.buffer(cornice["overhang_m"], join_style=MITRE),
                              top - cornice["drop_m"] - cornice["height_m"], top - cornice["drop_m"], spec["id"]))
        mesh = trimesh.util.concatenate(parts)
        rgb = gen["colors"]["building_surveyed" if spec["source"] == "openstreetmap" else "building_machine_learned"]
        building_meshes.append((spec["id"], mesh, rgb))
        building_meta.append({
            "id": spec["id"],
            "source": spec["source"],
            "source_id": spec["source_id"],
            "source_dataset": spec["source_dataset"],
            "confidence": spec["confidence"],
            "block": spec["block"],
            "footprint": ring_coords(clipped),
            "footprint_area_m2": round(clipped.area, 2),
            "clipped_to_lot": spec["clipped_to_lot"],
            "geometry_is_estimated": spec["geometry_is_estimated"],
            "geometry_rule": spec["geometry_rule"],
            "base_y": curb,
            "height_m": round(height, 2),
            "levels": spec["levels"],
            "height_is_estimated": spec["height_is_estimated"],
            "height_rule": spec["height_rule"],
            "building_type": spec["building_type"],
            "model": "generic_building",
            "appearance": appearance,
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

    props, prop_warnings = extract_props(osm, origin, extent, roadway, all_platforms, streets_l,
                                         gen["props"], curb)
    warnings += prop_warnings
    props += reference_trees(faces, platforms, reference, curb)

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
            "props": "positions and species from OSM; heights by type unless tagged: "
                     f"tree {gen['props']['tree_height_m']} m, palm {gen['props']['palm_height_m']} m, "
                     f"street lamp {gen['props']['street_lamp_height_m']} m",
            "terrain": "flat at y = 0 (no elevation data used)",
            "facades": f"{gen['facade_style']}: stylized windows/shopfront/cornice, colour picked from a palette by building id; not real appearance",
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
        "props": props,
        "warnings": warnings,
    }
    (out / "scenario.json").write_text(json.dumps(metadata, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"metadata": metadata, "roadway": roadway, "platforms": platforms, "sidewalks": sidewalks,
            "lots": lots, "extent": extent, "faces": faces}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gen_config", type=Path)
    parser.add_argument("area_config", type=Path)
    parser.add_argument("osm_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--extra-buildings", type=Path)
    parser.add_argument("--reference", type=Path, help="street-level photo observations (JSON)")
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
    reference, reference_source = None, None
    if args.reference:
        data = json.loads(args.reference.read_text(encoding="utf-8"))
        reference = {face["face_id"]: face for face in data["faces"]}
        reference_source = {k: data.get(k) for k in ("source", "license", "surveyed_at_utc", "method")}
        reference_source["file"] = args.reference.name
    result = generate(gen, area_config, osm, extra, extra_source, args.output_dir, reference)
    if reference_source:
        meta_path = args.output_dir / "scenario.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["sources"].append(reference_source)
        meta["attribution"] += "; street-level reference photos from Mapillary contributors (CC BY-SA 4.0)"
        meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        result["metadata"] = meta
    meta = result["metadata"]
    estimated = sum(1 for b in meta["buildings"] if b["height_is_estimated"])
    kinds = {k: sum(1 for p in meta["props"] if p["type"] == k) for k in ("tree", "palm", "street_lamp")}
    print(f"props: {kinds}")
    print(f"buildings: {len(meta['buildings'])} ({estimated} estimated heights); "
          f"street segments: {len(meta['street_segments'])}; spawn: {meta['spawn']}; "
          f"sidewalk offset: {meta['estimation_rules']['sidewalk_centerline_offset_m']} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
