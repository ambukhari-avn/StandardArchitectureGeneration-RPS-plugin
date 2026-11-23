"""Text fitting and component drawing tests. Run:  python -m unittest discover -s tests"""
import os
import re
import sys
import tempfile
import unittest
import zipfile
import xml.dom.minidom

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import textfit
from components import Components
from draw import LABEL_ZONE, draw_component
from vsdx_writer import FONT_FLOOR, Page, png_size, write_vsdx

BASE = os.environ.get("ARCH_BASE_VSDX") or os.path.join(HERE, "..", "base", "base.vsdx")


class TextFitTests(unittest.TestCase):
    def test_returns_largest_size_that_fits(self):
        self.assertEqual(textfit.fit_size("OK", 1.0, 0.3, (8, 7, 6)), 8)
        long = "word " * 14                                   # needs a smaller size in a narrow cell
        self.assertLess(textfit.fit_size(long.strip(), 1.0, 0.45, (8, 7, 6.5, 6)), 8)

    def test_never_goes_below_the_floor(self):
        with self.assertRaises(textfit.TextFitError):
            textfit.fit_size("x" * 500, 1.0, 0.3, (8, 7, 6.5, 6, 5, 4))
        self.assertEqual(FONT_FLOOR, 6.0)

    def test_newlines_count_as_lines(self):
        self.assertEqual(textfit.lines_needed("a\nb\nc", 2.0, 7), 3)


class DrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = Components()

    def test_component_without_picture_is_a_rectangle_with_its_label(self):
        pg = Page()
        ids = draw_component(pg, self.c, "ps_pressure_switch", 1.0, 1.0, 1.4, 0.6)
        self.assertEqual(len(ids), 1)
        s = pg.shapes[0]
        self.assertEqual((s["kind"], s["text"]), ("rect", "PS - Pressure switch"))
        self.assertEqual((s["x"], s["y"], s["w"], s["h"]), (1.0, 1.0, 1.4, 0.6))
        self.assertGreaterEqual(s["size"], FONT_FLOOR)
        self.assertEqual(s["key"], "ps_pressure_switch|qty=1")

    def test_component_with_picture_is_a_picture_with_label_underneath(self):
        pg = Page()
        draw_component(pg, self.c, "hmi_panel_siemens", 2.0, 2.0, 1.2, 1.0, suffix="-01", qty=3)
        img, txt = pg.shapes
        self.assertEqual(img["kind"], "image")
        self.assertEqual(txt["text"], "HMI panel-01")
        self.assertAlmostEqual(txt["y"], 2.0)
        self.assertAlmostEqual(txt["h"], LABEL_ZONE)
        self.assertGreaterEqual(img["y"], 2.0 + LABEL_ZONE - 1e-9)                    # picture sits above the label zone
        self.assertLessEqual(img["x"] + img["w"], 2.0 + 1.2 + 1e-9)
        iw, ih = png_size(self.c.picture_path("hmi_panel_siemens"))
        self.assertAlmostEqual(img["w"] / img["h"], iw / ih, 3)                      # true aspect ratio
        self.assertTrue(img["key"].endswith("|qty=3"))

    def test_repeat_row_resolves_to_the_component_it_repeats(self):
        pg = Page()
        draw_component(pg, self.c, "ls_level_switch_row60", 1, 1, 1.4, 0.6)
        self.assertTrue(pg.shapes[0]["key"].startswith("ls_level_switch|"))

    def test_label_that_cannot_fit_raises(self):
        with self.assertRaises(textfit.TextFitError):
            draw_component(Page(), self.c, "dpit_differential_pressure_indicating_transmitter", 1, 1, 0.3, 0.2)

    def test_cell_too_short_for_picture_and_label_raises(self):
        with self.assertRaises(ValueError):
            draw_component(Page(), self.c, "hmi_panel_siemens", 1, 1, 1.2, LABEL_ZONE)

    def test_one_picture_used_many_times_is_stored_once(self):
        pg = Page()
        for i in range(5):
            draw_component(pg, self.c, "hmi_panel_siemens", 1 + i * 1.3, 5, 1.2, 1.0, suffix="-%02d" % (i + 1))
        draw_component(pg, self.c, "hmi_panel_schneider", 1, 3, 1.2, 1.0)
        out = os.path.join(tempfile.mkdtemp(), "t.vsdx")
        write_vsdx(pg, out, BASE, "t")
        z = zipfile.ZipFile(out)
        media = [n for n in z.namelist() if n.startswith("visio/media/")]
        self.assertEqual(len(media), 2)                                               # two different pictures, six placements
        page = z.read("visio/pages/page1.xml").decode()
        self.assertEqual(page.count("Type='Foreign'"), 6)
        self.assertEqual(len(re.findall(r"<Rel r:id='rId1'/>", page)), 5)
        for n in z.namelist():
            if n.endswith((".xml", ".rels")):
                xml.dom.minidom.parseString(z.read(n))


if __name__ == "__main__":
    unittest.main()
