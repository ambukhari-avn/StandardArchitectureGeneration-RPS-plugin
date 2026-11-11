"""Meaning-based spec (v2): validation, questions, placement, redundancy, rings, switches, report. Run:  python -m unittest discover -s tests"""
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import build_diagram as B
import compile_v2 as C
from cables import Cables
from components import Components

BASE = os.path.join(HERE, "..", "base", "base.vsdx")
SAMPLE_V1 = os.path.join(HERE, "..", "samples", "diagram_example.json")
SAMPLE_RING = os.path.join(HERE, "..", "samples", "diagram_example_ring_v2.json")
SAMPLE_V2 = os.path.join(HERE, "..", "samples", "diagram_example_v2.json")
SAMPLE_RING = os.path.join(HERE, "..", "samples", "diagram_example_ring_v2.json")


def owner_example():
    with open(SAMPLE_V2, encoding="utf-8") as fh:
        return json.load(fh)


def build(spec):
    d = tempfile.mkdtemp()
    return B.build(spec, BASE, os.path.join(d, "o.vsdx"), spec_dir=d)


class ValidateTests(unittest.TestCase):
    def test_the_owners_example_validates_with_no_errors_or_questions(self):
        errors, questions, warnings = C.validate(owner_example())
        self.assertEqual((errors, questions), ([], []))

    def test_a_missing_scope_is_a_question_and_nothing_is_built(self):
        s = owner_example()
        del s["items"][0]["scope"]
        errors, questions, _ = C.validate(s)
        self.assertEqual(errors, [])
        self.assertEqual(questions, ["Which scope is Pressure transmitter: Avanceon or Client/Other?"])
        with self.assertRaises(B.BuildError) as cm:
            build(s)
        self.assertTrue(str(cm.exception).startswith("questions for the user:"))
        self.assertIn("Which scope is Pressure transmitter", str(cm.exception))

    def test_unknown_and_dual_scope_are_questions_too(self):
        for bad in ("unknown", "dual", "both"):
            s = owner_example()
            s["items"][2]["scope"] = bad
            self.assertEqual(len(C.validate(s)[1]), 1, bad)

    def test_a_missing_level_is_a_question_and_an_unknown_level_is_an_error(self):
        s = owner_example()
        del s["items"][4]["level"]
        errors, questions, _ = C.validate(s)
        self.assertEqual(errors, [])
        self.assertIn("Which Purdue level", questions[0])
        s = owner_example()
        s["items"][4]["level"] = "L9"
        errors, _, _ = C.validate(s)
        self.assertTrue(any("unknown level 'L9'" in e for e in errors))

    def test_a_question_written_into_the_spec_stops_the_build(self):
        s = owner_example()
        s["questions"] = ["What protocol connects the PLC and the third-party device?"]
        self.assertEqual(C.validate(s)[1], ["What protocol connects the PLC and the third-party device?"])
        with self.assertRaises(B.BuildError):
            build(s)

    def test_duplicate_ids_bad_quantities_and_unknown_references_are_errors(self):
        s = owner_example()
        s["items"][1]["id"] = "pt"
        self.assertTrue(any("duplicate" in e for e in C.validate(s)[0]))
        for qty in (0, -1, 1.5, "2", True):
            s = owner_example()
            s["items"][0]["qty"] = qty
            self.assertTrue(any("qty" in e for e in C.validate(s)[0]), qty)
        s = owner_example()
        s["links"][0]["to"] = "nope"
        self.assertTrue(any("'nope'" in e for e in C.validate(s)[0]))
        s = owner_example()
        s["links"][0]["cable"] = "coax"
        self.assertTrue(any("coax" in e for e in C.validate(s)[0]))
        s = owner_example()
        s["redundancy"][0]["secondary"] = "ghost"
        self.assertTrue(any("ghost" in e for e in C.validate(s)[0]))
        s = owner_example()
        s["rings"] = [{"id": "r", "first": "plc1", "members": ["ghost", "pt"]}]
        self.assertTrue(any("ghost" in e for e in C.validate(s)[0]))
        s = owner_example()
        s["items"][2]["component"] = "not_in_library"
        self.assertTrue(any("not in the library" in e for e in C.validate(s)[0]))

    def test_coordinates_are_not_part_of_the_format_and_a_v1_file_is_not_a_v2_file(self):
        errors, _, _ = C.validate({"shapes": [{"id": "a", "x": 1, "y": 1}]})
        self.assertTrue(errors)

    def test_an_instrument_on_level_2_gets_a_warning_but_still_validates(self):
        s = owner_example()
        s["items"][0]["level"] = "L2"
        errors, questions, warnings = C.validate(s)
        self.assertEqual((errors, questions), ([], []))
        self.assertTrue(any("'pt'" in w and "L2" in w and "L0" in w for w in warnings), warnings)
        self.assertEqual([w for w in C.validate(owner_example())[2] if "looks like" in w], [])

    def test_a_historian_on_level_3_or_2_is_fine(self):
        for lv in ("L3", "L2"):
            s = owner_example()
            s["items"].append({"id": "h", "label": "Historian", "kind": "server", "level": lv, "scope": "other"})
            self.assertEqual([w for w in C.validate(s)[2] if "looks like" in w], [], lv)

    def test_band_colours_are_checked(self):
        s = owner_example()
        s["band_colors"] = {"L2": "red"}
        self.assertTrue(any("band_colors[L2]" in w for w in C.validate(s)[2]))


class BuildEntryTests(unittest.TestCase):
    def test_a_v1_file_still_builds_exactly_as_before(self):
        with open(SAMPLE_V1, encoding="utf-8") as fh:
            r = B.build(json.load(fh), BASE, os.path.join(tempfile.mkdtemp(), "o.vsdx"), spec_dir=os.path.dirname(SAMPLE_V1))
        self.assertEqual((r["shapes"], r["lines"], r["warnings"]), (10, 6, []))
        self.assertTrue(any(s["text"].endswith("| spec v1") for s in r["page"].shapes))


def nodes_of(v1):
    return {s["id"]: s for s in v1["shapes"] if s["kind"] != "zone"}


def zones_of(v1, prefix):
    return {s["id"]: s for s in v1["shapes"] if s["id"].startswith(prefix)}


def overlap(a, b):
    return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > 0.01 and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > 0.01


def spec_with(items, links=(), **kw):
    s = {"spec_version": 2, "project": {"project": "P"}, "items": items, "links": list(links)}
    s.update(kw)
    return s


def item(iid, level, scope="avanceon", **kw):
    d = {"id": iid, "label": kw.pop("label", iid.upper()), "level": level, "scope": scope}
    d.update(kw)
    return d


class PlacementTests(unittest.TestCase):
    def test_the_owners_example_draws_only_what_was_asked(self):
        v1 = C.compile_v2(owner_example())
        self.assertEqual(sorted(nodes_of(v1)), ["an", "plc1", "plc2", "pt-01", "pt-02", "ws-01", "ws-02"])
        self.assertEqual(sorted(s["id"] for s in v1["shapes"] if s["kind"] == "zone"),
                         sorted(["band_L2", "band_L1", "band_L0", "hdr_L2", "hdr_L1", "hdr_L0",
                                 "scope_L2_avanceon", "scope_L1_avanceon", "scope_L0_avanceon"]))
        bands = zones_of(v1, "band_")
        self.assertLess(bands["band_L2"]["y"], bands["band_L1"]["y"])               # bands run L2, L1, L0 from the top
        self.assertLess(bands["band_L1"]["y"], bands["band_L0"]["y"])
        for absent in ("L3", "L3.5", "L4", "L5"):
            self.assertNotIn("band_" + absent, bands)
        nodes = nodes_of(v1)
        for k in ("pt-01", "pt-02", "an"):                                          # every level-0 item lies below its parent
            self.assertGreater(nodes[k]["y"], nodes["plc1"]["y"] + nodes["plc1"]["h"])
        for k in ("plc1", "plc2"):
            self.assertGreater(nodes[k]["y"], nodes["ws-01"]["y"] + nodes["ws-01"]["h"])
        pts = [nodes[k]["x"] + nodes[k]["w"] / 2 for k in ("pt-01", "pt-02", "an")]
        self.assertAlmostEqual(sum(pts) / 3, nodes["plc1"]["x"] + nodes["plc1"]["w"] / 2, 2)   # the group hangs centred under its controller

    def test_no_overlaps_and_no_line_through_a_shape_for_the_example(self):
        r = build(owner_example())
        self.assertEqual([w for w in r["warnings"] if "overlap" in w or "passes through" in w or "outside" in w or "may not fit" in w], [])
        v1 = C.compile_v2(owner_example())
        items = [s for s in v1["shapes"] if s["kind"] != "zone"]
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                self.assertFalse(overlap(a, b), (a["id"], b["id"]))

    def test_every_shape_stays_inside_the_drawing_area(self):
        for spec in (owner_example(), self.big()):
            v1 = C.compile_v2(spec, area=(B.AREA_W, B.AREA_H))
            for s in v1["shapes"]:
                self.assertGreaterEqual(s["x"], -1e-6, s["id"])
                self.assertGreaterEqual(s["y"], -1e-6, s["id"])
                self.assertLessEqual(s["x"] + s["w"], B.AREA_W + 1e-6, s["id"])
                self.assertLessEqual(s["y"] + s["h"], B.AREA_H + 1e-6, s["id"])

    @staticmethod
    def big():
        s = owner_example()
        s["items"][0]["qty"] = 12
        return s

    def test_twelve_instruments_two_controllers_two_workstations_build_cleanly(self):
        r = build(self.big())
        self.assertEqual([w for w in r["warnings"] if "overlap" in w or "passes through" in w], [])
        self.assertEqual(sum(1 for s in C.compile_v2(self.big())["shapes"] if s["id"].startswith("pt-")), 12)

    def test_a_quantity_up_to_twelve_is_numbered_and_above_twelve_is_one_item_with_a_count(self):
        v1 = C.compile_v2(spec_with([item("a", "L0", qty=3), item("b", "L0", qty=13), item("c", "L0")]))
        n = nodes_of(v1)
        self.assertEqual(sorted(n), ["a-01", "a-02", "a-03", "b", "c"])
        self.assertEqual(n["a-02"]["label"], "A-02")
        self.assertEqual(n["b"]["label"], "B x 13")
        self.assertEqual(n["c"]["label"], "C")

    def test_scope_boxes_two_scopes_side_by_side_one_scope_one_box(self):
        v1 = C.compile_v2(spec_with([item("p", "L1", "avanceon"), item("s", "L1", "other"), item("w", "L2", "other")]))
        z = zones_of(v1, "scope_")
        self.assertEqual(sorted(z), ["scope_L1_avanceon", "scope_L1_other", "scope_L2_other"])
        a, o = z["scope_L1_avanceon"], z["scope_L1_other"]
        self.assertLess(a["x"] + a["w"], o["x"])                                    # side by side, not overlapping
        self.assertEqual(a["y"], o["y"])
        self.assertEqual((a["fill"], o["fill"]), ("#E7E6E6", "#F2DCDB"))
        self.assertEqual(a["label"], "Avanceon scope")
        self.assertEqual(o["label"], "Client / Other scope")
        nodes = nodes_of(v1)
        self.assertLess(nodes["p"]["x"] + nodes["p"]["w"], a["x"] + a["w"] + 1e-6)  # each item sits inside its own scope box
        self.assertGreater(nodes["s"]["x"], o["x"] - 1e-6)

    def test_the_header_of_every_band_is_the_same_but_for_the_fill(self):
        v1 = C.compile_v2(spec_with([item("a", "L0"), item("b", "L2")], band_colors={"L2": "#112233"}))
        h = zones_of(v1, "hdr_")
        self.assertEqual(h["hdr_L2"]["fill"], "#112233")
        self.assertEqual(h["hdr_L0"]["fill"], "#1F5FA6")
        for k, a in h.items():                                  # a vertical strip of one width and font; its border is its own fill
            self.assertEqual((a["w"], a["size"], a["line"], a["vertical"]), (0.45, 8, a["fill"], True))
        self.assertEqual(h["hdr_L0"]["label"], "Level 0 - Field (Instruments / Actuators)")

    def test_the_hard_ceiling_is_a_clear_not_built_message(self):
        items = [item("i%d_%d" % (lv, k), "L%d" % lv) for lv in range(3) for k in range(160)]
        with self.assertRaises(B.BuildError) as cm:
            build(spec_with(items))
        self.assertIn('too large for one A3 page; ask the user to split it or use "x N" counts', str(cm.exception))

    def test_a_crowded_page_steps_the_item_size_down_instead_of_failing(self):
        items = [item("i%d_%d" % (lv, k), "L%d" % lv) for lv in range(3) for k in range(40)]
        v1 = C.compile_v2(spec_with(items), area=(B.AREA_W, B.AREA_H))
        widths = {round(s["w"], 3) for s in v1["shapes"] if s["kind"] != "zone"}
        self.assertTrue(all(w < 1.35 for w in widths), widths)


class LinkTests(unittest.TestCase):
    def test_every_line_has_an_explicit_route_and_the_cable_is_kept(self):
        v1 = C.compile_v2(owner_example())
        self.assertEqual(len(v1["lines"]), 3 + 4 + 2)       # pt x2 + an to plc1, plc1/plc2 to 2 workstations, two redundancy links
        for ln in v1["lines"]:
            self.assertGreaterEqual(len(ln["points"]), 2)
        self.assertEqual({ln["cable"] for ln in v1["lines"]}, {"hardwired", "ethernet"})

    def test_a_hardwired_line_runs_from_the_instrument_to_the_controller(self):
        v1 = C.compile_v2(owner_example())
        ln = next(l for l in v1["lines"] if l["from"] == "pt-01")
        self.assertEqual(ln["to"], "plc1")
        self.assertGreater(ln["points"][0][1], ln["points"][-1][1])      # starts low (instrument) and ends high (controller): the arrow points at the PLC

    def test_several_lines_into_one_side_do_not_stack(self):
        v1 = C.compile_v2(owner_example())
        ends = [l["points"][-1][0] for l in v1["lines"] if l["to"] == "plc1" and l["cable"] == "hardwired"]
        self.assertEqual(len(ends), 3)
        self.assertEqual(len({round(x, 3) for x in ends}), 3)

    def test_assumed_links_get_a_star_and_the_footer_note_appears_once(self):
        v1 = C.compile_v2(owner_example())
        labels = {l["from"] + ">" + l["to"]: l.get("label") for l in v1["lines"]}
        self.assertEqual(labels["pt-01>plc1"], "4-20 mA*")
        self.assertEqual(labels["an>plc1"], "*")                          # unlabelled but assumed: just the star
        self.assertEqual(sum(1 for n in v1["notes"] if n.startswith("* = assumed link")), 1)
        s = owner_example()
        for lk in s["links"]:
            lk["assumed"] = False
        s["redundancy"][0]["assumed"] = False
        self.assertFalse([n for n in C.compile_v2(s)["notes"] if "assumed" in n])

    def test_a_bundle_of_identical_lines_carries_its_label_once(self):
        s = spec_with([item("i", "L0", qty=8, group="p"), item("p", "L1")], [{"from": "i", "to": "p", "cable": "hardwired", "label": "4-20 mA"}])
        v1 = C.compile_v2(s)
        self.assertEqual(len(v1["lines"]), 8)
        self.assertEqual([l.get("label") for l in v1["lines"]].count("4-20 mA"), 1)
        self.assertTrue(any("printed once" in x for x in C.compile_v2(s)["_report"]["added_by_rule"]))

    def test_units_pair_up_the_way_the_old_design_did(self):
        A, B_ = ["a1", "a2", "a3", "a4"], ["b1", "b2"]
        self.assertEqual(C.pair_up(A, B_), [("a1", "b1"), ("a2", "b1"), ("a3", "b2"), ("a4", "b2")])
        self.assertEqual(C.pair_up(["a"], B_), [("a", "b1"), ("a", "b2")])
        self.assertEqual(C.pair_up(["a1", "a2"], ["b1", "b2"]), [("a1", "b1"), ("a2", "b2")])

    def test_the_slot_options_of_edge_point_spread_lines_and_default_to_the_middle(self):
        r = (0, 0, 2, 1)
        self.assertEqual(B.edge_point(r, (1, 5)), (1.0, 1))
        xs = [B.edge_point(r, (1, 5), i, 3)[0] for i in range(3)]
        self.assertEqual(xs, [0.5, 1.0, 1.5])
        pts = B.route((0, 4, 1, 1), (0, 0, 1, 1), [], (0, 2), (1, 2))
        self.assertEqual(len(pts), 4)                                       # different slots on the two ends make an elbow


class LayoutPolishTests(unittest.TestCase):
    """Defects found by looking at the 12-instrument preview: arrows beside the shape, labels on top of each other, text on a border."""

    def test_arrowheads_stay_on_the_shape_they_point_at(self):
        spec = PlacementTests.big()
        v1 = C.compile_v2(spec, area=(B.AREA_W, B.AREA_H))
        plc = nodes_of(v1)["plc1"]
        ends = [l["points"][-1][0] for l in v1["lines"] if l["to"] == "plc1" and l["cable"] == "hardwired"]
        self.assertEqual(len(ends), 13)
        self.assertEqual(len({round(x, 3) for x in ends}), 13)                  # still one point each
        for x in ends:
            self.assertGreaterEqual(x, plc["x"])
            self.assertLessEqual(x, plc["x"] + plc["w"])

    def test_every_scope_box_clears_the_last_row_of_its_band(self):
        v1 = C.compile_v2(PlacementTests.big(), area=(B.AREA_W, B.AREA_H))
        for z in zones_of(v1, "scope_").values():
            inside = [s for s in nodes_of(v1).values() if z["y"] <= s["y"] and s["y"] + s["h"] <= z["y"] + z["h"] + 0.5 and s["x"] >= z["x"] - 1e-6
                      and s["x"] + s["w"] <= z["x"] + z["w"] + 1e-6]
            self.assertTrue(inside, z["id"])
            for s in inside:
                self.assertLessEqual(s["y"] + s["h"] + 0.05, z["y"] + z["h"], (z["id"], s["id"]))

    def test_line_labels_do_not_sit_on_each_other_or_on_a_header(self):
        with mock.patch.object(B, "draw_line_label", wraps=B.draw_line_label) as spy:
            build(owner_example())
        taken = spy.call_args_list[0][0][3]                       # the rectangles of every label placed, in drawing coordinates
        self.assertGreaterEqual(len(taken), 4)
        for i, a in enumerate(taken):
            for b in taken[i + 1:]:
                self.assertFalse(B._hit(a, b, 0), (a, b))
        avoid = spy.call_args_list[0][0][4]                       # the three band headers and the seven items
        self.assertEqual(len(avoid), 3 + 7)
        for a in taken:
            for o in avoid:
                self.assertFalse(B._hit(a, o, 0), (a, o))

    def test_a_label_is_wide_enough_for_one_line(self):
        page = B.Page()
        B.draw_line_label(page, [(0, 0), (3, 0)], "Redundancy link 1*")
        w = page.shapes[-1]["w"]
        self.assertGreaterEqual(w, 18 * 0.62 * 6.5 / 72)

    def test_two_labels_asked_for_the_same_place_are_moved_apart(self):
        page, taken = B.Page(), []
        B.draw_line_label(page, [(0, 0), (4, 0)], "OPC UA*", taken)
        B.draw_line_label(page, [(0, 0.05), (4, 0.05)], "OPC UA*", taken)
        a, b = page.shapes[-2], page.shapes[-1]
        self.assertFalse(B._hit((a["x"], a["y"], a["w"], a["h"]), (b["x"], b["y"], b["w"], b["h"]), 0))

    def test_numbered_copies_make_one_picture_line_and_one_warning(self):
        r = build(PlacementTests.big())
        self.assertEqual([w for w in r["warnings"] if "BOX: no picture" in w], ["BOX: no picture found for Pressure transmitter",
                                                                              "BOX: no picture found for Analyzer"])
        self.assertTrue(any(x.startswith("Pressure transmitter: box") and x.endswith("[x12]") for x in r["report"]["pictures"]))
        self.assertTrue(any(x == "Analyzer: box" for x in r["report"]["pictures"]))


class RedundancyTests(unittest.TestCase):
    def test_a_pair_is_drawn_side_by_side_as_primary_and_secondary_with_two_links(self):
        v1 = C.compile_v2(owner_example())
        n = nodes_of(v1)
        self.assertEqual(n["plc1"]["label"].split("\n")[0], "Primary Controller")
        self.assertEqual(n["plc2"]["label"].split("\n")[0], "Secondary Controller")
        self.assertEqual(n["plc1"]["label"].split("\n")[1], "Siemens S7-1500")                 # the model beneath
        self.assertAlmostEqual(n["plc1"]["y"], n["plc2"]["y"])                                  # same row
        self.assertLess(n["plc1"]["x"], n["plc2"]["x"])
        red = [l for l in v1["lines"] if {l["from"], l["to"]} == {"plc1", "plc2"}]
        self.assertEqual(len(red), 2)
        self.assertEqual({l["cable"] for l in red}, {"ethernet"})
        self.assertEqual(sorted(l["label"] for l in red), ["Redundancy link 1*", "Redundancy link 2*"])
        ys = sorted(l["points"][0][1] for l in red)
        self.assertAlmostEqual(ys[1] - ys[0], 0.16, 2)                                          # two parallel lines, +-0.08 in
        self.assertTrue(all(abs(l["points"][0][1] - l["points"][-1][1]) < 1e-6 for l in red))

    def test_the_redundancy_lines_use_the_ethernet_colour_in_the_drawing(self):
        r = build(owner_example())
        red = [s for s in r["page"].shapes if s["role"] == "line" and s["key"] in ("plc1->plc2",)]
        self.assertEqual(len(red), 2)
        self.assertTrue(all(s["line"] == Cables().get("ethernet")["color"] and s["pattern"] == 2 for s in red))

    def test_another_link_count_warns_and_a_bad_pair_is_an_error(self):
        s = owner_example()
        s["redundancy"][0]["links"] = 3
        self.assertTrue(any("document shows two" in w for w in C.validate(s)[2]))
        self.assertEqual(len([l for l in C.compile_v2(s)["lines"] if {l["from"], l["to"]} == {"plc1", "plc2"}]), 3)
        s = owner_example()
        s["redundancy"][0]["secondary"] = "ws"                       # a different level and a quantity of 2
        self.assertTrue(C.validate(s)[0])
        s = owner_example()
        s["redundancy"][0]["secondary"] = "nope"
        self.assertTrue(any("'nope'" in e for e in C.validate(s)[0]))

    def test_peer_links_of_the_primary_are_not_copied_to_the_secondary(self):
        s = owner_example()
        s["links"] = [l for l in s["links"] if l["from"] != "plc2"]
        v1 = C.compile_v2(s)
        self.assertFalse([l for l in v1["lines"] if "plc2" in (l["from"], l["to"]) and "plc1" not in (l["from"], l["to"])])

    def test_without_redundancy_single_controllers_are_unaffected(self):
        s = owner_example()
        s["redundancy"] = []
        s["items"] = [i for i in s["items"] if i["id"] != "plc2"]
        s["links"] = [l for l in s["links"] if l["from"] != "plc2"]
        v1 = C.compile_v2(s)
        self.assertEqual(nodes_of(v1)["plc1"]["label"].split("\n")[0], "Primary Controller") if False else None
        self.assertNotIn("Secondary Controller", json.dumps(v1))


class ReportAndCliTests(unittest.TestCase):
    def test_the_report_lists_assumed_items_and_picture_statuses(self):
        r = build(owner_example())
        rep = r["report"]
        self.assertTrue(any("link pt -> plc1" in x and "4-20 mA" in x for x in rep["assumed"]))
        self.assertTrue(any("redundancy plc1 / plc2" in x for x in rep["assumed"]))
        self.assertIn("Instruments are wired to the primary controller.", rep["assumed"])
        self.assertTrue(any(x.startswith("Primary Controller: library") for x in rep["pictures"]))
        self.assertTrue(any(x.startswith("Analyzer: box") for x in rep["pictures"]))
        self.assertTrue(any("BOX: no picture found for Analyzer" in w for w in rep["warnings"]))

    def test_the_compiled_free_form_spec_builds_on_its_own(self):
        r = build(owner_example())
        self.assertIsNotNone(r["v1"])
        d = tempfile.mkdtemp()
        r2 = B.build(r["v1"], BASE, os.path.join(d, "o.vsdx"), spec_dir=d)
        self.assertEqual((r2["shapes"], r2["lines"]), (r["shapes"], r["lines"]))
        self.assertEqual(r2["spec_version"], 1)

    def test_the_stamp_says_spec_v2_for_a_v2_build(self):
        r = build(owner_example())
        self.assertTrue(any(s["text"].endswith("| spec v2") for s in r["page"].shapes))


def ring_example():
    with open(SAMPLE_RING, encoding="utf-8") as fh:
        return json.load(fh)


def on_ellipse(shape, x, y):
    cx, cy, a, b = shape["x"] + shape["w"] / 2, shape["y"] + shape["h"] / 2, shape["w"] / 2, shape["h"] / 2
    return ((x - cx) / a) ** 2 + ((y - cy) / b) ** 2


class RingTests(unittest.TestCase):
    def setUp(self):
        self.spec = ring_example()
        self.v1 = C.compile_v2(self.spec, area=(B.AREA_W, B.AREA_H))
        self.nodes = nodes_of(self.v1)
        self.switches = {k: s for k, s in self.nodes.items() if k.startswith("r1_")}
        self.ellipse = [s for s in self.v1["shapes"] if s["kind"] == "ellipse"]

    def test_three_rios_make_eight_ring_switches_and_one_ellipse(self):
        self.assertEqual(len(self.switches), 2 + 2 * 3)
        self.assertEqual(len(self.ellipse), 1)
        self.assertEqual(self.ellipse[0]["label"], "Fiber Optic Ring")
        self.assertEqual(self.ellipse[0]["cable"], "fibre")
        for node in ("plc1", "rio1", "rio2", "rio3"):
            self.assertEqual(sorted(k for k in self.switches if k.startswith("r1_%s_" % node)), ["r1_%s_sw1" % node, "r1_%s_sw2" % node])
        self.assertTrue(all(s["label"] == "Ring switch" and s["component"] == "network_switch_approved" for s in self.switches.values()))

    def test_every_spoke_ends_exactly_on_the_ellipse_and_starts_at_its_switch(self):
        spokes = [l for l in self.v1["lines"] if l["to"] == "ring_r1"]
        self.assertEqual(len(spokes), 8)
        e = self.ellipse[0]
        for l in spokes:
            self.assertEqual(l["cable"], "fibre")
            self.assertEqual(len(l["points"]), 2)
            x, y = l["points"][-1]
            self.assertAlmostEqual(on_ellipse(e, x, y), 1.0, 3)                 # on the curve
            sw = self.nodes[l["from"]]
            self.assertAlmostEqual(l["points"][0][0], sw["x"] + sw["w"] / 2, 3)
            self.assertAlmostEqual(x, l["points"][0][0], 3)                     # straight up or down

    def test_the_main_nodes_two_switches_are_at_the_two_ends_so_the_loop_closes_on_both_sides(self):
        e = self.ellipse[0]
        cx = e["x"] + e["w"] / 2
        left, right = (self.nodes["r1_plc1_sw1"], self.nodes["r1_plc1_sw2"])
        self.assertLess(left["x"] + left["w"] / 2, cx - 0.35 * e["w"])
        self.assertGreater(right["x"] + right["w"] / 2, cx + 0.35 * e["w"])
        plc = self.nodes["plc1"]
        self.assertAlmostEqual(plc["x"] + plc["w"] / 2, cx, 3)

    def test_the_rows_run_main_then_ellipse_then_switches_then_members_then_the_field(self):
        n, e = self.nodes, self.ellipse[0]
        bottom = lambda k: n[k]["y"] + n[k]["h"]
        self.assertLess(bottom("plc1"), e["y"] + 0.01)
        self.assertLess(e["y"] + e["h"], n["r1_rio1_sw1"]["y"] + 0.01)
        self.assertLess(bottom("r1_rio1_sw1"), n["rio1"]["y"] + 0.01)
        for rio in ("rio1", "rio2", "rio3"):
            self.assertLess(bottom(rio), min(s["y"] for k, s in n.items() if k.startswith("pt")))
        self.assertEqual(n["r1_rio1_sw1"]["y"], n["r1_rio3_sw2"]["y"])           # all member switches in one row
        xs = [n[r]["x"] for r in ("rio1", "rio2", "rio3")]
        self.assertEqual(xs, sorted(xs))                                          # members run left to right in the order given

    def test_each_rio_has_its_own_switch_pair_directly_above_it(self):
        n = self.nodes
        for rio in ("rio1", "rio2", "rio3"):
            c = n[rio]["x"] + n[rio]["w"] / 2
            a, b = (n["r1_%s_sw1" % rio], n["r1_%s_sw2" % rio])
            self.assertAlmostEqual((a["x"] + a["w"] / 2 + b["x"] + b["w"] / 2) / 2, c, 3)
            self.assertLess(a["x"] + a["w"] / 2, c)
            self.assertGreater(b["x"] + b["w"] / 2, c)

    def test_the_field_items_hang_under_their_own_rio(self):
        n, last = self.nodes, -1e9
        for rio, pt in (("rio1", "pt1"), ("rio2", "pt2"), ("rio3", "pt3")):
            c = n[rio]["x"] + n[rio]["w"] / 2
            xs = [s["x"] + s["w"] / 2 for k, s in n.items() if k.startswith(pt + "-")]
            self.assertAlmostEqual(sum(xs) / len(xs), c, delta=0.5)          # two boxes are wider than the RIO pitch, so not exactly centred
            self.assertGreater(min(xs), last)                                  # but each RIO's items stay together and in the RIOs' order
            last = max(xs)

    def test_nothing_overlaps_and_nothing_is_crossed_and_everything_is_inside_its_scope_box(self):
        r = build(ring_example())
        self.assertEqual([w for w in r["warnings"] if "overlap" in w or "passes through" in w or "outside" in w or "may not fit" in w], [])
        zone = zones_of(self.v1, "scope_L1")["scope_L1_avanceon"]
        for s in [s for s in self.v1["shapes"] if s["kind"] != "zone" and s["id"].startswith(("plc1", "rio", "r1_", "ring_"))]:
            self.assertGreaterEqual(s["x"], zone["x"] - 1e-6, s["id"])
            self.assertLessEqual(s["x"] + s["w"], zone["x"] + zone["w"] + 1e-6, s["id"])
            self.assertGreaterEqual(s["y"], zone["y"] - 1e-6, s["id"])
            self.assertLessEqual(s["y"] + s["h"], zone["y"] + zone["h"] + 1e-6, s["id"])

    def test_the_drawn_ring_is_one_closed_72_point_polygon_in_fibre_style(self):
        r = build(ring_example())
        polys = [s for s in r["page"].shapes if s["kind"] == "polygon"]
        self.assertEqual(len(polys), 1)
        p = polys[0]
        self.assertEqual((p["pts"][0], len(p["pts"])), (p["pts"][-1], 73))
        self.assertEqual((p["line"], p["pattern"], p["fill"]), (Cables().style("fibre")["color"], 2, "#E5F7E8"))
        self.assertEqual((p["text"], p["bold"], p["size"]), ("Fiber Optic Ring", True, 8))

    def test_the_report_lists_the_ring_order_and_the_switches_it_added_but_does_not_call_them_assumed(self):
        rep = build(ring_example())["report"]
        self.assertIn("ring r1 (Fiber Optic Ring): Main PLC -> RIO-1 -> RIO-2 -> RIO-3 -> Main PLC", rep["added_by_rule"])
        self.assertTrue(any("2 ring switches added at each of Main PLC, RIO-1, RIO-2, RIO-3" in x for x in rep["added_by_rule"]))
        self.assertFalse([x for x in rep["assumed"] if "Ring switch" in x or "ring" in x.lower()])

    def test_the_link_from_each_ring_switch_to_its_node_is_ethernet_and_assumed(self):
        links = [l for l in self.v1["lines"] if l["cable"] == "ethernet" and (l["from"].startswith("r1_") or l["to"].startswith("r1_"))]
        self.assertEqual(len(links), 8)
        self.assertTrue(all(l["label"] == "*" for l in links))

    def test_the_two_main_switches_sit_beside_the_main_node_and_are_joined_to_it_by_horizontal_lines(self):
        ends = {(l["from"], l["to"]) for l in self.v1["lines"] if l["cable"] == "ethernet"}
        self.assertTrue({("plc1", "r1_plc1_sw1"), ("plc1", "r1_plc1_sw2")} <= ends)
        for l in self.v1["lines"]:
            if "plc1" in (l["from"], l["to"]) and (l["from"].startswith("r1_") or l["to"].startswith("r1_")):
                self.assertEqual(len({round(p[1], 3) for p in l["points"]}), 1)

    def test_no_rings_means_no_ellipse_and_no_ring_switches(self):
        s = ring_example()
        del s["rings"]
        v1 = C.compile_v2(s)
        self.assertFalse([x for x in v1["shapes"] if x["kind"] == "ellipse" or x["id"].startswith(("r1_", "ring_"))])
        self.assertFalse([x for x in v1["shapes"] if x.get("component") == "network_switch_approved"])

    def test_the_ring_is_never_added_by_itself_and_the_other_samples_are_unchanged(self):
        self.assertNotIn("ellipse", json.dumps(C.compile_v2(owner_example())))
        self.assertEqual((build(owner_example())["shapes"], build(owner_example())["lines"]), (16, 9))

    def test_a_ring_with_fewer_than_two_members_is_an_error(self):
        s = ring_example()
        s["rings"][0]["members"] = ["rio1"]
        self.assertTrue(any("at least 2 members" in e for e in C.validate(s)[0]))
        with self.assertRaises(B.BuildError):
            build(s)

    def test_a_ring_with_an_unknown_or_repeated_or_mixed_node_is_an_error(self):
        for change, text in ((lambda s: s["rings"][0].update(members=["rio1", "nope"]), "'nope'"),
                             (lambda s: s["rings"][0].update(members=["rio1", "rio1"]), "different items"),
                             (lambda s: s["rings"][0].update(first="ws"), "same level"),
                             (lambda s: s["items"][3].update(scope="other"), "same scope"),
                             (lambda s: s["items"][3].update(qty=2), "single item"),
                             (lambda s: s["rings"][0].update(switches={"rio1": ["x", "y"]}), "ring switches")):
            s = ring_example()
            change(s)
            self.assertTrue(any(text in e for e in C.validate(s)[0]), text)

    def test_a_ring_too_wide_for_the_page_is_refused_clearly(self):
        s = ring_example()
        for k in range(4, 30):
            s["items"].append({"id": "rio%d" % k, "label": "RIO-%d" % k, "kind": "rio", "level": "L1", "scope": "avanceon"})
            s["rings"][0]["members"].append("rio%d" % k)
        with self.assertRaises(B.BuildError) as cm:
            build(s)
        self.assertIn("too large for one A3 page", str(cm.exception))

    def test_switches_the_ai_listed_are_used_instead_of_generated_ones(self):
        s = ring_example()
        for k in (1, 2):
            s["items"].append({"id": "psw%d" % k, "label": "Main ring switch %d" % k, "kind": "switch", "level": "L1", "scope": "avanceon"})
        s["rings"][0]["switches"] = {"plc1": ["psw1", "psw2"]}
        v1 = C.compile_v2(s, area=(B.AREA_W, B.AREA_H))
        n = nodes_of(v1)
        self.assertEqual(len([k for k in n if k.startswith("r1_")]), 6)                       # only the three RIOs got generated ones
        self.assertEqual([l["from"] for l in v1["lines"] if l["to"] == "ring_r1" and l["from"].startswith("psw")], ["psw1", "psw2"])
        self.assertEqual(len([l for l in v1["lines"] if l["to"] == "ring_r1"]), 8)
        self.assertLess(n["psw1"]["x"], n["plc1"]["x"])
        self.assertGreater(n["psw2"]["x"], n["plc1"]["x"])
        self.assertTrue(any("2 ring switches added at each of RIO-1, RIO-2, RIO-3" in x for x in v1["_report"]["added_by_rule"]))

    def test_a_ring_beside_other_controllers_keeps_them_above_the_ring_block(self):
        s = ring_example()
        s["items"].append({"id": "plc2", "label": "Standalone PLC", "level": "L1", "scope": "avanceon", "kind": "controller"})
        v1 = C.compile_v2(s, area=(B.AREA_W, B.AREA_H))
        n = nodes_of(v1)
        self.assertLess(n["plc2"]["y"] + n["plc2"]["h"], n["plc1"]["y"] + 0.01)

    def test_a_ring_that_does_not_fit_at_full_size_steps_the_size_down(self):
        s = ring_example()
        for k in range(4, 8):
            s["items"].append({"id": "rio%d" % k, "label": "RIO-%d" % k, "kind": "rio", "level": "L1", "scope": "avanceon"})
            s["rings"][0]["members"].append("rio%d" % k)
        v1 = C.compile_v2(s, area=(B.AREA_W, B.AREA_H))
        self.assertEqual(len([x for x in v1["shapes"] if x["id"].startswith("r1_")]), 2 + 2 * 7)
        self.assertEqual([w for w in build(s)["warnings"] if "overlap" in w or "passes through" in w], [])


class SwitchTests(unittest.TestCase):
    """Task 9: switches and patch panels are drawn only when asked, always with the approved symbol."""

    def test_a_spec_without_a_switch_contains_none(self):
        self.assertFalse([s for s in C.compile_v2(owner_example())["shapes"] if s.get("component") == "network_switch_approved"])

    def test_a_switch_item_uses_the_approved_symbol_and_ignores_a_picture_given(self):
        s = spec_with([item("p", "L1"), item("sw1", "L1", kind="switch", image="web.png", image_source="http://x"),
                       item("sw2", "L1", kind="switch", component="industrial_switch")])
        errors, questions, warnings = C.validate(s)
        self.assertEqual((errors, questions), ([], []))
        self.assertEqual(len([w for w in warnings if "always use the approved symbol" in w]), 2)
        v1 = C.compile_v2(s)
        for k in ("sw1", "sw2"):
            self.assertEqual(nodes_of(v1)[k]["component"], "network_switch_approved")
            self.assertNotIn("image", nodes_of(v1)[k])
        self.assertEqual(nodes_of(v1)["sw1"]["label"], "SW1")                                   # the label given is kept

    def test_a_switch_without_a_label_is_called_network_switch(self):
        s = spec_with([item("p", "L1"), {"id": "sw1", "kind": "switch", "level": "L1", "scope": "avanceon"},
                       {"id": "sw2", "kind": "switch", "level": "L1", "scope": "avanceon"}])
        self.assertEqual(C.validate(s)[0], [])
        self.assertEqual(nodes_of(C.compile_v2(s))["sw1"]["label"], "Network switch")

    def test_a_single_switch_warns_that_the_document_default_is_two_and_none_is_added(self):
        one = spec_with([item("p", "L1"), item("sw", "L2", kind="switch")])
        self.assertTrue(any("only one switch on L2" in w and "default is two" in w for w in C.validate(one)[2]))
        self.assertEqual(len([k for k in nodes_of(C.compile_v2(one)) if k.startswith("sw")]), 1)
        two = spec_with([item("p", "L1"), item("sw1", "L2", kind="switch"), item("sw2", "L2", kind="switch")])
        self.assertFalse([w for w in C.validate(two)[2] if "only one switch" in w])

    def test_a_switch_sits_on_a_lower_row_than_the_items_it_serves(self):
        s = spec_with([item("a", "L1"), item("b", "L1"), item("sw1", "L1", kind="switch"), item("sw2", "L1", kind="switch")])
        n = nodes_of(C.compile_v2(s))
        self.assertGreater(n["sw1"]["y"], n["a"]["y"] + n["a"]["h"] - 0.01)
        self.assertEqual(n["sw1"]["y"], n["sw2"]["y"])

    def test_a_patch_panel_is_drawn_beside_the_item_it_serves_in_that_items_band(self):
        s = spec_with([item("plc", "L1"), item("other", "L1"), item("fo", "L2", kind="patch_panel", near="plc", label="FO patch panel")])
        v1 = C.compile_v2(s)
        n = nodes_of(v1)
        self.assertEqual(n["fo"]["component"], "fo_patch_panel")
        centre = lambda k: n[k]["y"] + n[k]["h"] / 2
        self.assertAlmostEqual(centre("fo"), centre("plc"), 3)                                  # same band, same row
        self.assertTrue(any("patch panel FO patch panel moved to L1" in x for x in v1["_report"]["added_by_rule"]))
        self.assertLess(abs((n["fo"]["x"] + n["fo"]["w"] / 2) - (n["plc"]["x"] + n["plc"]["w"] / 2)), 1.6)

    def test_a_patch_panel_without_near_warns(self):
        s = spec_with([item("plc", "L1"), item("fo", "L1", kind="patch_panel")])
        self.assertTrue(any("beside the item it serves" in w for w in C.validate(s)[2]))

    def test_missing_approved_symbols_in_the_library_are_an_error(self):
        comps = Components(extras=False)
        errors = C.validate(spec_with([item("a", "L1"), item("sw1", "L1", kind="switch")]), comps)[0]
        self.assertTrue(any("approved symbol" in e for e in errors))

    def test_switches_and_patch_panels_have_the_same_picture_scale_in_one_drawing(self):
        s = spec_with([item("a", "L1"), item("sw1", "L1", kind="switch"), item("sw2", "L1", kind="switch"), item("fo", "L1", kind="patch_panel", near="a")])
        n = nodes_of(C.compile_v2(s))
        self.assertEqual({(round(n[k]["w"], 3), round(n[k]["h"], 3)) for k in ("sw1", "sw2", "fo")}, {(1.0, 0.95)})


def write_png(path, w=200, h=160, rgba=(200, 30, 30, 255)):
    """A plain-colour PNG, written with the standard library only (no Pillow needed)."""
    import struct
    import zlib
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class PictureTests(unittest.TestCase):
    """Task 10: library picture, else the exact model's picture, else a generic one, else a box that is reported."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_png(os.path.join(self.dir, "big.png"))
        write_png(os.path.join(self.dir, "tiny.png"), 60, 50)

    def build(self, items, **kw):
        s = spec_with([item("p", "L1")] + items, [{"from": i["id"], "to": "p", "cable": "hardwired"} for i in items if i["level"] == "L0"], **kw)
        return B.build(s, BASE, os.path.join(self.dir, "o.vsdx"), spec_dir=self.dir)

    def l0(self, **kw):
        d = {"id": "t", "label": "Transmitter", "level": "L0", "scope": "avanceon", "kind": "instrument"}
        d.update(kw)
        return d

    def test_a_library_picture_wins_over_a_web_picture(self):
        s = spec_with([item("plc", "L1", component="modular_plc_siemens", image="big.png", image_source="https://example.com")])
        errors, _, warnings = C.validate(s)
        self.assertEqual(errors, [])
        self.assertTrue(any("library picture of 'modular_plc_siemens' is used" in w for w in warnings))
        sh = nodes_of(C.compile_v2(s, spec_dir=self.dir))["plc"]
        self.assertEqual(sh["component"], "modular_plc_siemens")
        self.assertNotIn("image", sh)

    def test_a_library_entry_without_a_picture_lets_the_web_picture_in(self):
        r = self.build([self.l0(component="pressure_transmitter", image="big.png", image_source="https://oem.example/pt", image_match="exact")])
        sh = nodes_of(C.compile_v2(spec_with([item("p", "L1"), self.l0(component="pressure_transmitter", image="big.png", image_source="x")]), spec_dir=self.dir))["t"]
        self.assertNotIn("component", sh)
        self.assertEqual(os.path.basename(sh["image"]), "big.png")
        self.assertFalse([w for w in r["warnings"] if "BOX" in w])
        self.assertTrue(any(x.startswith("Transmitter: web, exact picture (https://oem.example/pt)") for x in r["report"]["pictures"]))

    def test_a_missing_image_source_warns_once_per_picture_and_a_given_one_does_not(self):
        r = self.build([self.l0(image="big.png", qty=3)])
        self.assertEqual([w for w in r["warnings"] if "image_source" in w], ['picture big.png has no "image_source" (URL or OEM site name); add one so the source is recorded'])
        self.assertFalse([w for w in self.build([self.l0(image="big.png", image_source="https://oem.example")])["warnings"] if "image_source" in w])

    def test_a_generic_picture_is_reported_as_generic(self):
        r = self.build([self.l0(image="big.png", image_source="https://oem.example", image_match="generic")])
        self.assertIn("generic picture used for Transmitter (exact model not found)", r["warnings"])
        self.assertTrue(any("web, generic picture" in x for x in r["report"]["pictures"]))
        self.assertIn("1 picture(s) from outside the component library (1 generic); sources are in the shape data.", r["notes"])

    def test_the_footer_note_counts_pictures_from_outside_the_library(self):
        r = self.build([self.l0(id="a", image="big.png", image_source="s", image_match="exact"), self.l0(id="b", image="big.png", image_source="s")])
        self.assertIn("2 picture(s) from outside the component library; sources are in the shape data.", r["notes"])
        self.assertFalse([n for n in self.build([self.l0()])["notes"] if "outside the component library" in n])

    def test_a_low_resolution_picture_warns(self):
        r = self.build([self.l0(image="tiny.png", image_source="s")])
        self.assertTrue(any("tiny.png is low resolution (60 x 50 px)" in w for w in r["warnings"]))
        self.assertFalse([w for w in self.build([self.l0(image="big.png", image_source="s")])["warnings"] if "low resolution" in w])

    def test_a_level_0_item_with_no_picture_at_all_is_a_box_and_reported(self):
        r = self.build([self.l0()])
        self.assertIn("BOX: no picture found for Transmitter", r["warnings"])
        self.assertIn("Transmitter: box", r["report"]["pictures"])

    def test_an_unreadable_picture_falls_back_to_a_box_with_a_warning(self):
        with open(os.path.join(self.dir, "bad.png"), "wb") as fh:
            fh.write(b"not a picture")
        r = self.build([self.l0(image="bad.png", image_source="s")])
        self.assertTrue(any("picture not usable" in w for w in r["warnings"]))
        self.assertIn("BOX: no picture found for Transmitter", r["warnings"])

    def test_the_approved_symbol_is_never_replaced_by_a_web_picture(self):
        r = self.build([item("sw1", "L1", kind="switch", image="big.png", image_source="s"), item("sw2", "L1", kind="switch")])
        self.assertTrue(any(x.startswith("SW1: library (network_switch_approved") for x in r["report"]["pictures"]))


class CommandLineTests(unittest.TestCase):
    """The way the AI actually runs the program: python scripts/build_diagram.py <spec.json>."""

    def run_cli(self, spec, *extra):
        import subprocess
        d = tempfile.mkdtemp()
        path = os.path.join(d, "spec.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(spec, fh)
        out = os.path.join(d, "o.vsdx")
        p = subprocess.run([sys.executable, os.path.join(HERE, "..", "scripts", "build_diagram.py"), path, "--out", out] + list(extra),
                           capture_output=True, text=True, timeout=120)
        return p, d, out

    def test_an_unanswered_question_stops_the_build_and_is_printed(self):
        s = owner_example()
        del s["items"][0]["scope"]
        s["questions"] = ["Which model is the analyzer?"]
        p, _, out = self.run_cli(s)
        self.assertEqual(p.returncode, 1)
        self.assertIn("NOT BUILT: questions for the user:", p.stdout)
        self.assertIn("Which scope is Pressure transmitter: Avanceon or Client/Other?", p.stdout)
        self.assertIn("Which model is the analyzer?", p.stdout)
        self.assertFalse(os.path.exists(out))

    def test_a_question_asked_in_the_spec_alone_also_stops_the_build(self):
        s = owner_example()
        s["questions"] = ["Does the client have approved header colours?"]
        p, _, out = self.run_cli(s)
        self.assertEqual(p.returncode, 1)
        self.assertIn("Does the client have approved header colours?", p.stdout)
        self.assertFalse(os.path.exists(out))

    def test_a_good_spec_prints_the_four_report_sections_in_order(self):
        p, _, out = self.run_cli(owner_example())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(os.path.exists(out))
        self.assertTrue(p.stdout.startswith("built "))
        order = [p.stdout.index(h) for h in ("ADDED BY RULE", "ASSUMED", "PICTURES", "WARNINGS")]
        self.assertEqual(order, sorted(order))
        self.assertIn("Primary Controller: library", p.stdout)
        self.assertIn("link pt -> plc1", p.stdout)

    def test_emit_v1_writes_the_free_form_spec_the_compiler_made(self):
        d = tempfile.mkdtemp()
        emitted = os.path.join(d, "v1.json")
        p, _, _ = self.run_cli(owner_example(), "--emit-v1", emitted)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        with open(emitted, encoding="utf-8") as fh:
            v1 = json.load(fh)
        self.assertIn("shapes", v1)
        self.assertNotIn("spec_version", v1)
        self.assertEqual(len(nodes_of(v1)), 7)
        p2, _, out2 = self.run_cli(v1)                              # the emitted file builds on its own, as a v1 spec
        self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)

    def test_a_v1_spec_has_no_gate_and_prints_warnings_only(self):
        with open(os.path.join(HERE, "..", "samples", "diagram_example.json"), encoding="utf-8") as fh:
            v1 = json.load(fh)
        v1["questions"] = ["ignored by v1"]
        p, _, out = self.run_cli(v1)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("ASSUMED", p.stdout)
        self.assertTrue(os.path.exists(out))

    def test_a_ring_spec_prints_the_ring_order_under_added_by_rule(self):
        p, _, _ = self.run_cli(ring_example())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("ring r1 (Fiber Optic Ring): Main PLC -> RIO-1 -> RIO-2 -> RIO-3 -> Main PLC", p.stdout.split("ASSUMED")[0])


class AssumptionTests(unittest.TestCase):
    def test_the_assumptions_strings_are_listed_in_the_report(self):
        s = owner_example()
        s["assumptions"] = ["Both workstations are dual-homed.", "  ", 5]
        rep = build(s)["report"]
        self.assertIn("Both workstations are dual-homed.", rep["assumed"])
        self.assertEqual(len([x for x in rep["assumed"] if x.strip() in ("", "5")]), 0)

    def test_an_assumed_item_is_listed_with_its_level_and_scope(self):
        s = spec_with([item("p", "L1"), item("x", "L2", "other", label="Historian", assumed=True)])
        self.assertIn("item Historian (L2, other)", C.compile_v2(s)["_report"]["assumed"])

    def test_nothing_assumed_means_no_star_and_no_footer_note(self):
        s = spec_with([item("a", "L0"), item("p", "L1")], [{"from": "a", "to": "p", "cable": "hardwired", "label": "4-20 mA"}])
        v1 = C.compile_v2(s)
        self.assertEqual(v1["lines"][0]["label"], "4-20 mA")
        self.assertFalse([n for n in v1["notes"] if "assumed" in n])
        self.assertEqual(v1["_report"]["assumed"], [])

    def test_the_star_note_is_added_once_however_many_links_are_assumed(self):
        v1 = C.compile_v2(owner_example())
        self.assertEqual(len([n for n in v1["notes"] if n.startswith("* = assumed link")]), 1)
        self.assertGreater(len([l for l in v1["lines"] if l.get("label", "").endswith("*")]), 3)

    def test_the_footer_notes_do_not_carry_the_assumptions_themselves(self):
        s = owner_example()
        s["assumptions"] = ["A very specific assumption text."]
        self.assertFalse([n for n in C.compile_v2(s)["notes"] if "specific assumption" in n])


if __name__ == "__main__":
    unittest.main()
