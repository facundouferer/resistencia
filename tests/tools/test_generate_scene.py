"""Phase 3 acceptance checks for tools/geometry_generator/generate_scene.py.

Runs the generator on the real downloaded sources into a temporary
directory (the committed generated/ files are not touched).
Run: tools/.venv/bin/python -m unittest discover -s tests/tools
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

import trimesh
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "geometry_generator"))
sys.path.insert(0, str(ROOT / "tools" / "geo_processor"))

import analyze_area as aa  # noqa: E402
import generate_scene as gs  # noqa: E402

OSM = ROOT / "data/source/osm/resistencia_2x2.osm.json"
OVERTURE = ROOT / "data/source/overture/resistencia_2x2.buildings.geojson"
REQUIRED_METADATA = ["name", "generated_at_utc", "sources", "license", "attribution", "projection", "origin",
                     "bounds", "units", "generator", "resources", "warnings", "buildings", "spawn"]


@unittest.skipUnless(OSM.exists() and OVERTURE.exists(), "raw sources not downloaded")
class GeneratedScenario(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name)
        gen = json.loads((ROOT / "tools/geometry_generator/config/resistencia_2x2.json").read_text())
        area = json.loads((ROOT / "tools/geo_processor/areas/resistencia_2x2.json").read_text())
        extra = aa.load_overture_buildings(OVERTURE)
        cls.result = gs.generate(gen, area, aa.load_osm(OSM), extra, {"source": "overture_maps"}, cls.out)
        cls.meta = cls.result["metadata"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_blocks_match_geographic_cells(self):
        for name, block in self.meta["blocks"].items():
            cell = Polygon(block["cell"][0])
            platform = self.result["platforms"][name]
            self.assertLess(cell.centroid.distance(platform.centroid), 0.5, name)
            self.assertTrue(cell.contains(platform), name)

    def test_roadway_is_one_connected_surface(self):
        roadway = self.result["roadway"]
        self.assertEqual(roadway.geom_type, "Polygon")
        for platform in self.result["platforms"].values():
            self.assertLess(roadway.intersection(platform).area, 0.01)

    def test_sidewalks_are_closed_rings_without_holes(self):
        width = self.meta["estimation_rules"]["sidewalk_width_m"]
        for name, sidewalk in self.result["sidewalks"].items():
            self.assertEqual(sidewalk.geom_type, "Polygon", name)
            self.assertEqual(len(sidewalk.interiors), 1, name)
            expected = self.result["platforms"][name].exterior.length * width
            self.assertAlmostEqual(sidewalk.area, expected, delta=expected * 0.05)

    def test_buildings_stay_inside_their_lots_and_flag_estimated_heights(self):
        self.assertEqual(len(self.meta["buildings"]), 172)
        ids = [b["id"] for b in self.meta["buildings"]]
        self.assertEqual(len(ids), len(set(ids)))
        for b in self.meta["buildings"]:
            lot = Polygon(self.meta["blocks"][b["block"]]["lot"][0])
            for ring in b["footprint"]:
                self.assertTrue(lot.buffer(0.01).contains(Polygon(ring)), b["id"])
            self.assertEqual(b["height_is_estimated"], b["height_rule"] != "source height")
            self.assertGreater(b["height_m"], 0)

    def test_glb_files_load_with_expected_nodes(self):
        scene = trimesh.load(self.out / "buildings.glb")
        self.assertEqual(set(scene.graph.nodes_geometry), {b["id"] for b in self.meta["buildings"]})
        for b in self.meta["buildings"][:20]:
            mesh = scene.geometry[b["id"]]
            top = b["base_y"] + b["height_m"]
            self.assertAlmostEqual(mesh.bounds[1][1], top, places=3)
            # Godot axes: the roof (upward faces at the top) has the footprint area.
            roof = (mesh.face_normals[:, 1] > 0.99) & (abs(mesh.triangles_center[:, 1] - top) < 1e-3)
            self.assertAlmostEqual(mesh.area_faces[roof].sum(), b["footprint_area_m2"], delta=0.05)
        sidewalks = trimesh.load(self.out / "sidewalks.glb")
        self.assertEqual(len(sidewalks.graph.nodes_geometry), 8)

    def test_facades_are_deterministic_and_flagged_as_estimated(self):
        gen = json.loads((ROOT / "tools/geometry_generator/config/resistencia_2x2.json").read_text())
        colors = set()
        for b in self.meta["buildings"]:
            appearance = b["appearance"]
            self.assertTrue(appearance["is_estimated"])
            self.assertIn(appearance["facade_color"], gen["facade_palette"])
            self.assertEqual(appearance["facade_color"], gs.facade_color(b["id"], gen["facade_palette"]))
            colors.add(appearance["facade_color"])
        self.assertGreaterEqual(len(colors), 6)

    def test_metadata_has_required_fields_and_resource_hashes(self):
        written = json.loads((self.out / "scenario.json").read_text())
        for key in REQUIRED_METADATA:
            self.assertIn(key, written)
        self.assertEqual(written["projection"], "EPSG:32721")
        self.assertEqual(set(written["resources"]), {"terrain.glb", "streets.glb", "sidewalks.glb", "buildings.glb"})

    def test_spawn_is_on_a_sidewalk(self):
        spawn = self.meta["spawn"]
        self.assertTrue(self.result["sidewalks"]["block_s"].contains(Point(spawn["x"], -spawn["z"])))


if __name__ == "__main__":
    unittest.main()
