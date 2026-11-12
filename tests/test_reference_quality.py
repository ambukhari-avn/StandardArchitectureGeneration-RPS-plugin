"""Regression checks for picture detail, safe cutouts and reference line weights."""
import os
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pictures
import build_diagram as B
import dev_preview
from vsdx_writer import Page


class ReferenceQualityTests(unittest.TestCase):
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
