"""Free-form diagram builder. Run:  python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_diagram as B
from cables import Cables

BASE = os.path.join(HERE, "..", "base", "base.vsdx")
EXAMPLE = os.path.join(HERE, "..", "samples", "diagram_example.json")


def spec(**kw):
    s = {"project": {"project": "P"},
         "shapes": [{"id": "a", "label": "A", "x": 1, "y": 1}, {"id": "b", "label": "B", "x": 5, "y": 1}],
         "lines": [{"from": "a", "to": "b", "cable": "ethernet"}]}
    s.update(kw)
    return s


def build(s):
    d = tempfile.mkdtemp()
    return B.build(s, BASE, os.path.join(d, "o.vsdx"), spec_dir=d)


class DiagramTests(unittest.TestCase):
    def test_the_sample_builds_one_a3_page(self):
        r = B.build(B.load_json(EXAMPLE), BASE, os.path.join(tempfile.mkdtemp(), "o.vsdx"), spec_dir=os.path.dirname(EXAMPLE))
        self.assertEqual((r["shapes"], r["lines"], r["warnings"]), (10, 6, []))
        with zipfile.ZipFile(r["out"]) as z:
            self.assertIn("visio/pages/page1.xml", z.namelist())

    def test_cable_colour_comes_from_the_table_and_the_legend_lists_it(self):
        r = build(spec())
        colours = {s["line"] for s in r["page"].shapes if s["role"] == "line"}
        self.assertIn(Cables().get("ethernet")["color"], colours)
        self.assertTrue(any(s["text"] == "Ethernet (Cu)" for s in r["page"].shapes))

    def test_the_footer_is_always_there_and_missing_values_print_tbc(self):
        texts = [s["text"] for s in build(spec())["page"].shapes]
        self.assertIn("Project:  P", texts)
        self.assertIn("End User:  TBC", texts)

    def test_bad_cable_and_unknown_shape_stop_the_build(self):
        for lines in ([{"from": "a", "to": "b", "cable": "coax"}], [{"from": "a", "to": "zz", "cable": "ethernet"}]):
            with self.assertRaises(B.BuildError):
                build(spec(lines=lines))

    def test_shape_off_the_page_is_moved_in_with_a_warning(self):
        s = spec()
        s["shapes"][0].update(x=99, y=-3)
        r = build(s)
        self.assertTrue(any("moved inside" in w for w in r["warnings"]))

    def test_missing_picture_falls_back_to_a_box(self):
        s = spec()
        s["shapes"][0]["image"] = "nope.png"
        r = build(s)
        self.assertTrue(any("picture not usable" in w for w in r["warnings"]))
        self.assertEqual(r["shapes"], 2)

    def test_another_raster_format_is_converted_when_pillow_is_there(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        d = tempfile.mkdtemp()
        Image.new("RGB", (200, 200), "red").save(os.path.join(d, "p.webp"))
        s = spec()
        s["shapes"][0]["image"] = os.path.join(d, "p.webp")
        self.assertTrue(any(x["kind"] == "image" and (x["key"] or "").startswith("image:") for x in build(s)["page"].shapes))

    def test_library_component_uses_its_picture(self):
        s = spec()
        s["shapes"][0]["component"] = "rack_server"
        self.assertTrue(any(x["kind"] == "image" and (x["key"] or "").startswith("component:rack_server") for x in build(s)["page"].shapes))

    def test_a_line_through_another_shape_is_warned_not_refused(self):
        s = spec()
        s["shapes"].append({"id": "c", "label": "C", "x": 3, "y": 1})
        self.assertTrue(any("passes through shape 'c'" in w for w in build(s)["warnings"]))

    def test_a_long_label_is_kept_and_warned(self):
        s = spec()
        s["shapes"][0].update(label="x" * 200, w=0.5, h=0.3)
        self.assertTrue(any("may not fit" in w for w in build(s)["warnings"]))

    def test_route_is_square_or_straight(self):
        a, b = (1, 5, 1, 0.5), (6, 1, 1, 0.5)
        pts = B.route(a, b, [])
        self.assertTrue(all(p[0] == q[0] or p[1] == q[1] for p, q in zip(pts, pts[1:])))
        self.assertEqual(len(B.route((1, 5, 1, 1), (1.2, 1, 1, 1), [])), 2)


if __name__ == "__main__":
    unittest.main()
