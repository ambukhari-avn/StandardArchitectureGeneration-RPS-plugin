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
         "shapes": [{"id": "a", "label": "A", "x": 1, "y": 1, "component": "industrial_switch"}, {"id": "b", "label": "B", "x": 5, "y": 1, "component": "industrial_switch"}],
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
        self.assertTrue(any(s["text"] == "Ethernet" for s in r["page"].shapes))

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

    def test_missing_picture_falls_back_to_a_generic_icon_never_a_box(self):
        s = spec()
        s["shapes"][0]["image"] = "nope.png"
        del s["shapes"][0]["component"]
        r = build(s)
        self.assertTrue(any("picture not usable" in w for w in r["warnings"]))
        self.assertTrue(any("generic device icon" in w for w in r["warnings"]))
        self.assertEqual(r["shapes"], 2)
        self.assertEqual([x for x in r["page"].shapes if x["role"] == "icon" and x["kind"] == "rect" and x["text"] in ("A", "B")], [])   # no box with text
        self.assertTrue(any((x["key"] or "").startswith("generic:") for x in r["page"].shapes))

    def test_another_raster_format_is_converted_when_pillow_is_there(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        d = tempfile.mkdtemp()
        Image.new("RGB", (200, 200), "red").save(os.path.join(d, "p.webp"))
        s = spec()
        del s["shapes"][0]["component"]
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
        s["shapes"][0].update(label="x" * 200, w=0.5, h=0.9)
        self.assertTrue(any("may not fit" in w for w in build(s)["warnings"]))

    def test_route_is_square_or_straight(self):
        a, b = (1, 5, 1, 0.5), (6, 1, 1, 0.5)
        pts = B.route(a, b, [])
        self.assertTrue(all(p[0] == q[0] or p[1] == q[1] for p, q in zip(pts, pts[1:])))
        self.assertEqual(len(B.route((1, 5, 1, 1), (1.2, 1, 1, 1), [])), 2)


def ring_spec(n_up=2, n_down=2, **kw):
    shapes = [{"id": "u%d" % i, "label": "U%d" % i, "x": 2 + i * 3, "y": 1, "w": 1.5, "h": 0.8, "component": "industrial_switch", "scope": "other"} for i in range(n_up)]
    shapes += [{"id": "d%d" % i, "label": "D%d" % i, "x": 2 + i * 3, "y": 4, "w": 1.5, "h": 0.8, "component": "industrial_switch", "scope": "other"} for i in range(n_down)]
    nodes = [s["id"] for s in shapes]
    s = {"project": dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z"), "shapes": shapes,
         "rings": [{"id": "fo", "nodes": nodes}]}
    s.update(kw)
    return s


class RingTests(unittest.TestCase):
    def ring(self, r):
        return [s for s in r["page"].shapes if s["kind"] == "ellipse"]

    def test_ring_is_one_dashed_light_green_ellipse_with_its_label(self):
        r = build(ring_spec())
        self.assertEqual(r["warnings"], [])
        (e,) = self.ring(r)
        fibre = Cables().get("fibre")
        self.assertEqual((e["line"], e["pattern"], e["fill"]), (fibre["color"], 2, B.RING_FILL))
        self.assertEqual(e["text"], "Fiber Optic Ring")
        self.assertGreater(e["w"], e["h"] * 3)                       # an elongated ellipse, as in the approved illustration

    def test_one_link_per_element_any_number_above_and_below_touching_the_ellipse(self):
        for up, down in ((2, 2), (3, 1), (4, 0), (1, 5)):
            r = build(ring_spec(up, down))
            (e,) = self.ring(r)
            links = [s for s in r["page"].shapes if s["role"] == "line" and (s["key"] or "").startswith("ring:fo:")]
            self.assertEqual(len(links), up + down)
            fibre = Cables().get("fibre")
            self.assertTrue(all((k["line"], k["pattern"]) == (fibre["color"], 2) for k in links))   # node links are green dashed too
            cy = e["y"] + e["h"] / 2
            for k in links:
                (x1, y1), (x2, y2) = k["pts"]
                self.assertAlmostEqual(x1, x2)                        # straight, vertical
                a, b = e["w"] / 2, e["h"] / 2
                self.assertAlmostEqual(((x2 - (e["x"] + a)) / a) ** 2 + ((y2 - cy) / b) ** 2, 1.0, 3)   # ends on the ellipse
                self.assertEqual(y1 > cy, y2 > cy)                    # node and its ellipse end are on the same side

    def test_nodes_above_join_the_top_and_nodes_below_join_the_bottom(self):
        r = build(ring_spec(2, 2))
        (e,) = self.ring(r)
        cy = e["y"] + e["h"] / 2
        by_key = {s["key"]: s for s in r["page"].shapes if s["role"] == "line"}
        self.assertTrue(all(by_key["ring:fo:u%d" % i]["pts"][1][1] > cy for i in range(2)))   # 'u' nodes sit higher on the sheet: top of the ring
        self.assertTrue(all(by_key["ring:fo:d%d" % i]["pts"][1][1] < cy for i in range(2)))   # 'd' nodes sit lower: bottom of the ring

    def test_ring_with_its_own_box_and_label(self):
        r = build(ring_spec(rings=[{"id": "a", "label": "FO ring A", "x": 1, "y": 2.2, "w": 9, "h": 1.0, "nodes": ["u0", "d0", "d1"]}]))
        (e,) = self.ring(r)
        self.assertEqual((e["text"], round(e["w"], 3), round(e["h"], 3)), ("FO ring A", 9.0, 1.0))
        self.assertIn("Fiber optic", [s["text"] for s in r["page"].shapes])   # the fibre cable is in the footer legend

    def test_single_row_puts_the_ring_below_it(self):
        r = build(ring_spec(3, 0))
        (e,) = self.ring(r)
        row_bottom = min(s["y"] for s in r["page"].shapes if (s["key"] or "").endswith(":scope"))
        self.assertLess(e["y"] + e["h"], row_bottom)

    def test_ellipse_is_written_as_a_visio_ellipse(self):
        r = build(ring_spec())
        import zipfile
        with zipfile.ZipFile(r["out"]) as z:
            self.assertIn("T='Ellipse'", z.read("visio/pages/page1.xml").decode())

    def test_bad_rings_stop_the_build(self):
        for bad in ([{"nodes": ["u0"]}], [{"nodes": ["u0", "u1", "nope"]}], [{"nodes": ["u0", "u1", "u1"]}],
                    [{"nodes": ["u0", "u1"], "cable": "nope"}], [{"nodes": ["u0", "u1"], "x": 1}]):
            with self.assertRaises(B.BuildError):
                build(ring_spec(2, 2, rings=bad))


def layer_spec(layers, per, **kw):
    proj = dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")
    shapes = [{"id": "%s%d" % (L, i), "label": "%s %d" % (L, i + 1), "layer": L, "scope": "avanceon", "component": "industrial_switch"} for L in layers for i in range(per[L])]
    s = {"project": proj, "layers": layers, "shapes": shapes}
    s.update(kw)
    return s


class LayerTests(unittest.TestCase):
    def panels(self, r):
        return sorted((s for s in r["page"].shapes if (s["key"] or "").startswith("layer:")), key=lambda s: -s["y"])

    def test_any_number_of_layers_fills_the_whole_drawing_area_in_standard_order(self):
        every = ["enterprise", "dmz", "operations", "scada", "control", "field"]
        for layers in (["field", "control"], ["field", "scada", "control"], every[1:], every[::-1]):
            r = build(layer_spec(layers, {L: 2 for L in layers}))
            self.assertEqual(r["warnings"], [])
            ps = self.panels(r)
            self.assertEqual([p["key"][6:] for p in ps], [L for L in every if L in layers])     # standard top-to-bottom order
            self.assertAlmostEqual(ps[0]["y"] + ps[0]["h"], B.TOP, 3)                            # starts at the top of the drawing area
            self.assertAlmostEqual(ps[-1]["y"], B.BOTTOM, 3)                                     # ends at the bottom: nothing left empty
            self.assertEqual(len({round(p["h"], 4) for p in ps}), 1)                              # equal bands
            self.assertTrue(all(abs(p["w"] - B.AREA_W) < 1e-6 for p in ps))

    def test_two_layers_are_tall_six_are_shorter(self):
        two = self.panels(build(layer_spec(["control", "field"], {"control": 2, "field": 2})))
        six = self.panels(build(layer_spec(["enterprise", "dmz", "operations", "scada", "control", "field"], {k: 1 for k in
                                                                                                          ["enterprise", "dmz", "operations", "scada", "control", "field"]})))
        self.assertGreater(two[0]["h"], 2 * six[0]["h"])

    def test_shapes_are_spread_evenly_and_centred_in_their_layer(self):
        r = build(layer_spec(["scada", "field"], {"scada": 3, "field": 4}))
        ps = {p["key"][6:]: p for p in self.panels(r)}
        tiles = sorted((s for s in r["page"].shapes if (s["key"] or "").endswith(":scope")), key=lambda s: (-s["y"], s["x"]))
        for L, n in (("scada", 3), ("field", 4)):
            p = ps[L]
            boxes = [t for t in tiles if p["y"] <= t["y"] and t["y"] + t["h"] <= p["y"] + p["h"] + 1e-6]
            self.assertEqual(len(boxes), n)
            gaps = [boxes[0]["x"] - (p["x"] + B.BAND_W)] + [b["x"] - (a["x"] + a["w"]) for a, b in zip(boxes, boxes[1:])] \
                + [p["x"] + p["w"] - (boxes[-1]["x"] + boxes[-1]["w"])]
            self.assertLess(max(gaps[1:-1]) - min(gaps[1:-1]) if n > 2 else 0, 1e-6)           # equal gaps between shapes
            for b in boxes:
                self.assertAlmostEqual(b["y"] + b["h"] / 2, p["y"] + p["h"] / 2, 3)             # vertically centred
                self.assertGreaterEqual(b["x"], p["x"] + B.BAND_W)

    def test_band_is_dark_blue_with_white_rotated_name_and_scope_boxes_are_outlined(self):
        r = build(layer_spec(["scada"], {"scada": 1}))
        band = [s for s in r["page"].shapes if (s["key"] or "").startswith("layer-band:")][0]
        name = [s for s in r["page"].shapes if (s["key"] or "").startswith("layer-name:")][0]
        self.assertEqual((band["fill"], name["text"], name["text_angle"]), (B.BAND_FILL, "SCADA Layer", 90))
        box = [s for s in r["page"].shapes if (s["key"] or "").endswith(":scope")][0]
        self.assertEqual((box["fill"].upper(), box["line"]), ("#CFE8F7", B.SCOPE_LINE))

    def test_vsdx_has_rounded_panels_and_rotated_names(self):
        r = build(layer_spec(["scada", "field"], {"scada": 1, "field": 1}))
        import zipfile
        x = zipfile.ZipFile(r["out"]).read("visio/pages/page1.xml").decode()
        self.assertIn("N='Rounding'", x)
        self.assertIn("N='TxtAngle'", x)

    def test_bad_layer_use_stops_the_build(self):
        with self.assertRaises(B.BuildError):
            build(dict(layer_spec(["scada"], {"scada": 1}), layers=["scada", "nope"]))
        with self.assertRaises(B.BuildError):
            build(dict(layer_spec(["scada"], {"scada": 1}), layers=["scada", "scada"]))
        bad = layer_spec(["scada"], {"scada": 1})
        bad["shapes"][0]["layer"] = "field"                                                      # not in the file's layers list
        with self.assertRaises(B.BuildError):
            build(bad)
        nolayers = layer_spec(["scada"], {"scada": 1})
        del nolayers["layers"]
        with self.assertRaises(B.BuildError):
            build(nolayers)

    def test_shapes_without_layers_are_unchanged(self):
        r = build(spec())
        self.assertEqual([s for s in r["page"].shapes if (s["key"] or "").startswith("layer")], [])


class PictureTests(unittest.TestCase):
    """Every device is a picture with its caption, on a transparent background; never a box."""

    def device(self, **kw):
        d = {"id": "d", "label": "Pressure transmitter", "x": 2, "y": 2, "image": os.path.join(HERE, "..", "samples", "pictures", "pressure_transmitter.png")}
        d.update(kw)
        return d

    def spec(self, *shapes):
        return {"project": dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z"), "shapes": list(shapes)}

    def test_device_is_a_picture_with_a_bold_caption_and_no_box(self):
        r = build(self.spec(self.device()))
        self.assertEqual(r["warnings"], [])
        shapes = r["page"].shapes
        self.assertTrue(any(s["kind"] == "image" and (s["key"] or "").startswith("image:") for s in shapes))
        cap = [s for s in shapes if s["text"] == "Pressure transmitter"]
        self.assertEqual([(c["role"], c["bold"]) for c in cap], [("text", True)])
        self.assertEqual([s for s in shapes if s["role"] == "icon" and s["kind"] == "rect" and s["text"] == "Pressure transmitter"], [])

    def test_second_caption_line_is_blue(self):
        for kw in ({"label": "SCADA Server", "sublabel": "(Primary)"}, {"label": "SCADA Server\n(Primary)"}):
            r = build(self.spec(self.device(**kw)))
            sub = [s for s in r["page"].shapes if s["text"] == "(Primary)"]
            self.assertEqual([s["color"] for s in sub], ["#1F4E9E"])
            self.assertIn("SCADA Server", [s["text"] for s in r["page"].shapes])

    def test_device_without_a_picture_gets_the_generic_icon_and_a_warning(self):
        r = build(self.spec({"id": "x", "label": "Mystery device", "x": 1, "y": 1}))
        self.assertTrue(any("generic device icon" in w for w in r["warnings"]))
        self.assertTrue(any((s["key"] or "").startswith("generic:") and s["kind"] == "image" for s in r["page"].shapes))
        self.assertIn("Mystery device", [s["text"] for s in r["page"].shapes])

    def test_a_short_device_cell_is_raised_so_the_picture_and_caption_fit(self):
        r = build(self.spec(self.device(h=0.2)))
        self.assertTrue(any("raised" in w for w in r["warnings"]))

    def test_scope_colour_is_a_tile_behind_the_picture(self):
        r = build(self.spec(self.device(scope="other")))
        tile = [s for s in r["page"].shapes if (s["key"] or "").endswith(":scope")]
        self.assertEqual([(t["fill"].upper(), t["line"]) for t in tile], [("#D5EFD3", B.SCOPE_LINE)])
        self.assertLess([s["id"] for s in r["page"].shapes].index(tile[0]["id"]),
                        [s["id"] for s in r["page"].shapes if s["kind"] == "image" and (s["key"] or "").startswith("image:")][0])   # tile is behind

    def test_group_has_a_dashed_rounded_container_and_a_blue_title_pill(self):
        r = build(self.spec({"id": "g", "kind": "group", "label": "Redundant PLC System", "x": 1, "y": 1, "w": 6, "h": 3}, self.device()))
        box = [s for s in r["page"].shapes if (s["key"] or "") == "shape:g"][0]
        pill = [s for s in r["page"].shapes if s["text"] == "Redundant PLC System"][0]
        self.assertEqual((box["pattern"], box["rounding"] > 0, pill["fill"], pill["color"]), (2, True, B.PILL_BLUE, "#FFFFFF"))
        self.assertGreater(pill["y"] + pill["h"], box["y"] + box["h"])           # the pill straddles the container's top edge
        with self.assertRaises(B.BuildError):
            build(self.spec({"id": "g", "kind": "group", "label": "no size", "x": 1, "y": 1}))

    def test_pill_label_sits_on_top_of_a_line_without_a_crossing_warning(self):
        r = build(self.spec(self.device(id="a", x=1, y=1), self.device(id="b", x=9, y=1),
                            {"id": "p", "kind": "pill", "label": "Field Instruments & Devices", "x": 3.5, "y": 1.4}) |
                  {"lines": [{"from": "a", "to": "b", "cable": "hardwired"}]})
        self.assertFalse(any("passes through" in w for w in r["warnings"]))
        self.assertIn("Field Instruments & Devices", [s["text"] for s in r["page"].shapes])


class BackgroundTests(unittest.TestCase):
    def make(self, bg=(255, 255, 255)):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (300, 200), bg)
        d = ImageDraw.Draw(im)
        d.rectangle([60, 40, 240, 160], fill=(40, 60, 120))
        d.rectangle([120, 80, 180, 120], fill=bg)                       # background-coloured detail INSIDE the device
        p = os.path.join(tempfile.mkdtemp(), "w.png")
        im.save(p)
        return p

    def test_white_background_becomes_transparent_and_inner_white_is_kept(self):
        import pictures
        from PIL import Image
        out, note = pictures.prepare(self.make())
        self.assertIsNone(note)
        im = Image.open(out).convert("RGBA")
        self.assertEqual(im.getpixel((0, 0))[3], 0)                                     # corner transparent
        self.assertEqual(im.getpixel((im.width // 2, im.height // 2)), (255, 255, 255, 255))   # inner white kept
        self.assertLess(im.width, 300)                                                  # trimmed to the device

    def test_light_grey_background_too(self):
        import pictures
        from PIL import Image
        out, _ = pictures.prepare(self.make((238, 238, 238)))
        self.assertEqual(Image.open(out).convert("RGBA").getpixel((0, 0))[3], 0)

    def test_without_pillow_the_standard_library_route_gives_the_same_result(self):
        import pictures
        from PIL import Image
        path = self.make()
        w, h, px = pictures._read_png(path)
        res = pictures._clean(w, h, px)
        self.assertIsNotNone(res)
        self.assertEqual(res[2][0][0][3], 0)
        self.assertEqual(res[2][res[1] // 2][res[0] // 2], (255, 255, 255, 255))

    def test_already_transparent_picture_is_only_trimmed(self):
        import pictures
        from PIL import Image
        im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        im.paste((200, 0, 0, 255), (30, 30, 70, 70))
        p = os.path.join(tempfile.mkdtemp(), "t.png")
        im.save(p)
        out, note = pictures.prepare(p)
        r = Image.open(out)
        self.assertIsNone(note)
        self.assertLess(r.width, 100)
        self.assertEqual(r.convert("RGBA").getpixel((r.width // 2, r.height // 2)), (200, 0, 0, 255))

    def test_a_picture_that_would_vanish_is_used_as_it_is_with_a_note(self):
        import pictures
        from PIL import Image
        p = os.path.join(tempfile.mkdtemp(), "w.png")
        Image.new("RGB", (80, 80), (255, 255, 255)).save(p)
        out, note = pictures.prepare(p)
        self.assertEqual(out, p)
        self.assertIn("used as it is", note)

    def test_unreadable_file_never_stops_the_build(self):
        import pictures
        p = os.path.join(tempfile.mkdtemp(), "bad.png")
        with open(p, "wb") as fh:
            fh.write(b"nope")
        out, note = pictures.prepare(p)
        self.assertEqual(out, p)
        self.assertTrue(note)

    def test_every_picture_in_a_build_goes_through_the_cleaner(self):
        s = {"project": dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z"),
             "shapes": [{"id": "d", "label": "D", "x": 2, "y": 2, "image": self.make()}]}
        r = build(s)
        img = [x for x in r["page"].shapes if (x["key"] or "").startswith("image:")][0]
        self.assertIn("arch_pictures", img["image"])                                    # the cleaned copy is what is drawn


if __name__ == "__main__":
    unittest.main()
