"""Phase 11 acceptance tests A-E, run through the real questionnaire (scripts/examples.py). Run:  python -m unittest discover -s tests

Test E's automatic checks run on every build (result["qa"]); the full-page preview is still inspected by eye before delivery.
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import arch_spec as A
import examples as X
import qa

BUILT = {}


def built(name):
    if name not in BUILT:
        run = X.CASES[name]()
        run.changes = A.changes_since_baseline(run.spec)                 # before generation stores a new baseline
        folder = tempfile.mkdtemp()
        r = X.write(name, run, folder, preview=False)
        d, warnings = A.to_diagram(run.spec)
        BUILT[name] = (run, r, d, warnings)
    return BUILT[name]


def drawn(r):
    return {s["key"]: s for s in r["page"].shapes if s.get("key")}


class TestA_SimplePLC(unittest.TestCase):
    def test_only_required_layers(self):
        run, r, d, _ = built("A_simple_plc")
        self.assertEqual(d["layers"], ["control", "field"])
        heads = [k for k in drawn(r) if k.startswith("layer-heading:")]
        self.assertEqual(sorted(heads), ["layer-heading:control", "layer-heading:field"])

    def test_equipment_positions_bottom_to_top(self):
        run, r, d, _ = built("A_simple_plc")
        y = {s["id"]: s for s in d["shapes"]}
        # rows from the top: switches (row 0), PLC/HMI (row 1), I/O (row 2): I/O -> PLC -> switches upwards (7.6)
        self.assertLess(y["EQ-006-1"]["row"], y["EQ-004-1"]["row"])
        self.assertLess(y["EQ-004-1"]["row"], y["EQ-005-1"]["row"])
        page = drawn(r)
        top = lambda i: page["shape:" + i]["y"] if "shape:" + i in page else None   # noqa: E731
        boxes = {s["id"]: s for s in d["shapes"]}
        self.assertTrue(boxes)

    def test_hardwired_ends_at_io(self):
        run, r, d, _ = built("A_simple_plc")
        hw = [c for c in r["display_connections"] if c["cable"] == "hardwired"]
        self.assertEqual(len(hw), 1)                                     # one representative connection
        self.assertEqual(hw[0]["b"] if hw[0]["a"].startswith("G-FIELD") else hw[0]["a"], "EQ-005-1")

    def test_no_unnecessary_boxes_or_equipment(self):
        run, r, d, _ = built("A_simple_plc")
        frames = [s for s in d["shapes"] if s.get("kind") == "group" and s.get("frame", True)]
        self.assertEqual([s["id"] for s in frames], ["G-FIELD"])         # only the field-instrument group is a visible box
        self.assertEqual(len(run.spec["equipment"]), 7)
        self.assertEqual(r["qa"], [])


class TestB_RedundantPLC(unittest.TestCase):
    def test_cpus_side_by_side_with_sync_link(self):
        run, r, d, _ = built("B_redundant_plc")
        shapes = {s["id"]: s for s in d["shapes"]}
        self.assertEqual(shapes["EQ-004-1"]["row"], shapes["EQ-004-2"]["row"])
        sync = [l for l in d["lines"] if l.get("direct")]
        self.assertEqual(len(sync), 1)
        self.assertEqual((sync[0]["from"], sync[0]["to"], sync[0]["arrows"]), ("EQ-004-1", "EQ-004-2", "both"))
        self.assertIn("Redundancy Sync (2 links)", sync[0]["label"])

    def test_representative_io_with_quantity(self):
        run, r, d, _ = built("B_redundant_plc")
        racks = [s for s in d["shapes"] if s["id"].startswith("EQ-005")]
        self.assertEqual(len(racks), 1)
        self.assertEqual(racks[0]["sublabel"], "Qty: 4 \u00b7 Dual redundant network")   # topology in the caption (v1.7.2)
        self.assertNotIn("G-IO", [s.get("parent", "")[:4] for s in racks])          # not inside a separate box
        self.assertEqual(A.eq(run.spec, "EQ-005")["quantity"], 4)                   # the specification keeps all four

    def test_redundant_network_paths(self):
        run, r, d, _ = built("B_redundant_plc")
        to_rack = [l for l in d["lines"] if l.get("to") == "EQ-005-1" and l["cable"] == "ethernet"]
        self.assertEqual({l["from"] for l in to_rack}, {"EQ-006-1", "EQ-006-2"})     # both switches reach the I/O network
        self.assertFalse(any(l.get("label") for l in to_rack))       # no crowded link label; the caption carries the topology
        plc_sw = {(l["from"], l["to"]) for l in d["lines"] if l["from"].startswith("EQ-004") and l["to"].startswith("EQ-006")}
        self.assertEqual(plc_sw, {("EQ-004-1", "EQ-006-1"), ("EQ-004-2", "EQ-006-2")})

    def test_clean_drawing(self):
        run, r, d, warnings = built("B_redundant_plc")
        self.assertEqual(r["qa"], [])
        self.assertFalse([w for w in warnings if "no drawn connection" in w])


class TestC_DMZ(unittest.TestCase):
    def test_dmz_named_and_only_selected_layers(self):
        run, r, d, _ = built("C_dmz")
        self.assertEqual(d["layers"], ["enterprise", "dmz", "scada", "control"])
        self.assertEqual(d["layer_headers"]["dmz"]["name"], "DMZ — Demilitarized Zone")
        name = drawn(r)["layer-name:dmz"]["text"].replace("\n", " ")
        self.assertEqual(name, "DMZ — Demilitarized Zone")

    def test_security_zone_interfaces(self):
        run, r, d, _ = built("C_dmz")
        fw = {(l["from"], l["to"]) for l in d["lines"] if "EQ-005-1" in (l["from"], l["to"])}
        self.assertIn(("EQ-005-1", "EQ-004-1"), fw)                    # SCADA switch side
        self.assertIn(("EQ-005-1", "EQ-008-1"), fw)                    # corporate switch side
        self.assertIn(("EQ-006-1", "EQ-005-1"), fw)                    # DMZ server behind the firewall

    def test_nothing_added(self):
        run, r, d, _ = built("C_dmz")
        cats = [e["category"] for e in run.spec["equipment"]]
        self.assertEqual(cats.count("firewall"), 1)
        self.assertEqual(cats.count("server") + cats.count("historian"), 3)   # SCADA servers, DMZ replica, ERP: as requested
        self.assertEqual(len([s for s in d["shapes"] if s.get("kind") != "group"]), 9)
        self.assertEqual(r["qa"], [])


class TestD_Revision(unittest.TestCase):
    def test_only_affected_items_change(self):
        run, r, d, _ = built("D_revision")
        ch = run.changes
        self.assertEqual([c["id"] for c in ch["equipment"]["changed"]], ["EQ-008"])
        self.assertEqual(ch["equipment"]["added"], [])
        self.assertEqual(ch["equipment"]["removed"], [])
        changed = {c["id"] for c in ch["connections"]["changed"]}
        self.assertEqual(changed, {c["id"] for c in run.spec["connections"] if c.get("origin") == "plcsw:EQ-004"})
        self.assertEqual(ch["connections"]["removed"], [])

    def test_unrelated_devices_unchanged(self):
        b = built("B_redundant_plc")[2]
        d = built("D_revision")[2]
        before = {s["id"]: s for s in b["shapes"]}
        after = {s["id"]: s for s in d["shapes"]}
        self.assertEqual(set(after) - set(before), {"EQ-008-2"})       # only the added workstation is new
        for i, s in before.items():
            if not i.startswith("EQ-008"):
                self.assertEqual({k: v for k, v in s.items() if k != "columns"}, {k: v for k, v in after[i].items() if k != "columns"})

    def test_title_block_and_footer_fixed_and_rebuilds(self):
        rb = built("B_redundant_plc")[1]
        rd = built("D_revision")[1]
        self.assertEqual(qa.template_signature(rb["page"]), qa.template_signature(rd["page"]))
        self.assertEqual(rd["qa"], [])
        rev = [s for s in rd["page"].shapes if "R1" in str(s.get("text") or "")]
        self.assertTrue(rev)                                            # the new revision is printed in the same title block


class TestE_VisualQuality(unittest.TestCase):
    def test_all_examples_pass_automatic_checks(self):
        for name in X.CASES:
            run, r, d, _ = built(name)
            self.assertEqual(r["qa"], [], name)
            page = r["page"]
            self.assertEqual(qa.check_page(page), [])
            self.assertEqual(qa.check_template(page), [])

    def test_vertical_headings_and_arrows(self):
        run, r, d, _ = built("B_redundant_plc")
        names = [s for s in r["page"].shapes if (s.get("key") or "").startswith("layer-name:")]
        self.assertTrue(all(s["text_angle"] == 90 for s in names))
        lines = [s for s in r["page"].shapes if s["kind"] == "line" and s.get("key")]
        eth = [s for s in lines if s["line"] == "#0000FF"]
        self.assertTrue(eth and not any(s.get("arrow") or s.get("arrow_start") for s in eth))   # no one-way Ethernet
        hw = [s for s in lines if s["line"] == "#000000" and s["key"].startswith("G-FIELD")]
        self.assertTrue(hw and all(s.get("arrow") and not s.get("arrow_start") for s in hw))   # signal arrow at the I/O
        sync = [s for s in lines if s["key"] == "EQ-004-1->EQ-004-2"]
        self.assertTrue(sync and sync[0].get("arrow") and sync[0].get("arrow_start"))

    def test_template_change_stops_the_build(self):
        import build_diagram as B
        import reference_footer as RF
        old = RF.F.HEIGHT
        try:
            RF.F.HEIGHT = old + .2
            with self.assertRaises(B.BuildError):
                X.write("A_simple_plc", X.case_a(), tempfile.mkdtemp(), preview=False)
        finally:
            RF.F.HEIGHT = old

    def test_editable_visio_output(self):
        import zipfile
        run, r, d, _ = built("A_simple_plc")
        with zipfile.ZipFile(r["out"]) as z:
            page = z.read("visio/pages/page1.xml").decode("utf-8")
        self.assertIn("TxtAngle", page)                                 # editable rotated heading text
        self.assertIn("EndArrow", page)
        self.assertGreater(page.count("<Shape "), 20)


if __name__ == "__main__":
    unittest.main()
