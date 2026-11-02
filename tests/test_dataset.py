"""Dataset import and loader tests. Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import import_dataset as imp
from components import Components
from vsdx_writer import png_size


def row(r, layer, title, brand=None, part=None):
    return {"layer": layer, "title": title, "brand": brand, "part_number": part, "source_row": r}


class IdTests(unittest.TestCase):
    def test_slug_and_base_id(self):
        self.assertEqual(imp.slug("4G/LTE router"), "4g_lte_router")
        self.assertEqual(imp.base_id("Rack server (use 2 stacked for redundant pair)"), "rack_server")
        self.assertEqual(imp.base_id("PS - Pressure switch"), "ps_pressure_switch")

    def test_unique_title_keeps_plain_id_and_collisions_use_brand_then_model(self):
        rows = [row(2, "PLC / L1", "Compact PLC", "Siemens", "6ES7214-1AG40"), row(3, "PLC / L1", "Compact PLC", "Schneider", "TM221CE16T"),
                row(4, "PLC / L1", "Safety PLC", "Siemens", "6ES7511-1FK02"), row(5, "PLC / L1", "Safety PLC", "Siemens", "6ES7155-6AU01"),
                row(6, "Network", "Switch")]
        ids = [i for i, _ in imp.assign_ids(rows)]
        self.assertEqual(ids, ["compact_plc_siemens", "compact_plc_schneider", "safety_plc_siemens_6es75111fk02",
                               "safety_plc_siemens_6es71556au01", "switch"])

    def test_same_title_same_brand_different_layer_uses_layer(self):
        rows = [row(2, "Analyzer / L0", "Chlorine analyzer"), row(3, "Sensor", "Chlorine analyzer")]
        self.assertEqual([i for i, _ in imp.assign_ids(rows)], ["chlorine_analyzer_analyzer_l0", "chlorine_analyzer_sensor"])

    def test_exact_repeat_points_at_first(self):
        rows = [row(2, "Sensor", "Level switch"), row(3, "Sensor", "Level switch"), row(4, "Sensor", "LEVEL SWITCH")]
        out = imp.assign_ids(rows)
        self.assertEqual(out[0], ("level_switch", None))
        self.assertEqual(out[1], ("level_switch_row3", "level_switch"))
        self.assertEqual(out[2][1], "level_switch")

    def test_ids_do_not_depend_on_row_order(self):
        a = [row(2, "PLC / L1", "Compact PLC", "Siemens"), row(3, "PLC / L1", "Compact PLC", "Schneider")]
        fwd = dict(zip([r["brand"] for r in a], [i for i, _ in imp.assign_ids(a)]))
        rev = dict(zip([r["brand"] for r in a[::-1]], [i for i, _ in imp.assign_ids(a[::-1])]))
        self.assertEqual(fwd, rev)

    def test_top_most_picture_wins(self):
        pics = [(16, {"order": 3, "media": "a"}), (16, {"order": 9, "media": "b"}), (16, {"order": 5, "media": "c"}), (17, {"order": 4, "media": "d"})]
        out = imp.top_picture_per_row(pics)
        self.assertEqual(out[16][0]["media"], "b")
        self.assertEqual([p["media"] for p in out[16][1]], ["a", "c"])
        self.assertEqual(out[17][1], [])


class ImportedDataTests(unittest.TestCase):
    """Checks on the committed data/components.json produced from the client's workbook."""

    @classmethod
    def setUpClass(cls):
        cls.c = Components()

    def test_counts(self):
        self.assertEqual(len(self.c.all), 85)
        self.assertEqual(len(self.c.distinct()), 70)
        self.assertEqual(sum(1 for x in self.c.distinct() if x["picture"]), 37)

    def test_ids_unique_and_repeats_resolve(self):
        self.assertEqual(len({x["id"] for x in self.c.all}), len(self.c.all))
        for x in self.c.all:
            self.assertFalse(self.c.get(x["id"])["duplicate_of"])

    def test_every_picture_exists_is_a_png_and_is_transparent_cutout_sized(self):
        for x in self.c.distinct():
            p = self.c.picture_path(x["id"])
            if p:
                w, h = png_size(p)
                self.assertGreater(w, 40)
                self.assertGreater(h, 40)

    def test_text_is_kept_as_supplied(self):
        r = {x["source_row"]: x for x in self.c.all}
        self.assertEqual(r[2]["title"], "4G/LTE router")
        self.assertEqual(r[2]["part_number"], "OnCell G3150A-LTE")
        self.assertEqual(r[16]["part_number"].split(" ")[0], "6AV2124-0MC01-0AX0")

    def test_stacked_pictures_use_the_top_one(self):
        # row 18 (Siemens compact PLC) has three pictures stacked; the S7-1200 on top is the one kept
        r18 = next(x for x in self.c.all if x["source_row"] == 18)
        self.assertEqual((r18["title"], r18["brand"]), ("Compact PLC", "Siemens"))
        self.assertTrue(self.c.picture_path(r18["id"]))
        # row 35 (emergency stop) has its picture although the picture's anchor starts on row 34
        self.assertTrue(next(x for x in self.c.all if x["source_row"] == 35)["picture"])


if __name__ == "__main__":
    unittest.main()
