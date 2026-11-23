"""1.6.0: common I/O box, chain topology, clearances, web-first pictures, fixed categories."""
import copy
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_diagram as B
import image_cache
import reference_layout as R
from cables import Cables
from components import Components

ROOT = os.path.abspath(B.ROOT)


def load():
    return B.load_json(os.path.join(ROOT, "samples", "two_plc_systems.json"))


class TopologyTests(unittest.TestCase):
    def build(self, spec):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return B.build(spec, os.path.join(ROOT, "base", "base.vsdx"), os.path.join(tmp.name, "a.vsdx"), spec_dir=os.path.join(ROOT, "samples"))

    def test_sample_builds_with_no_warnings_except_size_or_quality(self):
        result = self.build(load())
        self.assertEqual([w for w in result["warnings"] if "pixels per displayed inch" not in w], [])

    def test_each_plc_system_has_one_common_io_box_and_no_rack_boxes(self):
        spec = load()
        shapes, lines, warnings = B.prepare(spec, Components(), Cables(), os.path.join(ROOT, "samples"))
        B.apply_layers(spec, shapes, warnings)
        self.assertFalse([s for s in shapes if s["id"].startswith("__rack_")])
        for n in (1, 2):
            io = next(s for s in shapes if s["id"] == "io%d" % n)
            self.assertTrue(io["solid"])
            racks = [s for s in shapes if s.get("parent") == io["id"]]
            self.assertEqual(len(racks), 4)
            self.assertEqual(len({round(r["y"], 3) for r in racks}), 1)
            xs = sorted(r["x"] + r["w"] / 2 for r in racks)
            steps = [round(b - a, 2) for a, b in zip(xs, xs[1:])]
            self.assertLessEqual(max(steps) - min(steps), .02)       # equal horizontal spacing

    def test_chain_expands_to_sequential_links_only(self):
        spec = {"lines": [{"chain": ["a", "b", "c", "d"], "cable": "ethernet", "label": "x"}]}
        B.expand_chains(spec)
        self.assertEqual([(l["from"], l["to"]) for l in spec["lines"]], [("a", "b"), ("b", "c"), ("c", "d")])
        self.assertTrue(all(l["label"] == "x" for l in spec["lines"]))
        with self.assertRaises(B.BuildError):
            B.expand_chains({"lines": [{"chain": ["a"], "cable": "ethernet"}]})

    def test_racks_are_not_connected_by_adjacency(self):
        spec = load()
        spec["lines"] = [l for l in spec["lines"] if "chain" not in l]
        result = self.build(spec)
        self.assertTrue([w for w in result["warnings"] if "has no communication line" in w])
        links = {(c["a"], c["b"]) for c in result["display_connections"] if c["cable"] == "ethernet"}
        self.assertFalse(any(a.startswith("r1_") and b.startswith("r1_") for a, b in links))

    def test_each_instrument_group_has_one_representative_hardwired_cable(self):
        result = self.build(load())
        trunks = [c for c in result["display_connections"] if c.get("representative")]
        self.assertEqual({(c["a"], c["b"]) for c in trunks}, {("inst1", "io1"), ("inst2", "io2")})
        self.assertTrue(all(len(c["source_connections"]) == 3 for c in trunks))
        self.assertEqual(len(result["logical_connections"]), len([1 for l in load()["lines"] if "chain" not in l]) + 8)

    def test_redundancy_link_stays_on_the_plcs(self):
        result = self.build(load())
        link = next(c for c in result["display_connections"] if c.get("label") == "Redundancy Link")
        self.assertEqual((link["a"], link["b"]), ("plc1", "plc2"))

    def test_lines_stay_orthogonal_and_clear_of_pictures(self):
        result = self.build(load())
        lines = [s for s in result["page"].shapes if s["kind"] == "line" and s.get("pts")]
        self.assertTrue(lines)
        for line in lines:
            for (x0, y0), (x1, y1) in zip(line["pts"], line["pts"][1:]):
                self.assertTrue(abs(x0 - x1) < 1e-6 or abs(y0 - y1) < 1e-6 or max(abs(x0 - x1), abs(y0 - y1)) < .2)   # only crossing hops are not square
        pictures = [s for s in result["page"].shapes if s["kind"] == "image" and s["key"] != "logo"]
        for line in lines:
            for pic in pictures:
                self.assertFalse(B.crosses(line["pts"], (pic["x"], pic["y"], pic["w"], pic["h"]), inset=.15), (line["key"], pic["key"]))

    def test_unlabeled_wrapper_box_is_flagged(self):
        spec = load()
        spec["shapes"].append({"id": "wrap", "kind": "group", "layer": "control"})
        for s in spec["shapes"]:
            if s["id"] in ("sys1", "sys2"):
                s.pop("layer", None)
                s["parent"] = "wrap"
        shapes, lines, warnings = B.prepare(spec, Components(), Cables(), os.path.join(ROOT, "samples"))
        # one wrapper around two groups is fine; around a single group it is flagged
        spec["shapes"] = [s for s in spec["shapes"] if s["id"] != "sys2" and s.get("parent") != "sys2" and s.get("parent") != "io2"]
        spec["lines"] = []
        shapes, lines, warnings = B.prepare(spec, Components(), Cables(), os.path.join(ROOT, "samples"))
        B.apply_layers(spec, shapes, warnings)
        self.assertTrue([w for w in warnings if "only wraps" in w])


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.c = Components()

    def prepare(self, spec):
        return B.prepare(spec, self.c, Cables(), os.path.join(ROOT, "samples"))

    def test_fixed_categories_are_exactly_the_approved_four_plus_alternate(self):
        self.assertEqual(set(self.c.fixed), {"ethernet_switch", "ethernet_switch_variant", "fiber_optic_patch_panel", "laptop", "video_wall"})
        self.assertIsNone(self.c.fixed_for("Firewall"))

    def test_web_picture_replaces_a_non_fixed_library_picture_and_records_provenance(self):
        spec = {"shapes": [dict(id="a", label="Primary PLC", component="rack_plc", x=1, y=1, image="pictures/pressure_transmitter.png",
                                image_source="https://example.com/p.png", oem="Acme", model="X1")]}
        shapes, _, warnings = self.prepare(spec)
        self.assertTrue(shapes[0]["web"])
        self.assertIn("https://example.com/p.png", shapes[0]["key"])
        self.assertIn("Acme X1", shapes[0]["key"])
        self.assertEqual(warnings.notices, [])

    def test_missing_provenance_is_a_notice(self):
        spec = {"shapes": [dict(id="a", label="Pump", x=1, y=1, image="pictures/pressure_transmitter.png")]}
        _, _, warnings = self.prepare(spec)
        self.assertTrue([n for n in warnings.notices if "image_source" in n])
        self.assertTrue([n for n in warnings.notices if "oem and model" in n])

    def test_library_fallback_for_non_fixed_equipment_is_reported(self):
        _, _, warnings = self.prepare({"shapes": [dict(id="a", label="PLC", component="rack_plc", x=1, y=1)]})
        self.assertTrue([n for n in warnings.notices if "offline fallback" in n])
        _, _, quiet = self.prepare({"image_policy": "library", "shapes": [dict(id="a", label="PLC", component="rack_plc", x=1, y=1)]})
        self.assertEqual(quiet.notices, [])
        _, _, fixed = self.prepare({"shapes": [dict(id="a", label="Ethernet switch", x=1, y=1)]})
        self.assertEqual(fixed.notices, [])                                       # fixed categories never need a web picture

    def test_fixed_image_still_cannot_be_replaced_without_override(self):
        spec = {"shapes": [dict(id="a", label="Laptop", component="laptop", x=1, y=1, image="pictures/pressure_transmitter.png")]}
        with self.assertRaises(B.BuildError):
            self.prepare(spec)

    def test_image_cache_stores_and_finds_with_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "c")
            src = os.path.join(ROOT, "samples", "pictures", "pressure_transmitter.png")
            path = image_cache.add(src, "https://example.com/pt.png", "Acme", "PT-100", cache)
            self.assertEqual(image_cache.find("Acme", "PT-100", cache), path)
            self.assertIsNone(image_cache.find("Acme", "Other", cache))
            with self.assertRaises(ValueError):
                image_cache.add(src, "not a url", "Acme", "PT-100", cache)
            with self.assertRaises(ValueError):
                image_cache.add(src, "https://example.com/x", "", "PT-100", cache)


if __name__ == "__main__":
    unittest.main()
