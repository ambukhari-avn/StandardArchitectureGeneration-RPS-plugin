"""Questionnaire / structured specification tests (Phases 2-6 and 6.4). Run:  python -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import arch_spec as A
import build_diagram as B

TEXT = {
    "L0": "Level 0:\nPressure Transmitters — 12\nTemperature Transmitters — 8\nFlow Transmitters — 6",
    "L1": "Redundant PLC Controllers — 2\nRemote I/O Racks — 4\nIndustrial Ethernet Switches — 2\nFO Patch Panels — 2",
    "L2": "SCADA Servers — 2 (redundant)\nOperator Workstations — 2\nEngineering Workstation — 1\nSCADA Switches x 2",
}
ANSWERS = [("instrument_to_control", "hardwired"), ("io_protocol", "profinet"), ("io_topology", "daisy"), ("io_medium", "copper"), ("io_display", "individual"),
           ("plc_sync:EQ-004", "dedicated"), ("plc_sync_paths:EQ-004", "2"), ("plc_sync_medium:EQ-004", "fibre"),
           ("plc_switch:EQ-004", "each_dedicated"), ("plc_switch_medium", "copper"), ("control_scada", "copper"),
           ("scada_homing", "dual"), ("scada_lan_medium", "copper"), ("fibre_topology", "p2p"),
           ("fo_panel_links:EQ-007", "na")]


def standard(layers=("L0", "L1", "L2")):
    s = A.new_spec()
    A.set_project(s, client="ACME", project="WTP", doc_name="PLC & SCADA Architecture", revision="R0")
    A.select_layers(s, list(layers))
    for k in ("L0", "L1", "L2"):
        if k in layers:
            A.add_equipment(s, k, TEXT[k])
    return s


def answered():
    s = standard()
    for k, v in ANSWERS:
        A.answer(s, k, v)
    return s


class ParsingTests(unittest.TestCase):
    def test_quantities_and_formats(self):
        for line, name, qty in [("Pressure Transmitters — 12", "Pressure Transmitters", 12), ("2 x SCADA Servers", "SCADA Servers", 2),
                                ("SCADA Switches x 2", "SCADA Switches", 2), ("Level switches 4 nos", "Level switches", 4),
                                ("Engineering Workstation: 1", "Engineering Workstation", 1), ("Qty 3 Printers", "Printers", 3)]:
            r = A.parse_line(line)
            self.assertEqual((r["name"], r["quantity"]), (name, qty), line)

    def test_missing_quantity_and_model_are_not_invented(self):
        r = A.parse_line("SCADA Server")
        self.assertIsNone(r["quantity"])
        self.assertIsNone(r["model"])
        self.assertIn("quantity not stated", A.equipment_flags(dict(r, category="server")))

    def test_model_numbers_are_not_quantities(self):
        r = A.parse_line("Siemens S7-1500R CPU 1513R-1 PN — 2 (redundant)")
        self.assertEqual((r["quantity"], r["oem"], r["model"], r["category"]), (2, "Siemens", "S7-1500R CPU 1513R-1 PN", "plc"))
        self.assertEqual(r["redundancy"], "Redundant pair")

    def test_oem_model_scope_location_interfaces(self):
        r = A.parse_line("Modbus gateway Moxa MGate 5105 in MCC Panel-1 | Interfaces: Modbus RTU, Modbus TCP")
        self.assertEqual((r["category"], r["oem"], r["model"], r["location"]), ("gateway", "Moxa", "MGate 5105", "MCC Panel-1"))
        self.assertEqual(r["interfaces"], ["Modbus RTU", "Modbus TCP"])
        self.assertTrue(A.parse_line("Pressure Transmitters — 12 (client scope)")["scope"].startswith("other"))

    def test_categories(self):
        for name, cat in [("Pressure switch", "instrument"), ("Industrial Ethernet Switch", "switch"), ("Remote I/O Rack", "io"),
                          ("FO Patch Panel", "fo_panel"), ("Hot standby PLC", "plc"), ("Historian Server", "historian"),
                          ("Engineering Workstation", "eng_workstation"), ("Operator Workstation", "workstation"), ("FortiGate firewall", "firewall")]:
            self.assertEqual(A.categorize(name), cat, name)

    def test_redundant_pair_is_one_system(self):
        s = standard()
        plc = A.eq(s, "EQ-004")
        self.assertEqual((plc["quantity"], plc["systems"]), (2, 1))
        self.assertEqual(A.eq(s, "EQ-005")["systems"], 4)

    def test_original_text_kept_ids_stable_and_no_duplicates(self):
        s = standard()
        self.assertEqual(A.eq(s, "EQ-001")["source_text"], "Pressure Transmitters — 12")
        added, dupes = A.add_equipment(s, "L0", "Pressure Transmitters — 12")
        self.assertEqual((added, dupes[0][1]), ([], "EQ-001"))
        A.remove_equipment(s, "EQ-002")
        added, _ = A.add_equipment(s, "L0", "Level Transmitters - 3")
        self.assertEqual(added[0]["id"], "EQ-012")                  # never reuses EQ-002


class LayerTests(unittest.TestCase):
    def test_any_combination_and_no_auto_layers(self):
        s = A.new_spec()
        A.select_layers(s, ["L0", "L1"])
        self.assertEqual([l["key"] for l in s["layers"]], ["L0", "L1"])
        A.select_layers(s, ["L1", "L2", "L3.5", "L4", "L5"], renames={"L1": "Control System"})
        self.assertEqual([l["id"] for l in s["layers"]], ["control", "scada", "dmz", "enterprise", "external"])
        self.assertEqual(A.layer(s, "L1")["name"], "Control System")
        self.assertEqual(A.layer(s, "L3.5")["level"], 3.5)

    def test_dmz_adds_no_equipment(self):
        s = A.new_spec()
        A.select_layers(s, ["L2", "L3.5"])
        self.assertEqual(s["equipment"], [])
        self.assertEqual(A.questions(s), [])

    def test_custom_layer_order_and_drawing(self):
        s = A.new_spec()
        A.select_layers(s, ["L0", "L1", "L2"], custom=[("2.5", "Utilities", "Power & water")])
        self.assertEqual([l["level"] for l in s["layers"]], [0, 1, 2, 2.5])
        A.add_equipment(s, "C1", "Power Meters - 3")
        d, _ = A.to_diagram(s)
        self.assertEqual(d["layers"][0], "custom_utilities")
        table = B.layer_table(d)
        self.assertEqual([t["id"] for t in table][:3], ["external", "enterprise", "dmz"])
        self.assertLess([t["id"] for t in table].index("custom_utilities"), [t["id"] for t in table].index("scada"))

    def test_layer_with_equipment_not_dropped_silently(self):
        s = standard()
        with self.assertRaises(A.SpecError):
            A.select_layers(s, ["L1", "L2"])


class QuestionTests(unittest.TestCase):
    def test_first_question_and_order(self):
        s = standard()
        self.assertEqual(A.questions(s)[0]["key"], "instrument_to_control")
        steps = [q["step"] for q in A.questions(s)]
        self.assertEqual(steps, sorted(steps))

    def test_only_relevant_questions(self):
        s = A.new_spec()
        A.select_layers(s, ["L0", "L1"])
        A.add_equipment(s, "L0", "Pressure Transmitters - 4")
        A.add_equipment(s, "L1", "PLC - 1")
        keys = [q["key"] for q in A.questions(s)]
        self.assertEqual(keys, ["instrument_to_control"])           # no I/O, sync, switch, SCADA or fibre questions

    def test_every_question_offers_other(self):
        for q in A.questions(standard()):
            self.assertIn(A.OTHER, [c["value"] for c in q["choices"]])

    def test_full_flow_completes(self):
        s = answered()
        self.assertEqual(A.questions(s), [])
        self.assertFalse([i for i in A.validate(s) if i["severity"] == "error"])
        kinds = {(c["source"], c["destination"]) for c in s["connections"]}
        self.assertIn(("EQ-004", "EQ-004"), kinds)                  # sync link on the redundant pair
        self.assertIn(("EQ-004", "EQ-005"), kinds)                  # PLC -> racks
        self.assertIn(("EQ-001", "EQ-005"), kinds)                  # hardwired instruments -> racks

    def test_topology_is_asked_not_assumed_from_protocol(self):
        s = standard()
        A.answer(s, "instrument_to_control", "hardwired")
        A.answer(s, "io_protocol", "profinet")
        self.assertEqual(A.questions(s)[0]["key"], "io_topology")
        self.assertFalse(any(c["destination"] == "EQ-005" and c["source"] == "EQ-004" for c in s["connections"]))

    def test_sync_link_count_not_assumed(self):
        s = standard()
        for k, v in ANSWERS[:6]:
            A.answer(s, k, v)
        self.assertEqual(A.questions(s)[0]["key"], "plc_sync_paths:EQ-004")

    def test_no_ring_unless_requested(self):
        s = answered()
        self.assertFalse(any(c.get("pattern") == "ring" for c in s["connections"]))
        d, _ = A.to_diagram(s)
        self.assertNotIn("rings", d)

    def test_mixed_instruments_asks_per_group(self):
        s = standard()
        A.answer(s, "instrument_to_control", "mixed")
        self.assertEqual([q["key"] for q in A.questions(s)][:3], ["instrument_method:EQ-001", "instrument_method:EQ-002", "instrument_method:EQ-003"])

    def test_fibre_instruments_need_an_interface(self):
        s = standard()
        A.answer(s, "instrument_to_control", "fibre_interface")
        q = A.questions(s)[0]
        self.assertTrue(q["key"].startswith("instrument_interface:"))
        self.assertIn("cannot connect directly to fiber", q["prompt"])

    def test_firewall_zones_from_project_layers_and_not_assumed(self):
        s = standard(("L0", "L1", "L2", "L3.5"))
        A.add_equipment(s, "L3.5", "Firewall - 1")
        q = [q for q in A.questions(s) if q["key"].startswith("firewall_zones")][0]
        self.assertEqual({c["value"] for c in q["choices"]} - {A.OTHER}, {"L0", "L1", "L2", "L3.5"})
        with self.assertRaises(A.SpecError):
            A.answer(s, q["key"], "L2")                             # a firewall connects two zones

    def test_manual_connection_resolves_question(self):
        s = standard()
        for e in ("EQ-001", "EQ-002", "EQ-003"):
            A.connect(s, source=e, destination="EQ-005", protocol="hardwired", medium="Copper (hardwired)")
        self.assertNotIn("instrument_to_control", [q["key"] for q in A.questions(s)])

    def test_bad_choice_rejected(self):
        with self.assertRaises(A.SpecError):
            A.answer(standard(), "instrument_to_control", "wifi")


class ValidationTests(unittest.TestCase):
    def test_protocol_medium_topology_redundancy_not_interchangeable(self):
        s = standard()
        c = A.connect(s, source="EQ-004", destination="EQ-005", protocol="Star", medium="PROFINET")
        msgs = [i["message"] for i in A.validate(s) if i["where"] == c["id"]]
        self.assertTrue(any("is a topology, not a protocol" in m for m in msgs))
        self.assertTrue(any("is a protocol, not a medium" in m for m in msgs))
        self.assertEqual(c["protocol"], "Star")                     # flagged, not silently replaced

    def test_incompatible_combinations(self):
        s = standard()
        a = A.connect(s, source="EQ-004", destination="EQ-005", protocol="PROFINET", medium="RS-485")
        b = A.connect(s, source="EQ-004", destination="EQ-006", protocol="Modbus RTU", medium="Copper Ethernet")
        c = A.connect(s, source="EQ-001", destination="EQ-005", protocol="Hardwired", medium="Fiber optic")
        err = {i["where"] for i in A.validate(s) if i["severity"] == "error"}
        self.assertTrue({a["id"], b["id"], c["id"]} <= err)

    def test_cable_types_follow_standard(self):
        self.assertEqual(A.cable_type({"protocol": "Modbus RTU", "medium": "RS-485"})[0], "modbus")
        self.assertEqual(A.cable_type({"protocol": "Modbus TCP", "medium": "Copper Ethernet"})[0], "ethernet")
        self.assertIsNone(A.cable_type({"protocol": "PROFIBUS DP", "medium": "RS-485"})[0])
        self.assertIsNone(A.cable_type({"protocol": None, "medium": None})[0])


class RequestTests(unittest.TestCase):
    def test_round_trip_has_no_differences(self):
        s = answered()
        self.assertEqual(A.parse_request(s, A.request_text(s)), [])

    def test_manual_edits_are_parsed_back(self):
        s = answered()
        text = A.request_text(s)
        text = text.replace("Checked By: TBC", "Checked By: QA Lead")
        text = text.replace("[EQ-005] Remote I/O Racks | Qty: 4", "[EQ-005] Remote I/O Racks | Qty: 6")
        text = text.replace("## Notes\n", "## Notes\n- Panel layout per client drawing\n")
        text = "\n".join(l for l in text.splitlines() if "[EQ-010]" not in l) + "\n"
        text = text.replace("### [L0] Field Instruments\n", "### [L0] Field Instruments\n- Level Transmitters | Qty: 3\n")
        ch = A.parse_request(s, text)
        kinds = sorted(c["kind"] for c in ch)
        self.assertIn("project", kinds)
        self.assertIn("equipment-edit", kinds)
        self.assertIn("equipment-remove", kinds)
        self.assertIn("equipment-add", kinds)
        self.assertIn("notes", kinds)
        A.apply_changes(s, ch)
        self.assertEqual(A.eq(s, "EQ-005")["quantity"], 6)
        self.assertEqual(s["project"]["checked_by"], "QA Lead")
        self.assertFalse(any(e["id"] == "EQ-010" for e in s["equipment"]))
        self.assertEqual(A.parse_request(s, A.request_text(s)), [])

    def test_cli_refuses_to_overwrite_edited_request(self):
        d = tempfile.mkdtemp()
        spec, req = os.path.join(d, "s.json"), os.path.join(d, "r.md")
        A.save(answered(), spec)
        self.assertEqual(A.main(["request", spec, "--out", req]), 0)
        with open(req, "a", encoding="utf-8") as fh:
            fh.write("- extra note\n")
        self.assertEqual(A.main(["request", spec, "--out", req]), 2)


class DiagramTests(unittest.TestCase):
    def build(self, spec):
        d, warnings = A.to_diagram(spec)
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "d.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        out = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "build_diagram.py"), path, "--out",
                              os.path.join(folder, "A.vsdx")], capture_output=True, text=True)
        self.assertIn("built", out.stdout + out.stderr, out.stdout + out.stderr)
        return d

    def test_generated_diagram_builds(self):
        d = self.build(answered())
        self.assertEqual(d["layers"], ["scada", "control", "field"])
        self.assertEqual(d["project"]["client"], "ACME")
        ids = {s["id"] for s in d["shapes"]}
        self.assertTrue({"EQ-004-1", "EQ-004-2", "EQ-005-4"} <= ids)
        self.assertTrue(any(l.get("chain") for l in d["lines"]))
        self.assertTrue(any(l.get("direct") and "Redundancy Sync" in l.get("label", "") for l in d["lines"]))
        hw = [l for l in d["lines"] if l["cable"] == "hardwired"]
        self.assertTrue(hw and all(l["label"] == A.TYPICAL_HW for l in hw))

    def test_instruments_one_picture_per_type(self):
        d, _ = A.to_diagram(answered())
        pt = [s for s in d["shapes"] if s["id"].startswith("EQ-001")]
        self.assertEqual(len(pt), 1)
        self.assertEqual(pt[0]["sublabel"], "(Qty 12)")

    def test_unconfirmed_medium_is_not_drawn(self):
        s = answered()
        A.connect(s, source="EQ-009", destination="EQ-008", protocol="OPC UA")
        d, warnings = A.to_diagram(s)
        self.assertTrue(any("not drawn" in w for w in warnings))


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.s = answered()
        self.s["baseline"] = A.snapshot(self.s)
        self.s["baseline_revision"] = "R0"

    def test_remove_equipment_only_affects_its_connections(self):
        before = {c["id"] for c in self.s["connections"]}
        gone = A.remove_equipment(self.s, "EQ-010")
        A.materialize(self.s)
        ch = A.changes_since_baseline(self.s)
        self.assertEqual(ch["equipment"]["removed"], ["EQ-010"])
        self.assertEqual(ch["equipment"]["changed"], [])
        self.assertEqual(set(ch["connections"]["removed"]), set(gone))
        self.assertEqual({c["id"] for c in self.s["connections"]}, before - set(gone))

    def test_simplex_to_redundant_asks_sync(self):
        s = standard()
        A.edit_equipment(s, "EQ-004", redundancy="-", quantity="1")
        for k, v in ANSWERS:
            if not k.startswith("plc_sync"):
                try:
                    A.answer(s, k, v)
                except A.SpecError:
                    pass
        self.assertFalse(any(q["key"].startswith("plc_sync") for q in A.questions(s)))
        A.edit_equipment(s, "EQ-004", redundancy="Redundant pair", quantity="2")
        self.assertTrue(A.questions(s)[0]["key"].startswith("plc_sync:EQ-004"))

    def test_change_io_to_daisy_chain_keeps_ids(self):
        s = A.new_spec()
        A.select_layers(s, ["L0", "L1", "L2"])
        for k in ("L0", "L1", "L2"):
            A.add_equipment(s, k, TEXT[k])
        for k, v in ANSWERS:
            if k == "io_display":
                continue                                    # a star needs no simplified-display choice
            A.answer(s, k, "star" if k == "io_topology" else v)
            if k == "io_medium":
                A.answer(s, "io_star_hub", "EQ-006")
        io = [c for c in s["connections"] if c["origin"] == "io:EQ-005"][0]
        A.answer(s, "io_topology", "daisy")
        io2 = [c for c in s["connections"] if c["origin"] == "io:EQ-005"][0]
        self.assertEqual(io["id"], io2["id"])
        self.assertEqual((io2["topology"], io2["source"]), ("Daisy-chain", "EQ-004"))

    def test_add_servers_and_move_firewall(self):
        A.edit_equipment(self.s, "EQ-008", quantity="4")
        A.select_layers(self.s, ["L0", "L1", "L2", "L3.5"])
        A.add_equipment(self.s, "L2", "Firewall - 1")
        A.edit_equipment(self.s, "EQ-012", layer="L3.5")
        ch = A.changes_since_baseline(self.s)
        self.assertEqual([c["id"] for c in ch["equipment"]["changed"]], ["EQ-008"])
        self.assertEqual(ch["equipment"]["added"], ["EQ-012"])
        self.assertEqual(A.eq(self.s, "EQ-012")["layer"], "L3.5")
        self.assertEqual(ch["unchanged_equipment"], 10)

    def test_manual_connection_edit_survives_new_answers(self):
        cid = [c for c in self.s["connections"] if c["origin"] == "ctlscada"][0]["id"]
        A.edit_connection(self.s, cid, label="Uplink")
        A.answer(self.s, "control_scada", "fibre")
        c = [c for c in self.s["connections"] if c["id"] == cid][0]
        self.assertEqual((c["label"], c["medium"]), ("Uplink", "Copper Ethernet"))


if __name__ == "__main__":
    unittest.main()
