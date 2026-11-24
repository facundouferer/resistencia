"""Tests for tools/geo_processor/analyze_area.py.

Run: tools/.venv/bin/python -m unittest discover -s tests/tools
Synthetic fixtures below are test data, not geography of Resistencia.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "geo_processor"))

import analyze_area as aa  # noqa: E402

_TMP = tempfile.TemporaryDirectory()  # removed when the test process exits
REAL_CONFIG = ROOT / "tools/geo_processor/areas/resistencia_2x2.json"
REAL_OSM = ROOT / "data/source/osm/resistencia_2x2.osm.json"

E0, N0 = 500000.0, 7000000.0  # synthetic UTM origin
CONFIG = {
    "name": "synthetic",
    "boundary_streets": ["South St", "East St", "North St", "West St"],
    "inner_streets": ["Mid EW", "Mid NS"],
    "expected_blocks": 4,
}


class SyntheticOsm:
    """Builds an Overpass-like JSON document from UTM coordinates."""

    def __init__(self):
        self.elements, self._next = [], 1

    def node(self, e, n):
        lon, lat = aa._to_geo.transform(E0 + e, N0 + n)
        self.elements.append({"type": "node", "id": self._next, "lat": lat, "lon": lon})
        self._next += 1
        return self._next - 1

    def way(self, points, tags):
        ids = [self.node(e, n) for e, n in points]
        if points[0] == points[-1]:
            ids[-1] = ids[0]
        self.elements.append({"type": "way", "id": self._next, "nodes": ids, "tags": tags})
        self._next += 1

    def street(self, name, a, b):
        self.way([a, b], {"highway": "residential", "name": name})

    def grid(self, skip=None):
        streets = {
            "South St": ((-150, -120), (150, -120)), "Mid EW": ((-150, 0), (150, 0)), "North St": ((-150, 120), (150, 120)),
            "West St": ((-120, -150), (-120, 150)), "Mid NS": ((0, -150), (0, 150)), "East St": ((120, -150), (120, 150)),
        }
        for name, (a, b) in streets.items():
            if name != skip:
                self.street(name, a, b)
        return self

    def load(self):
        tmp = Path(tempfile.mkdtemp(dir=_TMP.name)) / "osm.json"
        tmp.write_text(json.dumps({"elements": self.elements, "osm3s": {"timestamp_osm_base": "test"}}))
        return aa.load_osm(tmp)


class AnalyzeSyntheticGrid(unittest.TestCase):
    def test_finds_four_blocks_with_measured_sides(self):
        report, *_ = aa.analyze(CONFIG, SyntheticOsm().grid().load())
        self.assertEqual(sorted(report["blocks"]), ["block_ne", "block_nw", "block_se", "block_sw"])
        for block in report["blocks"].values():
            for side in block["centerline_cell_sides_m"]:
                self.assertAlmostEqual(side, 120.0, delta=0.1)
        for side in report["boundary_sides_m"]:
            self.assertAlmostEqual(side, 240.0, delta=0.1)

    def test_local_origin_is_inner_intersection(self):
        report, *_ = aa.analyze(CONFIG, SyntheticOsm().grid().load())
        self.assertEqual((report["local_origin"]["easting"], report["local_origin"]["northing"]), (E0, N0))

    def test_assigns_buildings_and_flags_missing_height(self):
        osm = SyntheticOsm().grid()
        osm.way([(10, 10), (30, 10), (30, 30), (10, 30), (10, 10)], {"building": "yes", "height": "12 m"})
        osm.way([(-30, -30), (-10, -30), (-10, -10), (-30, -10), (-30, -30)], {"building": "yes"})
        report, _, geojson, buildings, *_ = aa.analyze(CONFIG, osm.load())
        by_block = {b.block: b for b in buildings}
        self.assertEqual(by_block["block_ne"].height_m, 12.0)
        self.assertIsNone(by_block["block_sw"].height_m)
        self.assertIn("1 of 2 buildings in the blocks have no height or levels", report["warnings"])
        props = [f["properties"] for f in geojson["features"] if f["properties"]["kind"] == "building"]
        self.assertEqual({p["source"] for p in props}, {"openstreetmap"})
        self.assertTrue(all(p["source_id"].startswith("way/") for p in props))

    def test_missing_street_fails_instead_of_guessing(self):
        with self.assertRaisesRegex(ValueError, "streets not found"):
            aa.analyze(CONFIG, SyntheticOsm().grid(skip="Mid NS").load())


def overture_file(features):
    """Writes an Overture-like GeoJSON; `features` are (id, dataset, UTM ring)."""
    out = []
    for fid, dataset, ring in features:
        coords = [list(aa._to_geo.transform(E0 + e, N0 + n)) for e, n in ring]
        out.append({"type": "Feature", "id": fid, "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {"sources": [{"dataset": dataset, "confidence": 0.8}]}})
    path = Path(tempfile.mkdtemp(dir=_TMP.name)) / "overture.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": out}))
    return path


def square(e, n, size=20):
    return [(e, n), (e + size, n), (e + size, n + size), (e, n + size), (e, n)]


class MergeOvertureBuildings(unittest.TestCase):
    def setUp(self):
        osm = SyntheticOsm().grid()
        osm.way(square(10, 10), {"building": "yes"})  # OSM building in block_ne
        self.osm = osm.load()
        self.extra = aa.load_overture_buildings(overture_file([
            ("dup", "Microsoft ML Buildings", square(12, 12)),          # same building as OSM
            ("new", "Google Open Buildings", square(-40, -40)),         # fills block_sw
            ("osm", "OpenStreetMap", square(-40, 40)),                  # OSM-derived, ignored
        ]))

    def test_skips_osm_derived_features(self):
        self.assertEqual(sorted(b.source_id for b in self.extra), ["dup", "new"])

    def test_osm_wins_and_duplicates_are_dropped(self):
        report, _, geojson, buildings, *_ = aa.analyze(CONFIG, self.osm, self.extra, {"source": "overture_maps"})
        by_id = {b.id: b for b in buildings}
        self.assertNotIn("overture_dup", by_id)
        self.assertEqual(by_id["overture_new"].block, "block_sw")
        self.assertEqual(by_id["overture_new"].source, "overture_maps")
        self.assertEqual(report["extra_buildings_dropped_as_osm_duplicates"], 1)
        self.assertEqual(report["blocks"]["block_ne"]["buildings_by_dataset"], {"OpenStreetMap": 1})
        self.assertEqual(report["blocks"]["block_sw"]["buildings_by_dataset"], {"Google Open Buildings": 1})
        self.assertTrue(any("machine-learned" in w for w in report["warnings"]))

    def test_without_extra_buildings_output_is_osm_only(self):
        report, *_ = aa.analyze(CONFIG, self.osm)
        self.assertEqual(report["extra_buildings_dropped_as_osm_duplicates"], 0)
        self.assertIsNone(report["secondary_source"])


class ProjectionRoundTrip(unittest.TestCase):
    def test_utm_round_trip_error_below_one_millimetre(self):
        for lon, lat in [(-58.9865, -27.4480), (-58.9882, -27.4496), (-58.9848, -27.4465)]:
            e, n = aa._to_utm.transform(lon, lat)
            lon2, lat2 = aa._to_geo.transform(e, n)
            e2, n2 = aa._to_utm.transform(lon2, lat2)
            self.assertLess(abs(e - e2) + abs(n - n2), 0.001)


@unittest.skipUnless(REAL_OSM.exists(), "raw OSM data not downloaded")
class AnalyzeRealArea(unittest.TestCase):
    def test_real_area_has_four_blocks_of_about_120_m(self):
        config = json.loads(REAL_CONFIG.read_text(encoding="utf-8"))
        report, *_ = aa.analyze(config, aa.load_osm(REAL_OSM))
        self.assertEqual(len(report["corners"]), 4)
        self.assertEqual(len(report["blocks"]), 4)
        for block in report["blocks"].values():
            self.assertEqual(len(block["centerline_cell_sides_m"]), 4)
            for side in block["centerline_cell_sides_m"]:
                self.assertTrue(110 < side < 130, side)


if __name__ == "__main__":
    unittest.main()
