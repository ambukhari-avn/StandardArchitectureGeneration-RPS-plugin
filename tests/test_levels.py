"""Purdue levels, header colours and scope colours. Run:  python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import footer
import levels


class OrderTests(unittest.TestCase):
    def test_only_the_used_levels_are_returned_top_to_bottom(self):
        self.assertEqual(levels.order(["L0", "L2", "L1"]), ["L2", "L1", "L0"])
        self.assertEqual(levels.order(["L1"]), ["L1"])
        self.assertEqual(levels.order([]), [])
        self.assertEqual(levels.order(["L0", "L0", "L0"]), ["L0"])

    def test_the_dmz_sits_between_level_4_and_level_3(self):
        self.assertEqual(levels.order(["L3", "L3.5", "L4", "L0", "L5", "L2", "L1"]), ["L5", "L4", "L3.5", "L3", "L2", "L1", "L0"])
        self.assertEqual(levels.order(["L3", "L4", "L3.5"]), ["L4", "L3.5", "L3"])

    def test_an_unknown_level_raises(self):
        with self.assertRaises(ValueError):
            levels.order(["L2", "L9"])
        with self.assertRaises(ValueError):
            levels.level_title("level 2")

    def test_titles_name_the_level(self):
        for k in levels.LEVEL_IDS:
            self.assertTrue(levels.level_title(k).startswith("Level " + k[1:]))


class HeaderColourTests(unittest.TestCase):
    def test_the_default_is_dark_blue_for_every_band(self):
        c = levels.header_colours({})
        self.assertEqual(set(c.values()), {"#1F5FA6"})
        self.assertEqual(set(c), set(levels.LEVEL_IDS))
        self.assertEqual(levels.header_colours(None)["L0"], "#1F5FA6")

    def test_a_valid_client_colour_is_applied_to_that_level_only(self):
        c = levels.header_colours({"band_colors": {"L2": "#112233"}})
        self.assertEqual(c["L2"], "#112233")
        self.assertEqual(c["L1"], levels.DEFAULT_HEADER_FILL)

    def test_an_invalid_colour_is_ignored_with_a_warning(self):
        w = []
        c = levels.header_colours({"band_colors": {"L2": "blue", "L1": "#12345", "L0": "#ABCDEF", "L9": "#000000"}}, w)
        self.assertEqual((c["L2"], c["L1"], c["L0"]), ("#1F5FA6", "#1F5FA6", "#ABCDEF"))
        self.assertEqual(len(w), 3)
        self.assertTrue(any("L2" in x for x in w) and any("L9" in x for x in w))
        w = []
        levels.header_colours({"band_colors": ["#112233"]}, w)
        self.assertEqual(len(w), 1)

    def test_the_header_geometry_is_the_same_for_every_band(self):
        self.assertEqual((levels.HEADER_H, levels.HEADER_SIZE), (0.10, 8))


class ScopeTests(unittest.TestCase):
    def test_scope_colours_equal_the_footer_legend_colours(self):
        self.assertEqual(levels.SCOPE_FILL, {"avanceon": "#E7E6E6", "other": "#F2DCDB"})
        self.assertIs(footer.SCOPE_FILL, levels.SCOPE_FILL)               # one copy only

    def test_a_clear_scope_passes(self):
        self.assertEqual(levels.check_scope({"label": "PLC", "scope": "avanceon"}), "avanceon")
        self.assertEqual(levels.check_scope({"label": "SCADA", "scope": "other"}), "other")
        self.assertEqual(levels.check_scope({"label": "SCADA", "scope": " Other "}), "other")      # spacing / case only

    def test_missing_unknown_or_dual_scope_is_a_question_not_a_guess(self):
        for bad in ({"label": "PLC"}, {"label": "PLC", "scope": "unknown"}, {"label": "PLC", "scope": "dual"},
                    {"label": "PLC", "scope": "both"}, {"label": "PLC", "scope": ""}, {"label": "PLC", "scope": None},
                    {"label": "PLC", "scope": ["avanceon", "other"]}):
            with self.assertRaises(levels.ScopeQuestion) as cm:
                levels.check_scope(bad)
            self.assertIn("Which scope is PLC: Avanceon or Client/Other?", cm.exception.question)


if __name__ == "__main__":
    unittest.main()
