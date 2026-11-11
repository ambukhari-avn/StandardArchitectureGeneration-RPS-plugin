"""Background removal for web pictures. Run:  python -m unittest discover -s tests
The tests that need Pillow are skipped when it is not installed; the missing-Pillow behaviour is tested either way."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_diagram as B
import imaging
from vsdx_writer import png_size

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

BASE = os.path.join(HERE, "..", "base", "base.vsdx")
RED = (200, 0, 0, 255)


def picture(directory, name="p.png", size=(400, 300), bg=(255, 255, 255, 255), box=(100, 80, 300, 220), hole=None, mode="RGBA"):
    img = Image.new("RGBA", size, bg)
    d = ImageDraw.Draw(img)
    if box:
        d.rectangle([box[0], box[1], box[2] - 1, box[3] - 1], fill=RED)
    if hole:
        d.rectangle([hole[0], hole[1], hole[2] - 1, hole[3] - 1], fill=(255, 255, 255, 255))
    path = os.path.join(directory, name)
    (img if mode == "RGBA" else img.convert("RGB")).save(path)
    return path


@unittest.skipUnless(Image, "Pillow is not installed")
class CleanTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_a_red_square_on_white_loses_the_white_and_is_cropped_to_the_square(self):
        out, status = imaging.clean(picture(self.dir))
        self.assertEqual(status, "removed")
        img = Image.open(out).convert("RGBA")
        self.assertEqual(img.size, (200 + 2 * 2, 140 + 2 * 2))                    # the square plus 2 px each side
        self.assertEqual(img.getpixel((0, 0))[3], 0)                              # corner: transparent
        self.assertEqual(img.getpixel((img.width - 1, img.height - 1))[3], 0)
        self.assertEqual(img.getpixel((img.width // 2, img.height // 2)), RED)    # centre: opaque red

    def test_a_white_hole_enclosed_by_the_object_stays_opaque(self):
        out, status = imaging.clean(picture(self.dir, hole=(180, 130, 220, 170)))
        img = Image.open(out).convert("RGBA")
        self.assertEqual(status, "removed")
        self.assertEqual(img.getpixel((img.width // 2, img.height // 2)), (255, 255, 255, 255))   # the hole in the middle is still white
        self.assertEqual(img.getpixel((0, 0))[3], 0)                                               # the outside is not

    def test_a_white_dent_open_to_the_outside_is_cleared_because_it_is_connected_to_it(self):
        img = Image.new("RGBA", (400, 300), (255, 255, 255, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([100, 80, 299, 219], fill=RED)
        d.rectangle([180, 80, 219, 150], fill=(255, 255, 255, 255))               # a notch cut from the top edge
        path = os.path.join(self.dir, "n.png")
        img.save(path)
        out, _ = imaging.clean(path)
        got = Image.open(out).convert("RGBA")
        self.assertEqual(got.getpixel((got.width // 2, 4))[3], 0)

    def test_a_picture_that_is_already_transparent_is_returned_untouched(self):
        path = picture(self.dir, bg=(0, 0, 0, 0))
        self.assertEqual(imaging.clean(path), (path, "already-transparent"))

    def test_a_picture_with_a_non_white_background_is_skipped_and_flagged(self):
        path = picture(self.dir, bg=(30, 90, 160, 255))
        self.assertEqual(imaging.clean(path), (path, "skipped: background not plain"))

    def test_a_picture_that_is_all_background_is_skipped(self):
        path = picture(self.dir, box=None)
        self.assertEqual(imaging.clean(path), (path, "skipped: the whole picture is background"))

    def test_a_file_that_is_not_a_picture_is_skipped_not_fatal(self):
        path = os.path.join(self.dir, "x.png")
        with open(path, "wb") as fh:
            fh.write(b"nope")
        out, status = imaging.clean(path)
        self.assertEqual(out, path)
        self.assertTrue(status.startswith("skipped: cannot read"))

    def test_a_big_picture_is_reduced_to_800_pixels_on_the_long_side(self):
        path = picture(self.dir, size=(3000, 2000), box=(600, 400, 2400, 1700))
        out, status = imaging.clean(path)
        self.assertEqual(status, "removed")
        w, h = png_size(out)
        self.assertLessEqual(max(w, h), 800)
        self.assertGreater(min(w, h), 100)

    def test_a_jpeg_is_accepted_and_the_original_file_is_never_changed(self):
        path = picture(self.dir, "p.jpg", mode="RGB")
        with open(path, "rb") as fh:
            before = fh.read()
        out, status = imaging.clean(path)
        self.assertEqual(status, "removed")
        self.assertNotEqual(out, path)
        with open(path, "rb") as fh:
            self.assertEqual(fh.read(), before)


class WithoutPillowTests(unittest.TestCase):
    """Decision D1: the core still runs on the standard library alone."""

    def test_a_missing_pillow_returns_the_original_path_with_the_skipped_status(self):
        with mock.patch.object(imaging, "_pillow", return_value=None):
            self.assertEqual(imaging.clean("whatever.png"), ("whatever.png", "skipped: Pillow not installed"))

    def test_the_real_import_failure_is_handled_too(self):
        real = __import__

        def no_pil(name, *a, **k):
            if name == "PIL" or name.startswith("PIL."):
                raise ImportError("no PIL")
            return real(name, *a, **k)
        with mock.patch("builtins.__import__", side_effect=no_pil):
            self.assertIsNone(imaging._pillow())

    def test_the_build_still_places_the_picture_and_says_the_background_was_not_removed(self):
        d = tempfile.mkdtemp()
        sys.path.insert(0, HERE)
        from test_compile_v2 import write_png
        write_png(os.path.join(d, "a.png"), 200, 160)
        spec = {"project": {"project": "P"}, "shapes": [{"id": "t", "label": "T", "x": 2, "y": 2, "image": "a.png", "image_source": "oem"}], "lines": []}
        with mock.patch.object(imaging, "_pillow", return_value=None):
            r = B.build(spec, BASE, os.path.join(d, "o.vsdx"), spec_dir=d)
        self.assertEqual(len([s for s in r["page"].shapes if s["kind"] == "image" and s["key"] != "logo"]), 1)
        self.assertIn("background not removed from a.png (skipped: Pillow not installed); install it once with: pip install pillow", r["warnings"])


@unittest.skipUnless(Image, "Pillow is not installed")
class BuildIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def spec(self, image, qty=1, **kw):
        shapes = [dict({"id": "t%d" % k, "label": "T", "x": 2 + 2 * k, "y": 2, "image": image, "image_source": "https://oem.example"}, **kw) for k in range(qty)]
        return {"project": {"project": "P"}, "shapes": shapes, "lines": []}

    def test_a_web_picture_is_cleaned_before_it_is_placed_and_no_warning_is_printed(self):
        picture(self.dir, "a.png")
        r = B.build(self.spec("a.png"), BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)
        used = [s["image"] for s in r["page"].shapes if s["kind"] == "image" and s["key"] != "logo"]
        self.assertEqual(len(used), 1)
        self.assertTrue(used[0].endswith("_clean.png"))
        self.assertFalse([w for w in r["warnings"] if "background" in w])

    def test_one_file_used_by_several_shapes_is_cleaned_once(self):
        picture(self.dir, "a.png")
        with mock.patch.object(imaging, "clean", wraps=imaging.clean) as spy:
            B.build(self.spec("a.png", qty=3), BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)
        self.assertEqual(spy.call_count, 1)

    def test_a_picture_that_cannot_be_cleaned_is_still_placed_with_one_warning(self):
        picture(self.dir, "a.png", bg=(30, 90, 160, 255))
        r = B.build(self.spec("a.png", qty=2), BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)
        self.assertEqual(len([s for s in r["page"].shapes if s["kind"] == "image" and s["key"] != "logo"]), 2)
        self.assertEqual([w for w in r["warnings"] if "background" in w], ["background not removed from a.png (skipped: background not plain)"])

    def test_library_pictures_are_never_cleaned(self):
        with mock.patch.object(imaging, "clean", wraps=imaging.clean) as spy:
            spec = {"project": {"project": "P"}, "shapes": [{"id": "a", "label": "PLC", "component": "modular_plc_siemens", "x": 2, "y": 2}], "lines": []}
            B.build(spec, BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)
        self.assertEqual(spy.call_count, 0)

    def test_an_already_transparent_picture_prints_no_warning(self):
        picture(self.dir, "a.png", bg=(0, 0, 0, 0))
        r = B.build(self.spec("a.png"), BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)
        self.assertFalse([w for w in r["warnings"] if "background" in w])


if __name__ == "__main__":
    unittest.main()
