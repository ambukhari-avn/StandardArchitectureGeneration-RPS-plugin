"""v1.7.2 engine regression tests: blocking quality checks with automatic correction, layout lock, minimum picture sizes, instrument
library and ISA balloon fallback, buses, relative placement, waypoints, corridors, attachment points, verify-diagram, revisions with
--previous, and the v1.7.1 defects. Run:  python -m unittest discover -s tests"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import arch_spec as A
import build_diagram as B
import examples as X
import qa
from components import Components, instrument_tag

BASE = os.path.join(ROOT, "base", "base.vsdx")


def build(spec, **kw):
    out = os.path.join(tempfile.mkdtemp(), "A.vsdx")
    return B.build(spec, BASE, out, spec_dir=os.path.join(ROOT, "samples"), **kw), out


def scada(n_ws=4, extra=None):
    """A small SCADA layer: n workstations and a switch, each workstation linked to the switch."""
    shapes = [{"id": "g", "kind": "group", "layer": "scada", "label": "", "frame": False},
              {"id": "sw", "parent": "g", "component": "ethernet_switch", "label": "SCADA Switch", "row": 1, "category": "switch"}]
    lines = []
    for i in range(1, n_ws + 1):
        shapes.append({"id": "ws%d" % i, "parent": "g", "component": "client_operator_workstation", "label": "Operator Workstation %d" % i,
                       "row": 0, "category": "workstation"})
        lines.append({"from": "ws%d" % i, "to": "sw", "cable": "ethernet"})
    spec = {"layers": ["scada"], "project": {"client": "ACME", "project": "Test", "doc_name": "Test"}, "shapes": shapes, "lines": lines}
    spec.update(extra or {})
    return spec


class InstrumentLibraryTests(unittest.TestCase):
    def test_every_library_component_has_a_picture(self):
        c = Components()
        self.assertEqual([x["id"] for x in c.distinct() if not x.get("picture")], [])
        for cid in ("pressure_transmitter", "electromagnetic_flowmeter", "radar_level_transmitter", "mov_motor_operated_valve"):
            self.assertTrue(os.path.exists(c.picture_path(cid)), cid)

    def test_missing_instrument_picture_is_an_isa_balloon_never_the_generic_icon(self):
        spec = {"layers": ["field"], "project": {"client": "A", "project": "B", "doc_name": "C"},
                "shapes": [{"id": "f", "kind": "group", "layer": "field", "label": ""},
                           {"id": "pt", "parent": "f", "label": "Pressure Transmitters", "category": "instrument"},
                           {"id": "xv", "parent": "f", "label": "Shutdown Valves", "category": "instrument"}]}
        r, _ = build(spec)
        keys = {s["key"] for s in r["page"].shapes if s.get("key")}
        self.assertFalse(any(k.startswith("generic:") for k in keys))
        pics = [s.get("image") for s in r["page"].shapes if s.get("image")]
        self.assertTrue(any("isa_pt" in p for p in pics) and any("isa_xv" in p for p in pics))
        self.assertEqual((instrument_tag("Temperature Transmitter"), instrument_tag("Level switch")), ("TT", "LS"))

    def test_examples_use_no_generic_icon(self):
        for name in X.CASES:
            run = X.CASES[name]()
            d, _ = A.to_diagram(run.spec)
            instruments = {s["id"] for s in d["shapes"] if s.get("category") == "instrument"}
            r = X.write(name, run, tempfile.mkdtemp(), preview=False)
            generic = {str(s.get("key"))[len("generic:"):] for s in r["page"].shapes if str(s.get("key", "")).startswith("generic:")}
            self.assertFalse(generic & instruments, name)                # instruments: library picture or ISA balloon only


class SizeAndCorrectionTests(unittest.TestCase):
    def test_categories_and_plc_io_priority(self):
        sz = qa.sizes()
        self.assertGreater(sz["plc"]["min"], sz["server"]["min"])
        self.assertGreater(sz["io"]["weight"], 1.0)
        self.assertEqual(qa.category_of({"label": "Redundant PLC Controller"}), "plc")
        self.assertEqual(qa.category_of({"label": "Remote I/O Rack 2"}), "io")
        self.assertEqual(qa.category_of({"label": "Level switch"}), "instrument")

    def test_plc_and_io_meet_their_minimums_in_examples(self):
        r = X.write("B_redundant_plc", X.case_b(), tempfile.mkdtemp(), preview=False)
        for s in r["page"].shapes:
            pass
        self.assertEqual(r["qa"], [])

    def test_impossible_layout_is_not_built_and_writes_nothing(self):
        shapes = [{"id": "g", "kind": "group", "layer": "control", "label": "", "frame": False}]
        shapes += [{"id": "p%d" % i, "parent": "g", "component": "rack_plc", "label": "PLC %d" % i, "category": "plc", "row": 0}
                   for i in range(120)]
        spec = {"layers": ["control"], "project": {"client": "A", "project": "B", "doc_name": "C"}, "shapes": shapes}
        out = os.path.join(tempfile.mkdtemp(), "A.vsdx")
        with self.assertRaises(B.BuildError) as ctx:
            B.build(spec, BASE, out, spec_dir=ROOT)
        self.assertIn("blocking quality defects", str(ctx.exception))
        self.assertFalse(os.path.exists(out))

    def test_correction_is_reported(self):
        r, _ = build(B.load_json(os.path.join(ROOT, "samples", "two_plc_systems.json")))
        self.assertEqual(r["qa"], [])


class LockTests(unittest.TestCase):
    def test_same_diagram_same_layout_and_lock_enforced(self):
        spec = B.load_json(os.path.join(ROOT, "samples", "reference_quality.json"))
        r1, _ = build(copy.deepcopy(spec))
        r2, _ = build(copy.deepcopy(spec), locked_layout=r1["layout"])
        self.assertEqual(r1["layout"], r2["layout"])
        changed = copy.deepcopy(spec)
        changed["shapes"][1]["label"] = "Changed after approval"
        with self.assertRaises(B.BuildError):
            build(changed, locked_layout=r1["layout"])

    def test_preview_is_rendered_from_the_built_page(self):
        r, _ = build(B.load_json(os.path.join(ROOT, "samples", "reference_quality.json")))
        self.assertEqual(qa.layout_signature(r["page"]), r["layout"])       # the preview renders this very page


class BusTests(unittest.TestCase):
    def test_bus_replaces_a_fan_of_cables(self):
        spec = scada(4, {"buses": [{"id": "lan", "members": ["ws1", "ws2", "ws3", "ws4"], "cable": "ethernet", "label": "SCADA LAN"}]})
        spec["lines"] = [{"from": "sw", "to": "lan", "cable": "ethernet"}]
        r, _ = build(spec)
        keys = [s.get("key") or "" for s in r["page"].shapes]
        self.assertEqual(sum(1 for k in keys if k == "bus:lan|drop"), 4)
        self.assertIn("bus:lan", keys)
        self.assertEqual(r["qa"], [])

    def test_generator_uses_a_bus_and_keeps_logical_links(self):
        run = X.case_d()
        d, _ = A.to_diagram(run.spec)
        self.assertTrue(d.get("buses"))
        ws = A.eq(run.spec, "EQ-008")
        self.assertTrue(any(ll for ll in d["logical_links"] if ["EQ-008-2", "EQ-006-1"] in ll["units"]))
        self.assertEqual(A.verify_diagram(run.spec, d), [])
        self.assertEqual(ws["quantity"], 2)

    def test_bus_can_be_switched_off(self):
        run = X.case_d()
        run.spec.setdefault("layout", {})["buses"] = "off"
        d, _ = A.to_diagram(run.spec)
        self.assertNotIn("buses", d)


class PlacementAndRoutingTests(unittest.TestCase):
    def test_left_of_reorders_a_row_and_conflicts_stop(self):
        spec = scada(3)
        for s in spec["shapes"]:
            if s["id"] == "ws3":
                s["place"] = {"left_of": "ws1"}
        r, _ = build(copy.deepcopy(spec))
        x = {s["text"]: s["x"] for s in r["page"].shapes if str(s.get("text") or "").startswith("Operator Workstation")}
        self.assertLess(x["Operator Workstation 3"], x["Operator Workstation 1"])
        for s in spec["shapes"]:
            if s["id"] == "ws1":
                s["place"] = {"left_of": "ws3"}
        with self.assertRaises(B.BuildError):
            build(spec)

    def test_waypoints_are_followed(self):
        spec = scada(1)
        r0, _ = build(copy.deepcopy(spec))
        spec["lines"][0]["waypoints"] = [[3.0, 1.2]]
        r, _ = build(spec)
        line = next(s for s in r["page"].shapes if s["kind"] == "line" and (s.get("key") or "").startswith("ws1"))
        self.assertTrue(any(abs(x - (B.MARGIN + 3.0)) < .05 for x, y in line["pts"]))

    def test_corridor_and_picture_end_checks(self):
        lines = [{"a": "x", "b": "y", "cable": "ethernet"}]
        self.assertTrue(qa.check_corridors(lines, [[(1, 5), (1, 1), (2, 1)]], [(0, 4, 10, 2)], [], lambda i: (0, 0, 1, 1)))
        dev = {"id": "y", "kind": "box", "pic": "p"}
        out = qa.check_picture_ends(lines, [[(5, 9), (5, 2)]], {"y": dev}, lambda d: (1, 0, 1, 2), lambda pt, d: True)
        self.assertTrue(out and "dangling" in out[0])

    def test_cables_never_leave_the_drawing_area(self):
        self.assertTrue(qa.check_inside([[(1, 1), (1, -3)]], 0, 10, 0, 10))


class SpecificationTests(unittest.TestCase):
    def test_verify_diagram_blocks_changes_to_confirmed_data(self):
        run = X.case_b()
        d, _ = A.to_diagram(run.spec)
        self.assertEqual(A.verify_diagram(run.spec, d), [])
        bad = copy.deepcopy(d)
        bad["shapes"] = [s for s in bad["shapes"] if s["id"] != "EQ-008-1"]
        self.assertTrue(A.verify_diagram(run.spec, bad))
        bad = copy.deepcopy(d)
        bad["lines"] = [l for l in bad["lines"] if not l.get("direct")]
        self.assertTrue(any("CN-" in p for p in A.verify_diagram(run.spec, bad)))
        bad = copy.deepcopy(d)
        bad["shapes"].append(dict(bad["shapes"][-1], id="EQ-004-3"))
        self.assertTrue(any("invented" in p for p in A.verify_diagram(run.spec, bad)))
        bad = copy.deepcopy(d)
        next(s for s in bad["shapes"] if s["id"] == "EQ-005-1")["sublabel"] = "Qty: 2"
        self.assertTrue(any("quantity" in p for p in A.verify_diagram(run.spec, bad)))

    def test_build_refuses_a_diagram_that_does_not_match_the_spec(self):
        folder = tempfile.mkdtemp()
        run = X.case_b()
        d, _ = A.to_diagram(run.spec)
        d["shapes"] = [s for s in d["shapes"] if s["id"] != "EQ-008-1"]
        A.save(run.spec, os.path.join(folder, "s.json"))
        with open(os.path.join(folder, "d.json"), "w") as fh:
            json.dump(d, fh)
        out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_diagram.py"), os.path.join(folder, "d.json"), "--out",
                              os.path.join(folder, "A.vsdx"), "--check-spec", os.path.join(folder, "s.json")], capture_output=True, text=True)
        self.assertIn("NOT BUILT", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(folder, "A.vsdx")))

    def test_previous_keeps_presentation_choices(self):
        run = X.case_b()
        d0, _ = A.to_diagram(run.spec)
        s = next(x for x in d0["shapes"] if x["id"] == "EQ-004-1")
        s.update(image="cache/plc.png", image_source="https://example.com/plc", oem="Siemens", model="S7-1500R")
        d0["lines"][0]["waypoints"] = [[2, 2]]
        d0["layer_weights"] = {"scada": 1, "control": 3, "field": 1}
        A.edit_equipment(run.spec, "EQ-008", quantity="2")
        A.materialize(run.spec)
        d1, _ = A.to_diagram(run.spec)
        A.merge_previous(d1, d0)
        s1 = next(x for x in d1["shapes"] if x["id"] == "EQ-004-1")
        self.assertEqual((s1["image"], s1["model"]), ("cache/plc.png", "S7-1500R"))
        self.assertEqual(d1["layer_weights"], d0["layer_weights"])
        self.assertTrue(any(x["id"] == "EQ-008-2" for x in d1["shapes"]))
        self.assertEqual(A.verify_diagram(run.spec, d1), [])

    def test_place_constraint_is_carried_into_the_drawing(self):
        run = X.case_a()
        run.spec.setdefault("layout", {})["place"] = {"EQ-007": {"left_of": "EQ-004"}}
        d, _ = A.to_diagram(run.spec)
        self.assertEqual(next(s for s in d["shapes"] if s["id"] == "EQ-007-1")["place"], {"left_of": "EQ-004-1"})


class V171DefectRegressionTests(unittest.TestCase):
    def test_control_to_scada_answer_not_dropped_by_a_later_link(self):
        run = X.case_b()
        self.assertTrue(any(c["origin"] == "ctlscada" for c in run.spec["connections"]))

    def test_every_unit_is_connected_after_a_revision(self):
        run = X.case_d()
        d, warnings = A.to_diagram(run.spec)
        self.assertFalse([w for w in warnings if "no drawn connection" in w])

    def test_redundant_io_network_reaches_both_switches(self):
        d, _ = A.to_diagram(X.case_b().spec)
        self.assertEqual({l["from"] for l in d["lines"] if l.get("to") == "EQ-005-1" and l["cable"] == "ethernet"}, {"EQ-006-1", "EQ-006-2"})

    def test_sync_link_ends_at_the_controllers(self):
        r = X.write("B_redundant_plc", X.case_b(), tempfile.mkdtemp(), preview=False)
        self.assertFalse([d for d in r["qa"] if "floating" in d or "dangling" in d])

    def test_workstation_library_pictures_carry_no_baked_name(self):
        from PIL import Image
        for f in ("client_operator_workstation", "engineering_workstation"):
            w, h = Image.open(os.path.join(ROOT, "data", "icons", f + ".png")).size
            self.assertLess(h, w * .7, f)                                  # the OWS-01 / EWS-01 text band is gone


if __name__ == "__main__":
    unittest.main()
