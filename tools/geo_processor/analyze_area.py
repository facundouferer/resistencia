"""Identify and measure the study blocks from raw OpenStreetMap data.

Reads the unmodified Overpass JSON, reprojects to EPSG:32721 and:

* finds the corners where the four boundary streets intersect;
* builds the blocks as the cells enclosed by the street centerlines;
* assigns every OSM building (way or multipolygon) to its block;
* reports measurements, missing data and doubtful entities.

Outputs (in the output directory):
    area.geojson      WGS 84 features for viewing in a GIS (QGIS, geojson.io)
    area_report.json  measurements, local origin and warnings
    preview.svg       quick visual check without a GIS

Usage:
    python tools/geo_processor/analyze_area.py AREA_CONFIG OSM_JSON OUTPUT_DIR \
        [--extra-buildings OVERTURE_GEOJSON]
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, Polygon, mapping
import numpy as np
import shapely
from shapely.ops import polygonize, unary_union

GENERATOR_VERSION = "0.1.0"
WORK_CRS = 32721  # WGS 84 / UTM zone 21S
GEO_CRS = 4326
STREET_HIGHWAYS = {"primary", "secondary", "tertiary", "residential", "living_street", "unclassified"}

_to_utm = Transformer.from_crs(GEO_CRS, WORK_CRS, always_xy=True)
_to_geo = Transformer.from_crs(WORK_CRS, GEO_CRS, always_xy=True)


@dataclass
class OsmData:
    nodes: dict[int, tuple[float, float]]  # id -> (E, N) in EPSG:32721
    ways: dict[int, dict]
    relations: list[dict]
    osm_base_timestamp: str | None = None
    node_tags: dict[int, dict] = field(default_factory=dict)  # tagged nodes only


@dataclass
class Building:
    id: str
    source_id: str
    footprint: Polygon
    tags: dict
    height_m: float | None = None
    levels: float | None = None
    block: str | None = None
    warnings: list[str] = field(default_factory=list)
    source: str = "openstreetmap"
    source_dataset: str = "OpenStreetMap"
    confidence: float | None = None  # only for machine-learned footprints


# An extra footprint overlapping an OSM building by more than this share of
# its own area is considered the same building and dropped.
DUPLICATE_OVERLAP = 0.2


def load_overture_buildings(path: Path) -> list[Building]:
    """Overture building features that do not come from OpenStreetMap.

    OSM-derived Overture features are skipped: OSM is read directly from
    the raw OSM download, which is the primary source.
    """
    buildings = []
    for f in json.loads(path.read_text(encoding="utf-8"))["features"]:
        sources = f["properties"].get("sources") or []
        datasets = [s.get("dataset") for s in sources]
        if "OpenStreetMap" in datasets or f["geometry"]["type"] not in ("Polygon", "MultiPolygon"):
            continue
        footprint = shapely.transform(
            shapely.geometry.shape(f["geometry"]),
            lambda c: np.column_stack(_to_utm.transform(c[:, 0], c[:, 1])),
        )
        confidences = [s["confidence"] for s in sources if s.get("confidence") is not None]
        buildings.append(Building(
            id=f"overture_{f['id']}", source_id=f["id"], footprint=footprint, tags={},
            source="overture_maps", source_dataset=", ".join(d for d in datasets if d),
            confidence=min(confidences) if confidences else None,
        ))
    return buildings


def merge_extra_buildings(primary: list[Building], extra: list[Building]) -> tuple[list[Building], int]:
    """Add extra footprints that do not duplicate a primary building."""
    tree = shapely.STRtree([b.footprint for b in primary])
    kept, duplicates = [], 0
    for building in extra:
        candidates = tree.query(building.footprint, predicate="intersects")
        overlap = sum(primary[i].footprint.intersection(building.footprint).area for i in candidates)
        if overlap > DUPLICATE_OVERLAP * building.footprint.area:
            duplicates += 1
        else:
            kept.append(building)
    return primary + kept, duplicates


def load_osm(path: Path) -> OsmData:
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes, ways, relations, node_tags = {}, {}, [], {}
    for element in raw["elements"]:
        if element["type"] == "node":
            nodes[element["id"]] = _to_utm.transform(element["lon"], element["lat"])
            if element.get("tags"):
                node_tags[element["id"]] = element["tags"]
        elif element["type"] == "way":
            ways[element["id"]] = element
        elif element["type"] == "relation":
            relations.append(element)
    return OsmData(nodes, ways, relations, raw.get("osm3s", {}).get("timestamp_osm_base"), node_tags)


def way_line(osm: OsmData, way: dict) -> LineString:
    return LineString([osm.nodes[node_id] for node_id in way["nodes"]])


def street_lines(osm: OsmData, names: list[str]) -> dict[str, MultiLineString]:
    """Merged centerline of every named street (driveable highway classes only)."""
    lines: dict[str, list[LineString]] = {name: [] for name in names}
    for way in osm.ways.values():
        tags = way.get("tags", {})
        if tags.get("name") in lines and tags.get("highway") in STREET_HIGHWAYS:
            lines[tags["name"]].append(way_line(osm, way))
    missing = [name for name, found in lines.items() if not found]
    if missing:
        raise ValueError(f"streets not found in OSM data: {missing}")
    return {name: unary_union(found) for name, found in lines.items()}


def single_intersection(a, b, label: str) -> Point:
    points = [g for g in getattr(a.intersection(b), "geoms", [a.intersection(b)]) if g.geom_type == "Point"]
    if len(points) != 1:
        raise ValueError(f"{label}: expected exactly one intersection, found {len(points)}")
    return points[0]


def compass(dx: float, dy: float) -> str:
    angle = math.degrees(math.atan2(dx, dy)) % 360  # 0 = north, clockwise
    return ("n", "ne", "e", "se", "s", "sw", "w", "nw")[int((angle + 22.5) // 45) % 8]


def find_blocks(streets: dict[str, MultiLineString], boundary: Polygon, expected: int) -> dict[str, Polygon]:
    """Cells enclosed by street centerlines inside the boundary, named by compass direction."""
    cells = [
        cell
        for cell in polygonize(unary_union(list(streets.values())))
        if boundary.buffer(1.0).contains(cell)
    ]
    if len(cells) != expected:
        raise ValueError(f"expected {expected} blocks, found {len(cells)}")
    center = boundary.centroid
    blocks = {}
    for cell in cells:
        name = f"block_{compass(cell.centroid.x - center.x, cell.centroid.y - center.y)}"
        if name in blocks:
            raise ValueError(f"two blocks share direction {name}")
        blocks[name] = cell
    return dict(sorted(blocks.items()))


def ring(osm: OsmData, way_ids: list[int]) -> list[Polygon]:
    return list(polygonize(unary_union([way_line(osm, osm.ways[w]) for w in way_ids if w in osm.ways])))


def parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", ".").removesuffix("m").strip())
    except ValueError:
        return None


def collect_buildings(osm: OsmData) -> tuple[list[Building], list[str]]:
    buildings, warnings = [], []
    for way in osm.ways.values():
        tags = way.get("tags", {})
        if "building" not in tags:
            continue
        if way["nodes"][0] != way["nodes"][-1] or len(way["nodes"]) < 4:
            warnings.append(f"way/{way['id']}: building way is not a closed ring, skipped")
            continue
        buildings.append(Building(f"osm_way_{way['id']}", f"way/{way['id']}", Polygon(way_line(osm, way).coords), tags))
    for relation in osm.relations:
        tags = relation.get("tags", {})
        if "building" not in tags or tags.get("type") != "multipolygon":
            continue
        outer = ring(osm, [m["ref"] for m in relation["members"] if m["type"] == "way" and m["role"] == "outer"])
        inner = ring(osm, [m["ref"] for m in relation["members"] if m["type"] == "way" and m["role"] == "inner"])
        if not outer:
            warnings.append(f"relation/{relation['id']}: multipolygon outer ring incomplete, skipped")
            continue
        footprint = unary_union(outer).difference(unary_union(inner)) if inner else unary_union(outer)
        buildings.append(Building(f"osm_relation_{relation['id']}", f"relation/{relation['id']}", footprint, tags))

    for building in buildings:
        building.height_m = parse_number(building.tags.get("height"))
        building.levels = parse_number(building.tags.get("building:levels"))
        if "height" in building.tags and building.height_m is None:
            building.warnings.append(f"unparseable height '{building.tags['height']}'")
        if not building.footprint.is_valid:
            building.warnings.append("invalid footprint geometry")
    return buildings, warnings


def assign_blocks(buildings: list[Building], blocks: dict[str, Polygon]) -> None:
    for building in buildings:
        point = building.footprint.representative_point()
        for name, cell in blocks.items():
            if cell.contains(point):
                building.block = name
                break


def to_geo(geometry):
    return shapely.transform(geometry, lambda c: np.column_stack(_to_geo.transform(c[:, 0], c[:, 1])))


def round_coords(value, digits: int = 7):
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, (list, tuple)):
        return [round_coords(v, digits) for v in value]
    if isinstance(value, dict):
        return {k: round_coords(v, digits) for k, v in value.items()}
    return value


def feature(geometry, properties: dict) -> dict:
    return {"type": "Feature", "properties": properties, "geometry": round_coords(mapping(to_geo(geometry)))}


def side_lengths(polygon: Polygon) -> list[float]:
    """Corner-to-corner side lengths; collinear intermediate vertices are dropped."""
    coords = list(polygon.simplify(1.0).exterior.coords)
    return [round(Point(a).distance(Point(b)), 1) for a, b in zip(coords, coords[1:])]


def write_svg(path: Path, boundary: Polygon, blocks: dict[str, Polygon], streets: dict, buildings: list[Building]) -> None:
    minx, miny, maxx, maxy = boundary.buffer(40).bounds
    scale = 800 / max(maxx - minx, maxy - miny)

    def pts(coords) -> str:
        return " ".join(f"{(x - minx) * scale:.1f},{(maxy - y) * scale:.1f}" for x, y in coords)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{(maxx - minx) * scale:.0f}" height="{(maxy - miny) * scale:.0f}" style="background:#fff">']
    for name, cell in blocks.items():
        parts.append(f'<polygon points="{pts(cell.exterior.coords)}" fill="#e8efe0" stroke="#9a9" />')
        c = cell.centroid
        parts.append(f'<text x="{(c.x - minx) * scale:.0f}" y="{(maxy - c.y) * scale:.0f}" font-size="14" fill="#575">{name}</text>')
    for building in buildings:
        polys = getattr(building.footprint, "geoms", [building.footprint])
        if building.height_m is not None or building.levels is not None:
            color = "#c0392b"
        elif building.source == "openstreetmap":
            color = "#888"
        else:
            color = "#3b7dd8"
        for poly in polys:
            parts.append(f'<polygon points="{pts(poly.exterior.coords)}" fill="{color}" fill-opacity="0.6" stroke="#333" stroke-width="0.5" />')
    for name, lines in streets.items():
        for line in getattr(lines, "geoms", [lines]):
            parts.append(f'<polyline points="{pts(line.coords)}" fill="none" stroke="#2c3e50" stroke-width="2" />')
    parts.append(f'<polygon points="{pts(boundary.exterior.coords)}" fill="none" stroke="#e67e22" stroke-width="2" stroke-dasharray="6 4" />')
    parts.append('<text x="8" y="20" font-size="12">Data © OpenStreetMap contributors (ODbL). Red: real height/levels. Grey: OSM, no height. Blue: machine-learned footprint (Overture), no height.</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def analyze(config: dict, osm: OsmData, extra_buildings: list[Building] | None = None,
            extra_source: dict | None = None) -> tuple[dict, list[dict], dict, list[Building], Polygon, dict]:
    boundary_names = config["boundary_streets"]
    inner_names = config["inner_streets"]
    streets = street_lines(osm, boundary_names + inner_names)

    corners = {}
    for a, b in zip(boundary_names, boundary_names[1:] + boundary_names[:1]):
        corners[f"{a} x {b}"] = single_intersection(streets[a], streets[b], f"{a} x {b}")
    boundary = Polygon([p.coords[0] for p in corners.values()])
    if not boundary.is_valid:
        raise ValueError("boundary corners do not form a simple polygon; check street order in config")

    origin_point = single_intersection(streets[inner_names[0]], streets[inner_names[1]], " x ".join(inner_names))
    origin = (round(origin_point.x), round(origin_point.y))

    blocks = find_blocks(streets, boundary, config["expected_blocks"])
    buildings, warnings = collect_buildings(osm)
    duplicates = 0
    if extra_buildings:
        buildings, duplicates = merge_extra_buildings(buildings, extra_buildings)
    assign_blocks(buildings, blocks)

    # Whole-area building parts are reported, not modelled yet.
    part_count = sum(1 for w in osm.ways.values() if "building:part" in w.get("tags", {}))
    if part_count:
        warnings.append(f"{part_count} building:part ways present; not used for footprints yet")

    in_area = [b for b in buildings if b.block]
    without_height = [b for b in in_area if b.height_m is None and b.levels is None]
    if without_height:
        warnings.append(f"{len(without_height)} of {len(in_area)} buildings in the blocks have no height or levels")
    machine_learned = [b for b in in_area if b.source != "openstreetmap"]
    if machine_learned:
        warnings.append(f"{len(machine_learned)} building footprints in the blocks are machine-learned (Overture), "
                        "not surveyed; shapes and separation between adjacent buildings are approximate")

    block_reports = {}
    for name, cell in blocks.items():
        inside = [b for b in in_area if b.block == name]
        covered = unary_union([b.footprint for b in inside]).area if inside else 0.0
        coverage = covered / cell.area
        block_reports[name] = {
            "centerline_cell_area_m2": round(cell.area, 1),
            "centerline_cell_sides_m": side_lengths(cell),
            "building_count": len(inside),
            "buildings_by_dataset": dict(sorted(collections.Counter(b.source_dataset for b in inside).items())),
            "building_footprint_coverage": round(coverage, 3),
            "buildings_with_height_or_levels": sum(1 for b in inside if b.height_m is not None or b.levels is not None),
        }
        if coverage < 0.2:
            warnings.append(f"{name}: buildings cover only {coverage:.0%} of the cell; footprints may be incomplete or the block is open space")

    origin_lon, origin_lat = _to_geo.transform(*origin)
    minx, miny, maxx, maxy = boundary.bounds
    report = {
        "scenario": config["name"],
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "generator": f"tools/geo_processor/analyze_area.py {GENERATOR_VERSION}",
        "source": {
            "name": "OpenStreetMap",
            "osm_base_timestamp": osm.osm_base_timestamp,
            "license": "Open Database License (ODbL) 1.0",
            "attribution": "© OpenStreetMap contributors",
        },
        "secondary_source": extra_source,
        "projection": f"EPSG:{WORK_CRS}",
        "units": "metres",
        "local_origin": {
            "description": f"Intersection of {' and '.join(inner_names)} centerlines, rounded to 1 m",
            "easting": origin[0],
            "northing": origin[1],
            "lat": round(origin_lat, 7),
            "lon": round(origin_lon, 7),
        },
        "godot_axes": "x = easting - origin.easting; y = height; z = -(northing - origin.northing)",
        "boundary_streets": boundary_names,
        "inner_streets": inner_names,
        "corners": {
            name: {"easting": round(p.x, 2), "northing": round(p.y, 2),
                   "lat": round(_to_geo.transform(p.x, p.y)[1], 7), "lon": round(_to_geo.transform(p.x, p.y)[0], 7)}
            for name, p in corners.items()
        },
        "boundary_sides_m": side_lengths(boundary),
        "boundary_bounds_utm": [round(v, 2) for v in (minx, miny, maxx, maxy)],
        "blocks": block_reports,
        "buildings_in_blocks": len(in_area),
        "buildings_outside_blocks": len(buildings) - len(in_area),
        "extra_buildings_dropped_as_osm_duplicates": duplicates,
        "building_warnings": {b.id: b.warnings for b in buildings if b.warnings},
        "warnings": warnings,
    }

    features = [feature(boundary, {"kind": "boundary", "name": config["name"]})]
    features += [feature(cell, {"kind": "block", "id": name}) for name, cell in blocks.items()]
    features += [feature(line, {"kind": "street_centerline", "name": name}) for name, line in streets.items()]
    features += [feature(Point(p.coords[0]), {"kind": "corner", "name": name}) for name, p in corners.items()]
    features.append(feature(Point(origin), {"kind": "local_origin"}))
    for b in buildings:
        features.append(feature(b.footprint, {
            "kind": "building", "id": b.id, "source": b.source, "source_id": b.source_id,
            "source_dataset": b.source_dataset, "confidence": b.confidence, "block": b.block, "height_m": b.height_m, "levels": b.levels,
            "building": b.tags.get("building"), "name": b.tags.get("name"),
        }))
    geojson = {
        "type": "FeatureCollection",
        "name": config["name"],
        "attribution": "© OpenStreetMap contributors, ODbL 1.0"
                       + ("; Overture Maps Foundation (Google Open Buildings, Microsoft ML Buildings)" if extra_source else ""),
        "features": features,
    }
    return report, features, geojson, buildings, boundary, {"blocks": blocks, "streets": streets}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", type=Path)
    parser.add_argument("osm_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--extra-buildings", type=Path,
                        help="Overture building GeoJSON; used where OSM has no footprint")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    osm = load_osm(args.osm_json)
    extra_buildings, extra_source = None, None
    if args.extra_buildings:
        extra_buildings = load_overture_buildings(args.extra_buildings)
        provenance = args.extra_buildings.with_name(args.extra_buildings.name.removesuffix(".geojson") + ".provenance.json")
        extra_source = json.loads(provenance.read_text(encoding="utf-8")) if provenance.exists() else {"file": args.extra_buildings.name}
        extra_source = {k: extra_source.get(k) for k in ("source", "release", "licenses", "attribution", "sha256", "file")}
    report, _, geojson, buildings, boundary, extra = analyze(config, osm, extra_buildings, extra_source)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "area_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output_dir / "area.geojson").write_text(json.dumps(geojson, ensure_ascii=False) + "\n", encoding="utf-8")
    write_svg(args.output_dir / "preview.svg", boundary, extra["blocks"], extra["streets"], [b for b in buildings if b.block])
    print(json.dumps({k: report[k] for k in ("boundary_sides_m", "blocks", "buildings_in_blocks", "warnings")}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
