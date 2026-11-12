"""Regression checks for picture detail, safe cutouts and reference line weights."""
import os
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pictures
import build_diagram as B
import dev_preview
from vsdx_writer import Page, shape_xml, write_vsdx
import footer


class ReferenceQualityTests(unittest.TestCase):
    def test_all_dashed_shape_kinds_export_native_tiny_dashes(self):
        page = Page()
        page.line([(1, 1), (4, 1)], "#0000FF", pattern=2)
        page.ellipse("ring", 1, 2, 3, .5, pattern=2)
        page.rect("zone", 1, 3, 3, 1, pattern=2, rounding=.12)
        for shape in page.shapes:
            xml = ET.fromstring(shape_xml(shape))
            cell = xml.find("Cell[@N='LinePattern']")
            self.assertEqual(cell.get("V"), "23")

    def test_packaged_bitmap_cannot_inherit_a_black_rectangle(self):
        im = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((20, 20, 60, 60), fill=(0, 0, 0, 255))
        path = self.save(im)
        page = Page()
        page.image(1, 1, 1, 1, path)
        out = os.path.join(os.path.dirname(path), "image.vsdx")
        write_vsdx(page, out, os.path.join(B.ROOT, "base", "base.vsdx"))
        ns = {"v": "http://schemas.microsoft.com/office/visio/2012/main"}
        with zipfile.ZipFile(out) as package:
            root = ET.fromstring(package.read("visio/pages/page1.xml"))
            shape = root.find("v:Shapes/v:Shape", ns)
            for name in ("FillPattern", "LinePattern", "ShdwPattern"):
                self.assertEqual(shape.find("v:Cell[@N='%s']" % name, ns).get("V"), "0")
            for name in ("NoFill", "NoLine"):
                self.assertEqual(shape.find("v:Section[@N='Geometry']/v:Cell[@N='%s']" % name, ns).get("V"), "1")
            with open(path, "rb") as original:
                self.assertEqual(package.read("visio/media/image1.png"), original.read())

    def test_layer_heading_has_full_height_blue_divider(self):
        page = Page()
        B.draw_layer(page, dict(id="scada", x=0, y=0, w=B.AREA_W, h=2, level="Level 2", name="SCADA", desc="Supervision"))
        border = next(s for s in page.shapes if s["key"] == "layer-divider:scada")
        self.assertEqual(border["line"], B.BLUE)
        self.assertEqual(border["lw"], 1.5)
        self.assertAlmostEqual(border["h"], 2)
        self.assertAlmostEqual(border["x"], B.MARGIN + B.BAND_W)

    def test_footer_borders_and_field_headings_are_bold(self):
        page = Page()
        footer.build_footer(page, {}, [{"label": "Ethernet", "color": "#0000FF", "pattern": 2}], allow_tbc=True)
        for shape in page.shapes:
            if shape["role"] == "block":
                self.assertGreaterEqual(shape["lw"], 1.5)
                self.assertEqual(shape["line"], footer.BLUE)
                if shape["text"]:
                    self.assertTrue(shape["bold"])
        for label in ("Notes:", "Legend", "Avanceon Scope", "Client Scope", "Ethernet"):
            self.assertTrue(next(s for s in page.shapes if s["text"] == label)["bold"])

    def save(self, im):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = os.path.join(folder.name, "device.png")
        im.save(path)
        return path

    def test_transparent_original_retains_detail_and_partial_alpha(self):
        im = Image.new("RGBA", (1800, 500), (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle((20, 20, 1779, 479), fill=(70, 90, 110, 255))
        im.putpixel((20, 25), (70, 90, 110, 100))
        result, note = pictures.prepare(self.save(im))
        self.assertIsNone(note)
        with Image.open(result) as cleaned:
            self.assertGreater(cleaned.width, 1700)
            self.assertIn(100, cleaned.getchannel("A").getdata())

    def test_complex_background_is_retained_with_explanation(self):
        im = Image.new("RGB", (120, 120), "navy")
        ImageDraw.Draw(im).rectangle((60, 0, 119, 119), fill="orange")
        path = self.save(im)
        result, note = pictures.prepare(path)
        self.assertEqual(result, path)
        self.assertIn("not a uniform light backdrop", note)

    def test_keep_mode_and_auto_use_separate_cached_results(self):
        im = Image.new("RGB", (120, 120), "white")
        ImageDraw.Draw(im).rectangle((30, 30, 90, 90), fill="black")
        path = self.save(im)
        auto, _ = pictures.prepare(path)
        keep, note = pictures.prepare(path, background="keep")
        self.assertIsNone(note)
        self.assertNotEqual(auto, keep)
        with Image.open(keep) as preserved:
            self.assertEqual(preserved.getpixel((0, 0)), (255, 255, 255, 255))

    def test_preview_draws_bold_text_and_dashed_container(self):
        self.assertNotEqual(dev_preview._font(12, True).getname(), dev_preview._font(12, False).getname())
        page = Page(w=2, h=1)
        page.rect("zone", .1, .1, 1.8, .8, line="#0000FF", lw=1.5, pattern=2)
        path = self.save(Image.new("RGB", (1, 1)))
        dev_preview.render(page, path)
        with Image.open(path) as im:
            self.assertEqual(im.size, (400, 200))
            top = [im.getpixel((x, 20)) for x in range(22, 378)]
            self.assertIn((255, 255, 255), top)
            self.assertIn((0, 0, 255), top)

    def test_build_emits_bold_cables_and_low_resolution_warning(self):
        path = self.save(Image.new("RGBA", (40, 40), (50, 70, 90, 255)))
        spec = {"shapes": [{"id": "a", "label": "A", "x": 1, "y": 1, "image": path, "background": "keep"},
                           {"id": "b", "label": "B", "x": 5, "y": 1, "component": "industrial_switch"}],
                "lines": [{"from": "a", "to": "b", "cable": "ethernet"}]}
        out = os.path.join(os.path.dirname(path), "diagram.vsdx")
        result = B.build(spec, os.path.join(B.ROOT, "base", "base.vsdx"), out, spec_dir=os.path.dirname(path))
        cable = next(s for s in result["page"].shapes if s["key"] == "a->b")
        self.assertEqual(cable["lw"], 1.75)
        self.assertTrue(any("pixels per displayed inch" in w for w in result["warnings"]))
