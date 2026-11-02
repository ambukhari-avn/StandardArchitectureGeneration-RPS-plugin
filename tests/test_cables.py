"""Cable table tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cables


def tmp_json(obj):
    p = os.path.join(tempfile.mkdtemp(), "x.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    return p


class CableTests(unittest.TestCase):
    def setUp(self):
        self.c = cables.Cables()

    def test_client_colour_standard(self):
        self.assertEqual(self.c.status, "client")
        self.assertEqual({i: c["color"] for i, c in self.c.by_id.items()},
                         {"ethernet": "#0000FF", "fibre": "#FF0000", "modbus": "#00B000", "bacnet": "#7030A0", "hardwired": "#000000"})
        self.assertEqual(self.c.line_style("fibre"), ("#FF0000", 1))

    def test_legend_has_only_used_cables_in_table_order(self):
        leg = self.c.legend(["fibre", "ethernet"])
        self.assertEqual([e["label"] for e in leg], ["Ethernet (Cu)", "Fibre"])
        self.assertTrue(all(e["kind"] == "line" and e["color"].startswith("#") for e in leg))

    def test_unknown_cable_is_an_error(self):
        with self.assertRaises(cables.CableError):
            self.c.get("coax")
        with self.assertRaises(cables.CableError):
            self.c.legend(["ethernet", "coax"])

    def test_bad_tables_are_rejected(self):
        ok = {"id": "a", "label": "A", "color": "#112233", "pattern": 1}
        for bad in (dict(ok, color="112233"), dict(ok, pattern=3), dict(ok, label=" ")):
            with self.assertRaises(cables.CableError):
                cables.Cables(tmp_json({"cables": [bad]}))
        with self.assertRaises(cables.CableError):
            cables.Cables(tmp_json({"cables": [ok, ok]}))
        with self.assertRaises(cables.CableError):
            cables.Cables(tmp_json({"cables": []}))

    def test_legend_feeds_the_footer(self):
        import footer
        from vsdx_writer import Page
        pg = Page()
        footer.build_footer(pg, dict(end_user="a", contractor="b", project="c", prepared_by="d", checked_by="e", approved_by="f"),
                            self.c.legend(["ethernet", "fibre", "hardwired"]))
        lines = [s for s in pg.shapes if s["role"] == "line"]
        self.assertEqual(sorted(s["line"] for s in lines), sorted(self.c.by_id[i]["color"] for i in ("ethernet", "fibre", "hardwired")))


if __name__ == "__main__":
    unittest.main()
