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
        self.assertTrue(any(s["text"] == "Ethernet Cable" for s in r["page"].shapes))

    def test_the_footer_is_always_there_and_missing_values_print_tbc(self):
        texts = [s["text"] for s in build(spec())["page"].shapes]
        self.assertIn("Project:  P", texts)
        self.assertIn("Client:  TBC", texts)

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

    def test_the_arrow_flag_reaches_the_xml_for_hardwired_lines_only(self):
        s = spec(lines=[{"from": "a", "to": "b", "cable": "hardwired"}])
        r = build(s)
        with zipfile.ZipFile(r["out"]) as z:
            self.assertIn("EndArrow", z.read("visio/pages/page1.xml").decode())     # the sample line (the footer legend sample too)
        drawn = [x for x in r["page"].shapes if x["role"] == "line" and x["key"] == "a->b"]
        self.assertEqual([x["arrow"] for x in drawn], [True])
        r = build(spec())                                                          # ethernet only: no arrowhead anywhere
        with zipfile.ZipFile(r["out"]) as z:
            self.assertNotIn("EndArrow", z.read("visio/pages/page1.xml").decode())
        self.assertFalse(any(x["arrow"] for x in r["page"].shapes if x["role"] == "line"))

    def test_a_labelled_line_gets_a_small_text_shape(self):
        s = spec()
        s["lines"][0]["label"] = "OPC UA"
        labels = [x for x in build(s)["page"].shapes if x["text"] == "OPC UA"]
        self.assertEqual(len(labels), 1)
        self.assertEqual(labels[0]["fill"], "#FFFFFF")
        self.assertFalse([x for x in build(spec())["page"].shapes if x["text"] == "OPC UA"])

    def test_explicit_points_bypass_routing(self):
        s = spec()
        s["lines"][0]["points"] = [[2, 1.2], [2, 3], [6, 3], [6, 1.6]]
        pts = next(x["pts"] for x in build(s)["page"].shapes if x["key"] == "a->b")
        self.assertEqual(len(pts), 4)
        self.assertAlmostEqual(pts[0][0], B.MARGIN + 2)
        self.assertAlmostEqual(pts[1][1], B.TOP - 3)
        s["lines"][0]["points"] = [[1, 1]]                                           # too short: ignored with a warning
        r = build(s)
        self.assertTrue(any("points must be" in w for w in r["warnings"]))

    def test_a_modbus_line_without_a_label_warns_and_with_one_does_not(self):
        s = spec(lines=[{"from": "a", "to": "b", "cable": "modbus"}])
        self.assertTrue(any("RTU or TCP" in w for w in build(s)["warnings"]))
        s["lines"][0]["label"] = "Modbus TCP"
        self.assertFalse(any("RTU or TCP" in w for w in build(s)["warnings"]))
        self.assertFalse(any("RTU or TCP" in w for w in build(spec())["warnings"]))     # an ethernet line needs no label

    def test_every_drawing_carries_the_plugin_version_stamp(self):
        import json
        with open(os.path.join(HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            version = json.load(fh)["version"]
        r = build(spec())
        stamps = [s for s in r["page"].shapes if s["text"].startswith("RPS Architecture plugin v")]
        self.assertEqual(len(stamps), 1)
        self.assertEqual(stamps[0]["text"], "RPS Architecture plugin v%s | spec v1" % version)
        self.assertLess(stamps[0]["y"] + stamps[0]["h"], 0.30 + 1e-9)               # below the footer frame
        self.assertAlmostEqual(stamps[0]["x"] + stamps[0]["w"], B.footer.X1)         # right-aligned to the footer's right edge
        self.assertEqual(stamps[0]["halign"], 2)
        with zipfile.ZipFile(r["out"]) as z:
            self.assertIn("RPS Architecture plugin v%s" % version, z.read("docProps/core.xml").decode())
        self.assertEqual(B.plugin_version(), version)

    def test_route_is_square_or_straight(self):
        a, b = (1, 5, 1, 0.5), (6, 1, 1, 0.5)
        pts = B.route(a, b, [])
        self.assertTrue(all(p[0] == q[0] or p[1] == q[1] for p, q in zip(pts, pts[1:])))
        self.assertEqual(len(B.route((1, 5, 1, 1), (1.2, 1, 1, 1), [])), 2)


class EllipseTests(unittest.TestCase):
    """The v1 kind "ellipse": the closed fibre-ring outline, drawn as a closed polygon of 72 points."""

    def ring_spec(self, **shape):
        e = {"id": "ring", "kind": "ellipse", "label": "Fiber Optic Ring", "x": 2, "y": 3, "w": 6, "h": 1.2}
        e.update(shape)
        return spec(shapes=spec()["shapes"] + [e], lines=[])

    def polygon(self, r):
        return next(s for s in r["page"].shapes if s["kind"] == "polygon")

    def test_the_ellipse_is_one_closed_polygon_of_72_points_in_the_fibre_style(self):
        r = build(self.ring_spec())
        p = self.polygon(r)
        self.assertEqual(len(p["pts"]), 73)
        self.assertEqual(p["pts"][0], p["pts"][-1])                           # closed: first point equals last
        fibre = Cables().style("fibre")
        self.assertEqual((p["line"], p["pattern"]), (fibre["color"], 2))     # green, dashed: from the cable table
        self.assertEqual(p["fill"], "#E5F7E8")
        self.assertEqual((p["text"], p["bold"], p["size"]), ("Fiber Optic Ring", True, 8))
        self.assertAlmostEqual(p["w"], 6, 2)
        self.assertAlmostEqual(p["h"], 1.2, 2)

    def test_every_point_lies_on_the_ellipse(self):
        p = self.polygon(build(self.ring_spec()))
        cx, cy, a, b = p["x"] + p["w"] / 2, p["y"] + p["h"] / 2, p["w"] / 2, p["h"] / 2
        for x, y in p["pts"]:
            self.assertAlmostEqual(((x - cx) / a) ** 2 + ((y - cy) / b) ** 2, 1.0, 6)

    def test_the_polygon_is_written_to_the_vsdx_as_a_closed_filled_path(self):
        r = build(self.ring_spec())
        with zipfile.ZipFile(r["out"]) as z:
            xml = z.read("visio/pages/page1.xml").decode()
        i = xml.index("#E5F7E8")
        geometry = xml[i:xml.index("</Shape>", i)]
        self.assertEqual(geometry.count("<Row T='LineTo'"), 72)               # 71 corners and the closing segment
        self.assertIn("<Cell N='NoFill' V='0'/>", geometry)

    def test_a_named_cable_changes_the_outline_style_and_an_unknown_one_is_an_error(self):
        p = self.polygon(build(self.ring_spec(cable="ethernet")))
        self.assertEqual(p["line"], Cables().style("ethernet")["color"])
        with self.assertRaises(B.BuildError):
            build(self.ring_spec(cable="coax"))

    def test_an_ellipse_needs_its_size_and_a_custom_fill_is_honoured(self):
        s = self.ring_spec()
        del s["shapes"][-1]["w"]
        with self.assertRaises(B.BuildError):
            build(s)
        self.assertEqual(self.polygon(build(self.ring_spec(fill="#FFEEDD")))["fill"], "#FFEEDD")

    def test_a_line_may_end_on_the_ellipse_without_a_warning(self):
        s = self.ring_spec()
        s["lines"] = [{"from": "a", "to": "ring", "cable": "fibre", "points": [[1.5, 2.0], [1.5, 3.4], [4.0, 3.4]]}]
        self.assertEqual([w for w in build(s)["warnings"] if "passes through" in w], [])

    def test_a_polygon_needs_three_points_and_is_closed_when_given_open(self):
        page = B.Page()
        with self.assertRaises(ValueError):
            page.polygon([(0, 0), (1, 1)])
        page.polygon([(0, 0), (2, 0), (1, 1)])
        self.assertEqual(page.shapes[-1]["pts"][0], page.shapes[-1]["pts"][-1])


if __name__ == "__main__":
    unittest.main()
