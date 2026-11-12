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
        s["lines"][0]["via"] = [[3.5, 1.5]]                                  # a hand-routed cable that runs through C
        self.assertTrue(any("passes through shape 'c'" in w for w in build(s)["warnings"]))

    def test_an_automatic_cable_goes_round_a_shape_in_its_way(self):
        s = spec()
        s["shapes"].append({"id": "c", "label": "C", "x": 3, "y": 1})
        self.assertFalse(any("passes through" in w for w in build(s)["warnings"]))

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
        row_bottom = min(s["y"] for s in r["page"].shapes if s["kind"] == "image" and (s["key"] or "").startswith("component:"))
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

    def blocks(self, r):
        return [s for s in r["page"].shapes if (s["key"] or "").startswith("scope-block:")]

    def pictures(self, r, p):
        return sorted((s for s in r["page"].shapes if s["kind"] == "image" and p["y"] <= s["y"] <= p["y"] + p["h"]), key=lambda s: s["x"])

    def test_shapes_are_spread_evenly_and_centred_in_their_layer(self):
        r = build(layer_spec(["scada", "field"], {"scada": 3, "field": 4}))
        ps = {p["key"][6:]: p for p in self.panels(r)}
        for L, n in (("scada", 3), ("field", 4)):
            p = ps[L]
            pics = self.pictures(r, p)
            self.assertEqual(len(pics), n)
            centres = [s["x"] + s["w"] / 2 for s in pics]
            steps = [b - a for a, b in zip(centres, centres[1:])]
            self.assertLess(max(steps) - min(steps), 1e-6)                                       # equal spacing
            self.assertGreater(centres[0], p["x"] + B.BAND_W)
            self.assertLess(centres[-1], p["x"] + p["w"])

    def test_layers_are_white_rows_with_a_blue_label_column_and_no_scope_blocks(self):
        spec = layer_spec(["scada", "control"], {"scada": 2, "control": 1})
        spec["shapes"][0]["scope"] = "other"
        r = build(spec)
        self.assertFalse(any((s["key"] or "").startswith(("scope-block:", "layer-band:")) for s in r["page"].shapes))
        self.assertFalse(any((s["key"] or "").endswith(":scope") for s in r["page"].shapes))
        row = [s for s in r["page"].shapes if (s["key"] or "") == "layer:scada"][0]
        self.assertEqual((row["fill"].upper(), row["line"], row["rounding"]), ("#FFFFFF", B.BLUE, 0))
        name = [s for s in r["page"].shapes if (s["key"] or "") == "layer-name:scada"][0]
        desc = [s for s in r["page"].shapes if (s["key"] or "") == "layer-desc:scada"][0]
        self.assertEqual((name["text"], name["color"], name["bold"]), ("LEVEL 2\nSCADA", B.BLUE, True))
        self.assertEqual((desc["text"], desc["color"]), ("Supervisory Monitoring & Operations", "#000000"))
        self.assertLess(name["x"] + name["w"], row["x"] + B.BAND_W + 0.01)                        # labels stay in the left column
        pics = [s for s in r["page"].shapes if s["kind"] == "image" and (s["key"] or "").startswith("component:")]
        self.assertTrue(all(p["x"] > row["x"] + B.BAND_W for p in pics))                          # devices start right of the column

    def test_layers_touch_each_other_and_fill_the_area(self):
        r = build(layer_spec(["scada", "control", "field"], {"scada": 1, "control": 1, "field": 1}))
        ps = self.panels(r)
        for a, b in zip(ps, ps[1:]):
            self.assertAlmostEqual(a["y"], b["y"] + b["h"], 3)

    def test_title_and_frame(self):
        r = build(layer_spec(["scada"], {"scada": 1}, title="plc & scada system architecture"))
        title = [s for s in r["page"].shapes if s["key"] == "title"][0]
        frame = [s for s in r["page"].shapes if s["key"] == "frame"][0]
        self.assertEqual((title["text"], title["color"], title["bold"]), ("PLC & SCADA SYSTEM ARCHITECTURE", B.BLUE, True))
        self.assertEqual((frame["line"], frame["fill"]), (B.BLUE, None))
        self.assertGreater(title["y"], B.TOP)                                                      # above the layers
        self.assertLess(title["y"] + title["h"], frame["y"] + frame["h"])                           # inside the frame
        r2 = build(layer_spec(["scada"], {"scada": 1}))
        self.assertEqual([s for s in r2["page"].shapes if s["key"] == "title"][0]["text"], "ARCHITECTURE")

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

    def test_scope_alone_adds_no_tile_behind_a_picture(self):
        r = build(self.spec(self.device(scope="other")))
        self.assertFalse(any((s["key"] or "").endswith(":scope") for s in r["page"].shapes))

    def test_group_is_a_dashed_rounded_blue_box_with_a_blue_bold_title_inside(self):
        r = build(self.spec({"id": "g", "kind": "group", "label": "MAIN PLC PANEL", "x": 1, "y": 1, "w": 6, "h": 3}, self.device()))
        box = [s for s in r["page"].shapes if (s["key"] or "") == "shape:g"][0]
        title = [s for s in r["page"].shapes if s["text"] == "MAIN PLC PANEL"][0]
        self.assertEqual((box["pattern"], box["rounding"] > 0, box["line"]), (2, True, B.BLUE))
        self.assertEqual((title["color"], title["bold"], title["fill"]), (B.BLUE, True, None))      # plain text, no pill
        self.assertLess(title["y"] + title["h"], box["y"] + box["h"] + 1e-6)                        # inside the box, at the top
        self.assertGreater(title["y"], box["y"] + box["h"] / 2)
        with self.assertRaises(B.BuildError):
            build(self.spec({"id": "g", "kind": "group", "label": "no size", "x": 1, "y": 1}))

    def test_pill_labels_are_not_drawn_but_old_files_still_build(self):
        r = build(self.spec(self.device(id="a", x=1, y=1), self.device(id="b", x=9, y=1),
                            {"id": "p", "kind": "pill", "label": "Field Instruments & Devices", "x": 3.5, "y": 1.4}) |
                  {"lines": [{"from": "a", "to": "b", "cable": "hardwired"}]})
        self.assertNotIn("Field Instruments & Devices", [s["text"] for s in r["page"].shapes])
        self.assertFalse(any("passes through" in w for w in r["warnings"]))


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

    def test_a_thin_frame_and_a_soft_drop_shadow_are_removed_too(self):
        import pictures
        from PIL import Image, ImageDraw, ImageFilter
        im = Image.new("RGB", (300, 220), (255, 255, 255))
        sh = Image.new("L", (300, 220), 0)
        ImageDraw.Draw(sh).rectangle([70, 60, 250, 175], fill=130)
        im.paste((110, 110, 110), (0, 0), sh.filter(ImageFilter.GaussianBlur(7)))
        ImageDraw.Draw(im).rectangle([60, 40, 240, 160], fill=(40, 60, 120))
        ImageDraw.Draw(im).rectangle([0, 0, 299, 219], outline=(205, 205, 205))        # 1 px frame, as many web photos have
        p = os.path.join(tempfile.mkdtemp(), "f.png")
        im.save(p)
        out, note = pictures.prepare(p)
        self.assertIsNone(note)
        res = Image.open(out).convert("RGBA")
        self.assertLess(res.width, 215)                                                  # frame gone: cropped to the device (and its faint edge)
        light = sum(1 for x in range(res.width) for y in range(res.height)
                    if res.getpixel((x, y))[3] > 100 and min(res.getpixel((x, y))[:3]) > 150)
        self.assertLess(light, 0.02 * res.width * res.height)                           # no light shadow or frame left opaque

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


class StaysA3Tests(unittest.TestCase):
    """Whatever the file asks for, the page is A3 and everything is inside it (Visio would otherwise grow the page)."""
    proj = dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")

    def dev(self, i, **kw):
        d = {"id": i, "label": i, "component": "industrial_switch", "x": 2, "y": 2}
        d.update(kw)
        return d

    def assert_everything_on_the_sheet(self, r):
        from vsdx_writer import A3_H, A3_W
        for s in r["page"].shapes:
            xs, ys = [s["x"], s["x"] + s["w"]], [s["y"], s["y"] + s["h"]]
            if s["pts"]:
                xs += [p[0] for p in s["pts"]]
                ys += [p[1] for p in s["pts"]]
            self.assertGreaterEqual(min(xs), -1e-6, s["key"])
            self.assertLessEqual(max(xs), A3_W + 1e-6, s["key"])
            self.assertGreaterEqual(min(ys), -1e-6, s["key"])
            self.assertLessEqual(max(ys), A3_H + 1e-6, s["key"])

    def test_the_saved_page_is_a3_and_never_resizes_itself(self):
        import re
        r = build({"project": self.proj, "shapes": [self.dev("a")]})
        with zipfile.ZipFile(r["out"]) as z:
            p = z.read("visio/pages/pages.xml").decode()
        self.assertAlmostEqual(float(re.search(r"N='PageWidth' V='([\d.]+)'", p).group(1)), 420 / 25.4, 3)
        self.assertAlmostEqual(float(re.search(r"N='PageHeight' V='([\d.]+)'", p).group(1)), 297 / 25.4, 3)
        self.assertEqual(re.search(r"N='DrawingResizeType' V='(\d+)'", p).group(1), "2")      # 2 = never resize

    def test_far_out_via_points_are_pulled_inside_with_a_warning(self):
        s = {"project": self.proj, "shapes": [self.dev("a"), self.dev("b", x=8)],
             "lines": [{"from": "a", "to": "b", "cable": "ethernet", "via": [[99, -40], [-30, 77]]}]}
        r = build(s)
        self.assertTrue(any("via point" in w and "moved inside" in w for w in r["warnings"]))
        self.assert_everything_on_the_sheet(r)

    def test_a_huge_or_far_ring_box_is_pulled_inside(self):
        s = {"project": self.proj, "shapes": [self.dev("a"), self.dev("b", x=8), self.dev("c", x=4, y=5)],
             "rings": [{"id": "r", "nodes": ["a", "b", "c"], "x": 20, "y": -9, "w": 60, "h": 40}]}
        r = build(s)
        self.assertTrue(any("ring ellipse did not fit" in w for w in r["warnings"]))
        self.assert_everything_on_the_sheet(r)

    def test_a_ring_spanning_the_whole_width_does_not_stick_out(self):
        shapes = [self.dev("n%d" % i, x=0.2 + i * 2.5, y=3) for i in range(7)]
        r = build({"project": self.proj, "shapes": shapes, "rings": [{"id": "r", "nodes": [s["id"] for s in shapes]}]})
        self.assert_everything_on_the_sheet(r)
        ell = [s for s in r["page"].shapes if s["kind"] == "ellipse"][0]
        self.assertLessEqual(ell["x"] + ell["w"], B.MARGIN + B.AREA_W + 1e-6)

    def test_safety_net_catches_anything_still_outside_and_keeps_clear_of_the_footer(self):
        from vsdx_writer import A3_H, A3_W, Page
        import footer
        pg = Page()
        n = len(pg.shapes)
        pg.rect("icon", 30, 30, 2, 2)                              # far off the sheet
        pg.rect("icon", 5, 0.5, 2, 0.5)                             # on top of the footer
        pg.line([(1, 1), (50, 50)], "#000000")
        warns = []
        moved = B.keep_on_page(pg, n, warns)
        self.assertEqual(moved, 3)
        self.assertEqual(len(warns), 3)
        for s in pg.shapes:
            self.assertLessEqual(s["x"] + s["w"], A3_W)
            self.assertLessEqual(s["y"] + s["h"], A3_H)
            self.assertGreaterEqual(s["y"], footer.TOP)

    def test_normal_drawings_are_not_touched_by_the_safety_net(self):
        r = build({"project": self.proj, "layers": ["scada", "field"],
                   "shapes": [self.dev("a", layer="scada"), self.dev("b", layer="field")]})
        self.assertFalse(any("outside the page" in w for w in r["warnings"]))


class CableRuleTests(unittest.TestCase):
    """Standard cabling rules: square, end to end, round devices, spread, hops; manual instructions win."""
    proj = dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")

    def dev(self, i, x, y, **kw):
        d = {"id": i, "label": i, "component": "industrial_switch", "x": x, "y": y}
        d.update(kw)
        return d

    def cables(self, r):
        return [s for s in r["page"].shapes if s["kind"] == "line" and "->" in (s["key"] or "")]

    def rects(self, r):
        return {(s["key"] or "")[len("component:"):]: None for s in r["page"].shapes}

    def test_every_segment_is_horizontal_or_vertical_and_ends_on_the_device_edges(self):
        import router
        shapes = [self.dev("a", 1, 1), self.dev("b", 7, 4), self.dev("c", 12, 1), self.dev("d", 3, 6)]
        lines = [{"from": "a", "to": "b", "cable": "ethernet"}, {"from": "b", "to": "c", "cable": "modbus"},
                 {"from": "a", "to": "d", "cable": "hardwired"}, {"from": "d", "to": "c", "cable": "ethernet"}]
        r = build({"project": self.proj, "shapes": shapes, "lines": lines})
        by = {s["id"]: B.rect_of(s) for s in B.prepare({"project": self.proj, "shapes": shapes, "lines": lines}, B.Components(), B.Cables(), ".")[0]}
        for c, cab in zip(lines, self.cables(r)):
            pts = cab["pts"]
            for p, q in zip(pts, pts[1:]):
                if abs(p[0] - q[0]) + abs(p[1] - q[1]) > 0.1:                                          # (hop arcs are made of tiny pieces)
                    self.assertTrue(abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6, (c, pts))  # no diagonal
            for end, other, first in ((c["from"], pts[1], pts[0]), (c["to"], pts[-2], pts[-1])):
                x, y, w, h = by[end]
                on_edge = (abs(first[0] - x) < 1e-6 or abs(first[0] - x - w) < 1e-6) and y - 1e-6 <= first[1] <= y + h + 1e-6 \
                    or (abs(first[1] - y) < 1e-6 or abs(first[1] - y - h) < 1e-6) and x - 1e-6 <= first[0] <= x + w + 1e-6
                self.assertTrue(on_edge, (end, first))                                                 # starts / ends on the device edge
            for sid, rect in by.items():
                if sid not in (c["from"], c["to"]):
                    self.assertFalse(B.crosses(pts, rect), (c, sid))                                   # never through another device

    def test_a_cable_goes_round_a_device_in_its_way(self):
        shapes = [self.dev("a", 1, 3), self.dev("m", 6, 3), self.dev("b", 11, 3)]
        r = build({"project": self.proj, "shapes": shapes, "lines": [{"from": "a", "to": "b", "cable": "ethernet"}]})
        (cab,) = self.cables(r)
        self.assertGreaterEqual(len(cab["pts"]), 4)                                                    # it bends round m
        self.assertFalse(any("passes through" in w for w in r["warnings"]))

    def test_aligned_devices_get_one_straight_cable(self):
        r = build({"project": self.proj, "shapes": [self.dev("a", 2, 2), self.dev("b", 9, 2)], "lines": [{"from": "a", "to": "b", "cable": "ethernet"}]})
        (cab,) = self.cables(r)
        self.assertEqual(len(cab["pts"]), 2)

    def test_cables_on_the_same_side_are_spread_apart(self):
        shapes = [self.dev("hub", 7, 1), self.dev("a", 2, 6), self.dev("b", 7, 6), self.dev("c", 12, 6)]
        lines = [{"from": "hub", "to": k, "cable": "ethernet"} for k in "abc"]
        r = build({"project": self.proj, "shapes": shapes, "lines": lines})
        starts = sorted(round(c["pts"][0][0], 3) for c in self.cables(r) if abs(c["pts"][0][1] - self.cables(r)[0]["pts"][0][1]) < 1e-6)
        self.assertEqual(len(starts), len(set(starts)))                                               # no two cables start at the same point
        self.assertGreater(len(set(round(c["pts"][0][0], 2) for c in self.cables(r))), 1)

    def test_a_crossing_is_drawn_as_a_hop_and_a_t_junction_is_not(self):
        import router
        flat = [[(0, 5), (10, 5)], [(5, 0), (5, 10)]]
        hopped = router.add_hops(flat)
        self.assertGreater(len(hopped[0]), 2)                                                          # the horizontal cable hops
        self.assertEqual(hopped[1], flat[1])                                                           # the vertical one is untouched
        self.assertGreater(max(p[1] for p in hopped[0]), 5.0)
        t_junction = router.add_hops([[(0, 5), (10, 5)], [(5, 0), (5, 5)]])
        self.assertEqual(t_junction[0], [(0, 5), (10, 5)])

    def test_manual_sides_win(self):
        shapes = [self.dev("a", 2, 2), self.dev("b", 9, 2)]
        r = build({"project": self.proj, "shapes": shapes, "lines": [{"from": "a", "to": "b", "cable": "ethernet", "from_side": "top", "to_side": "top"}]})
        (cab,) = self.cables(r)
        a = [s for s in B.prepare({"project": self.proj, "shapes": shapes}, B.Components(), B.Cables(), ".")[0] if s["id"] == "a"][0]
        x, y, w, h = B.rect_of(a)
        self.assertAlmostEqual(cab["pts"][0][1], y + h, 3)                                             # leaves the top of a
        self.assertGreater(cab["pts"][1][1], y + h)                                                    # and goes up first
        self.assertAlmostEqual(cab["pts"][-1][1], y + h, 3)                                            # arrives at the top of b

    def test_manual_via_points_are_followed_and_squared(self):
        shapes = [self.dev("a", 2, 2), self.dev("b", 9, 6)]
        r = build({"project": self.proj, "shapes": shapes, "lines": [{"from": "a", "to": "b", "cable": "ethernet", "via": [[5, 1.0], [7.5, 4.0]]}]})
        (cab,) = self.cables(r)
        for p, q in zip(cab["pts"], cab["pts"][1:]):
            self.assertTrue(abs(p[0] - q[0]) < 1e-6 or abs(p[1] - q[1]) < 1e-6)
        for vx, vy in ((5, 1.0), (7.5, 4.0)):
            self.assertTrue(any(abs(p[0] - (B.MARGIN + vx)) < 1e-6 and abs(p[1] - (B.TOP - vy)) < 1e-6 for p in cab["pts"]))   # passes through the given point

    def test_bad_side_name_is_ignored_with_a_warning(self):
        r = build({"project": self.proj, "shapes": [self.dev("a", 2, 2), self.dev("b", 9, 2)],
                   "lines": [{"from": "a", "to": "b", "cable": "ethernet", "from_side": "middle"}]})
        self.assertTrue(any("from_side" in w for w in r["warnings"]))

    def test_layered_drawing_keeps_cables_out_of_the_layer_band(self):
        shapes = [dict(self.dev("a", 0, 0), layer="scada", scope="avanceon"), dict(self.dev("b", 0, 0), layer="field", scope="avanceon")]
        for s in shapes:
            del s["x"], s["y"]
        r = build({"project": self.proj, "layers": ["scada", "field"], "shapes": shapes, "lines": [{"from": "a", "to": "b", "cable": "ethernet"}]})
        for cab in self.cables(r):
            self.assertTrue(all(p[0] >= B.MARGIN + B.BAND_W for p in cab["pts"]))


class ChannelRoutingTests(unittest.TestCase):
    """Devices in rows: cables leave by the top or bottom, run on their own track in the band between the rows, and enter by the top or bottom."""
    proj = dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")

    def rows(self):
        def d(i, layer, comp="industrial_switch"):
            return {"id": i, "label": i, "layer": layer, "scope": "avanceon", "component": comp}
        shapes = [d("s1", "scada"), d("s2", "scada"), d("s3", "scada"), d("p1", "control"), d("p2", "control"), d("p3", "control")]
        lines = [{"from": "s1", "to": "p3", "cable": "ethernet"}, {"from": "s2", "to": "p3", "cable": "ethernet"},
                 {"from": "s3", "to": "p1", "cable": "ethernet"}, {"from": "s1", "to": "p1", "cable": "ethernet"}]
        return build({"project": self.proj, "layers": ["scada", "control"], "shapes": shapes, "lines": lines})

    def cables(self, r):
        return [s for s in r["page"].shapes if s["kind"] == "line" and "->" in (s["key"] or "")]

    def test_cables_between_rows_are_vertical_horizontal_vertical_with_separate_tracks(self):
        r = self.rows()
        self.assertEqual(r["warnings"], [])
        ys = []
        for c in self.cables(r):
            pts = [p for i, p in enumerate(c["pts"]) if i == 0 or abs(p[0] - c["pts"][i - 1][0]) + abs(p[1] - c["pts"][i - 1][1]) > 0.1]
            runs = [(p, q) for p, q in zip(pts, pts[1:]) if abs(p[1] - q[1]) < 1e-6 and abs(p[0] - q[0]) > 0.2]
            if runs:                                                                      # (a cable between devices in line is simply straight)
                ys.append(round(runs[0][0][1], 3))
        self.assertGreaterEqual(len(ys), 2)
        self.assertEqual(len(ys), len(set(ys)))                                           # every cable has its own track

    def test_neighbours_in_a_row_get_one_straight_cable_and_others_go_round(self):
        def d(i, x):
            return {"id": i, "label": i, "layer": "scada", "scope": "avanceon", "component": "industrial_switch"}
        shapes = [d("a", 0), d("b", 0), d("c", 0)]
        r = build({"project": self.proj, "layers": ["scada", "field"], "shapes": shapes + [dict(d("f", 0), layer="field")],
                   "lines": [{"from": "a", "to": "b", "cable": "ethernet"}, {"from": "a", "to": "c", "cable": "ethernet"}]})
        ab, ac = self.cables(r)
        self.assertEqual(len(ab["pts"]), 2)                                              # a and b are neighbours: straight
        self.assertGreaterEqual(len(ac["pts"]), 4)                                       # c is behind b: over the top



class HardwiredBusTests(unittest.TestCase):
    proj = dict(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")

    def spec(self):
        def d(i, layer, comp):
            return {"id": i, "label": i, "layer": layer, "scope": "avanceon", "component": comp}
        shapes = [d("io", "control", "remote_i_o_drop"), d("p1", "field", "remote_i_o_drop"), d("p2", "field", "remote_i_o_drop"), d("p3", "field", "remote_i_o_drop")]
        lines = [{"from": k, "to": "io", "cable": "hardwired"} for k in ("p1", "p2", "p3")]
        return {"project": self.proj, "layers": ["control", "field"], "shapes": shapes, "lines": lines}

    def test_instruments_share_one_bus_and_the_arrowhead_is_at_the_io_end(self):
        r = build(self.spec())
        cabs = [s for s in r["page"].shapes if s["kind"] == "line" and "->" in (s["key"] or "")]
        self.assertEqual(len(cabs), 3)
        self.assertTrue(all(c["arrow"] for c in cabs))
        io_bottom = min(s["y"] for s in r["page"].shapes if s["kind"] == "image" and (s["key"] or "").startswith("component:") and s["y"] > B.BOTTOM + 4)
        for c in cabs:
            self.assertGreaterEqual(c["pts"][-1][1], io_bottom - 0.5)                           # the last point (arrowhead) is up at the I/O device
            self.assertLess(c["pts"][0][1], c["pts"][-1][1])                                    # starts at the instrument, below it
        runs = {round(p[1], 3) for c in cabs for p, q in zip(c["pts"], c["pts"][1:]) if abs(p[1] - q[1]) < 1e-6 and abs(p[0] - q[0]) > 0.1}
        self.assertEqual(len(runs), 1)                                                          # one shared horizontal bus

    def test_arrow_is_written_to_the_vsdx(self):
        r = build(self.spec())
        with zipfile.ZipFile(r["out"]) as z:
            self.assertIn("N='EndArrow'", z.read("visio/pages/page1.xml").decode())

    def test_other_cables_have_no_arrow(self):
        r = build(spec())
        self.assertFalse(any(s.get("arrow") for s in r["page"].shapes))


if __name__ == "__main__":
    unittest.main()
