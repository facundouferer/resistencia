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

    def test_props_come_from_osm_trees_and_lamps(self):
        props = self.meta["props"]
        raw = json.loads(OSM.read_text())
        osm_ids = {f"osm_node_{e['id']}" for e in raw["elements"] if e["type"] == "node"
                   and (e.get("tags", {}).get("natural") == "tree" or e.get("tags", {}).get("highway") == "street_lamp")}
        ids = [p["id"] for p in props]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(set(ids) <= osm_ids)
        self.assertEqual({p["type"] for p in props}, {"tree", "palm", "street_lamp"})
        extent = self.result["extent"]
        for p in props:
            self.assertTrue(extent.contains(Point(p["position"])), p["id"])
            self.assertTrue(p["height_is_estimated"])
            if p["type"] == "palm":
                self.assertIn(p["genus"], ["Phoenix", "Syagrus", "Butia", "Washingtonia", "Livistona", "Trachycarpus"])
            if p["surface"] == "roadway":
                self.assertTrue(any(p["id"] in w for w in self.meta["warnings"]), p["id"])
                self.assertTrue(self.result["roadway"].contains(Point(p["position"])))

    def test_metadata_has_required_fields_and_resource_hashes(self):
        written = json.loads((self.out / "scenario.json").read_text())
        for key in REQUIRED_METADATA:
            self.assertIn(key, written)
        self.assertEqual(written["projection"], "EPSG:32721")
        self.assertEqual(set(written["resources"]), {"terrain.glb", "streets.glb", "sidewalks.glb", "buildings.glb"})

    def test_spawn_is_on_a_sidewalk(self):
        spawn = self.meta["spawn"]
        self.assertTrue(self.result["sidewalks"]["block_s"].contains(Point(spawn["x"], -spawn["z"])))


FAKE_REFERENCE = {  # test data, not a real survey
    "block_s:Pueyrredón": {
        "face_id": "block_s:Pueyrredón", "visibility": "good",
        "images": [{"pkey": "test-image", "captured": "2015-12-20", "author": "test"}],
        "trees": {"present": True, "approx_count": 5},
        "buildings": [
            {"order": 1, "frontage_fraction": 0.5, "levels": 4, "facade_color": "#112233", "features": ["shopfront"]},
            {"order": 2, "frontage_fraction": 0.5, "levels": 1, "facade_color": "#445566", "features": ["garage door"]},
        ],
    },
    "block_n:Corrientes": {"face_id": "block_n:Corrientes", "visibility": "none", "trees": None, "buildings": None},
    "block_n:Remedios de Escalada": {
        "face_id": "block_n:Remedios de Escalada", "visibility": "good", "images": [], "trees": {"present": False},
        "buildings": [
            {"order": 1, "frontage_fraction": 0.5, "levels": 3, "facade_color": "#778899",
             "features": ["pitched tile roof", "balconies", "white house with red-brick base"]},
            {"order": 2, "frontage_fraction": 0.25, "levels": None, "features": ["unknown"]},
            {"order": 3, "frontage_fraction": 0.25, "levels": 0, "features": ["vacant lot"]},
        ],
    },
}


@unittest.skipUnless(OSM.exists() and OVERTURE.exists(), "raw sources not downloaded")
class ReferenceObservations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        gen = json.loads((ROOT / "tools/geometry_generator/config/resistencia_2x2.json").read_text())
        area = json.loads((ROOT / "tools/geo_processor/areas/resistencia_2x2.json").read_text())
        extra = aa.load_overture_buildings(OVERTURE)
        cls.result = gs.generate(gen, area, aa.load_osm(OSM), extra, {"source": "overture_maps"},
                                 Path(cls._tmp.name), FAKE_REFERENCE)
        cls.meta = cls.result["metadata"]

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_faces_match_the_survey_list(self):
        surveyed = json.loads((ROOT / "tools/reference/faces_resistencia_2x2.json").read_text())
        faces = self.result["faces"]
        self.assertEqual(sorted(faces), sorted(f["face_id"] for f in surveyed))
        for face in surveyed:
            generated = faces[face["face_id"]]
            self.assertEqual(generated["from_corner"], face["from_corner"])
            self.assertEqual(generated["to_corner"], face["to_corner"])
            self.assertAlmostEqual(generated["line"].length, face["length_m"], delta=0.2)

    def test_observed_trees_are_placed_on_that_sidewalk(self):
        trees = [p for p in self.meta["props"] if p["source"] == "mapillary_reference"]
        self.assertEqual(len(trees), 5)
        sidewalk = self.result["sidewalks"]["block_s"]
        for tree in trees:
            self.assertEqual(tree["source_id"], "block_s:Pueyrredón")
            self.assertTrue(sidewalk.contains(Point(tree["position"])), tree["id"])
            self.assertTrue(tree["height_is_estimated"])

    def test_facing_buildings_take_observed_levels_colour_and_ground_floor(self):
        facing = [b for b in self.meta["buildings"] if b["appearance"].get("reference_face") == "block_s:Pueyrredón"]
        self.assertGreater(len(facing), 0)
        for b in facing:
            self.assertIn((b["levels"], b["appearance"]["facade_color"], b["appearance"]["ground_floor"]),
                          [(4, "#112233", "shopfront"), (1, "#445566", "garage")])
            self.assertAlmostEqual(b["height_m"], b["levels"] * 3.0)
            self.assertTrue(b["height_is_estimated"])
            self.assertIn("mapillary", b["height_rule"])
        others = [b for b in self.meta["buildings"] if "reference_face" not in b["appearance"]]
        self.assertTrue(all(b["height_m"] == 6.0 for b in others))

    def test_frontages_are_built_on_the_property_line_only_for_known_levels(self):
        built = [b for b in self.meta["buildings"] if b["source"] == "mapillary_reference"
                 and b["appearance"]["reference_face"] == "block_n:Remedios de Escalada"]
        self.assertEqual([b["id"] for b in built], ["ref_block_n_Remedios_de_Escalada_1"])
        b = built[0]
        lot = self.result["lots"]["block_n"]
        footprint = Polygon(b["footprint"][0])
        self.assertTrue(lot.buffer(0.01).contains(footprint))
        front = self.result["faces"]["block_n:Remedios de Escalada"]["line"]
        self.assertLess(footprint.distance(front), 3.0 + 0.05)  # sidewalk width: lot edge = property line
        self.assertAlmostEqual(footprint.exterior.distance(lot.exterior), 0.0, places=2)
        self.assertTrue(b["geometry_is_estimated"])
        self.assertEqual((b["levels"], b["height_m"]), (3, 9.0))
        appearance = b["appearance"]
        self.assertEqual((appearance["roof"], appearance["balconies"], appearance["base_band_color"]),
                         ("gable_tile", True, "#8a4b35"))

    def test_frontages_replace_overture_but_never_overlap_osm(self):
        buildings = self.meta["buildings"]
        self.assertEqual(len([b for b in buildings if b["source"] == "openstreetmap"]), 39)
        ref = [Polygon(r) for b in buildings if b["source"] == "mapillary_reference" for r in b["footprint"]]
        others = [Polygon(r) for b in buildings if b["source"] != "mapillary_reference" for r in b["footprint"]]
        for poly in ref:
            for other in others:
                self.assertLess(poly.intersection(other).area, 0.05)
        self.assertTrue(any("replaced by photo-based frontage" in w for w in self.meta["warnings"]))

    def test_gable_roof_rises_above_the_walls(self):
        scene = trimesh.load(Path(self._tmp.name) / "buildings.glb")
        b = next(b for b in self.meta["buildings"] if b["id"] == "ref_block_n_Remedios_de_Escalada_1")
        mesh = scene.geometry[b["id"]]
        self.assertGreater(mesh.bounds[1][1], b["base_y"] + b["height_m"] + 1.0)


class FeatureKeywords(unittest.TestCase):
    def test_free_text_features_map_to_flags(self):
        self.assertEqual(gs.feature_flags(["red tile canopy/pitched tile roof", "ornate iron balcony"]),
                         {"pitched_roof": True, "balconies": True, "brick_base": False})
        self.assertEqual(gs.feature_flags(["brick bands", "flat roof"]),
                         {"pitched_roof": False, "balconies": False, "brick_base": True})
        self.assertEqual(gs.feature_flags(None), {"pitched_roof": False, "balconies": False, "brick_base": False})


if __name__ == "__main__":
    unittest.main()
