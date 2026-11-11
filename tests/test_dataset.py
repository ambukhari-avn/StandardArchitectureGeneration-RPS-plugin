"""Dataset import and loader tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import import_dataset as imp
from components import Components
from components import DATA
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
        cls.c = Components(extras=False)          # the workbook's rows only; hand-added components are tested below

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


class ExtrasTests(unittest.TestCase):
    """data/components_extra.json: hand-added components that import_dataset.py must never overwrite."""

    def write(self, directory, extra):
        import json
        import shutil
        shutil.copy(os.path.join(DATA, "components.json"), os.path.join(directory, "components.json"))
        os.makedirs(os.path.join(directory, "icons"), exist_ok=True)
        shutil.copy(os.path.join(DATA, "icons", "patch_panel.png"), os.path.join(directory, "icons", "patch_panel.png"))
        with open(os.path.join(directory, "components_extra.json"), "w", encoding="utf-8") as fh:
            json.dump({"source": {}, "components": extra}, fh)
        return os.path.join(directory, "components.json")

    @staticmethod
    def comp(cid, **kw):
        c = {"id": cid, "layer": "Network", "title": cid, "label": cid, "brand": None, "part_number": None, "confidence": None,
             "image_file_name": None, "picture": "icons/patch_panel.png", "duplicate_of": None, "source_row": None}
        c.update(kw)
        return c

    def test_the_extras_are_merged_into_the_library(self):
        c = Components()
        self.assertEqual(c.extra_ids, {"network_switch_approved", "fo_patch_panel"})
        self.assertEqual(len(c.all), 85 + 2)
        self.assertEqual(len(Components(extras=False).all), 85)
        self.assertEqual(c.get("network_switch_approved")["label"], "Network switch")

    def test_the_approved_pictures_exist_and_are_png(self):
        c = Components()
        for cid in ("network_switch_approved", "fo_patch_panel"):
            w, h = png_size(c.picture_path(cid))
            self.assertGreater(w, 100)
            self.assertGreater(h, 100)

    def test_the_imported_workbook_data_is_untouched_by_the_extras(self):
        with open(os.path.join(DATA, "components.json"), encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertFalse({c["id"] for c in raw["components"]} & Components().extra_ids)

    def test_a_duplicate_id_in_the_extras_raises(self):
        import tempfile
        d = tempfile.mkdtemp()
        path = self.write(d, [self.comp("patch_panel")])              # an id that components.json already has
        with self.assertRaises(ValueError) as cm:
            Components(path)
        self.assertIn("patch_panel", str(cm.exception))

    def test_an_extra_with_a_new_id_loads_and_resolves_its_picture_next_to_the_data_file(self):
        import tempfile
        d = tempfile.mkdtemp()
        c = Components(self.write(d, [self.comp("my_extra")]))
        self.assertIn("my_extra", c.extra_ids)
        self.assertTrue(c.picture_path("my_extra").startswith(d))

    def test_a_missing_extras_file_is_fine(self):
        import tempfile
        import shutil
        d = tempfile.mkdtemp()
        shutil.copy(os.path.join(DATA, "components.json"), d)
        self.assertEqual(Components(os.path.join(d, "components.json")).extra_ids, set())


class FindComponentTests(unittest.TestCase):
    """scripts/find_component.py: the library is searched before the web."""

    @classmethod
    def setUpClass(cls):
        import find_component
        cls.fc = find_component

    def ids(self, text):
        return [c["id"] for c in self.fc.find(text)]

    def test_s7_and_siemens_both_find_the_modular_plc(self):
        self.assertIn("modular_plc_siemens", self.ids("S7"))
        self.assertIn("modular_plc_siemens", self.ids("Siemens"))
        self.assertIn("modular_plc_siemens", self.ids("siemens modular"))
        self.assertEqual(self.ids("siemens modular")[0], "modular_plc_siemens")

    def test_every_word_must_match_and_case_does_not_matter(self):
        self.assertEqual(self.ids("SIEMENS zzzz"), [])
        self.assertEqual(self.ids("   "), [])
        self.assertEqual(self.ids("MODULAR PLC SIEMENS"), self.ids("modular plc siemens"))

    def test_the_hand_added_components_are_searched_too(self):
        self.assertIn("network_switch_approved", self.ids("approved"))
        self.assertIn("fo_patch_panel", self.ids("FO patch"))

    def test_exact_repeats_are_not_listed_twice(self):
        ids = self.ids("level switch")
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse([i for i in ids if i.endswith(tuple("0123456789")) and "_row" in i])

    def test_the_command_prints_ids_and_returns_0_or_1(self):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.fc.main(["S7"]), 0)
        self.assertIn("modular_plc_siemens", out.getvalue())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.fc.main(["nothing", "like", "this"]), 1)
        self.assertIn("No library component matches", out.getvalue())

    def test_the_output_says_whether_a_component_has_a_picture(self):
        c = Components()
        by_id = {x["id"]: x for x in c.all}
        self.assertIn("picture", self.fc.describe(by_id["modular_plc_siemens"], c))
        self.assertIn("no picture", self.fc.describe(by_id["pressure_transmitter"], c))


if __name__ == "__main__":
    unittest.main()
