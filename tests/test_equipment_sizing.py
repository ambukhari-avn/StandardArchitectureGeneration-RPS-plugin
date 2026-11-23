"""Equipment sizing rules (docs/equipment-sizing-rules.md): fill space, equal cells, aspect ratio, visible bounds."""
import copy
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_diagram as B
import draw
import reference_layout as R
from vsdx_writer import Page

ROOT = os.path.abspath(B.ROOT)


class EquipmentSizingTests(unittest.TestCase):
    def build(self, spec=None):
        spec = spec or B.load_json(os.path.join(ROOT, "samples", "reference_boxed.json"))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return B.build(spec, os.path.join(ROOT, "base", "base.vsdx"), os.path.join(tmp.name, "a.vsdx"),
                       spec_dir=os.path.join(ROOT, "samples"))

    def images(self, result):
        return [s for s in result["page"].shapes if s["kind"] == "image" and s["key"] != "logo"]

    def test_default_device_size_is_not_a_maximum(self):
        ups = next(s for s in self.images(self.build()) if s["key"] == "component:ups")
        self.assertGreater(ups["h"], 1.25)          # larger than the old default device height

    def test_comparable_devices_have_equal_displayed_sizes(self):
        images = self.images(self.build())
        for keys in (("component:rack_plc",), tuple("image:unknown|p%d" % i for i in range(1, 7))):
            group = [s for s in images if s["key"] in keys]
            self.assertGreaterEqual(len(group), 2)
            self.assertEqual(len({(round(s["w"], 4), round(s["h"], 4)) for s in group}), 1)

    def test_same_component_gets_one_size(self):
        shapes = [dict(id=i, kind="box", reference=True, key="component:rack", layer="control", x=0., y=0., w=w, h=h)
                  for i, (w, h) in enumerate([(2., 1.5), (1.6, 1.8), (2.2, 1.2)])]
        R.equalise(shapes)
        self.assertEqual({(s["w"], s["h"]) for s in shapes}, {(1.6, 1.2)})
        self.assertAlmostEqual(shapes[0]["x"], .2)

    def picture(self, size, box):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(im).rectangle(box, fill=(10, 20, 30, 255))
        path = os.path.join(tmp.name, "p.png")
        im.save(path)
        return path

    def test_visible_box_ignores_transparent_margins(self):
        path = self.picture((200, 100), (50, 10, 149, 89))
        l, t, r, b = draw.visible_box(path)
        self.assertAlmostEqual(l, .25, places=2)
        self.assertAlmostEqual(r, .75, places=2)
        self.assertAlmostEqual(t, .10, places=2)
        self.assertAlmostEqual(b, .90, places=2)

    def test_picture_fills_limiting_dimension_without_distortion(self):
        path = self.picture((200, 100), (50, 10, 149, 89))     # visible part is 100 x 80 px
        page = Page()
        draw.draw_picture(page, path, "Caption", 0., 0., 2., 1.3, "k", fill=.9, visible=True)
        image = page.shapes[0]
        self.assertAlmostEqual(image["w"] / image["h"], 2.0, places=3)          # the file keeps its own aspect ratio
        shown_w, shown_h = image["w"] * .5, image["h"] * .8                      # the visible equipment
        self.assertAlmostEqual(shown_w / shown_h, 100 / 80, places=3)
        area_h = 1.3 - draw.LABEL_ZONE
        self.assertAlmostEqual(max(shown_w / 2., shown_h / area_h), .9, places=3)  # 90 % in the limiting dimension

    def test_sample_equipment_is_not_flagged_small(self):
        result = self.build()
        self.assertFalse([w for w in result["warnings"] if "equipment is only" in w])


if __name__ == "__main__":
    unittest.main()
