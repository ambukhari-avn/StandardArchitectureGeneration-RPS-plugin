"""Behaviour checks for the new default reference layout and grouped wiring."""
import copy
import os
import shutil
import sys
import tempfile
import unittest
import importlib.util
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_diagram as B
import footer
import reference_layout as R
from cables import Cables
from vsdx_writer import Page


ROOT = os.path.abspath(B.ROOT)


class BoxedLayoutTests(unittest.TestCase):
    def sample(self):
        spec = B.load_json(os.path.join(ROOT, "samples", "reference_boxed.json"))
        spec["project"].update(end_user="E", client="C", project="P", prepared_by="X", checked_by="Y", approved_by="Z")
        return spec

    def build(self, spec):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return B.build(spec, os.path.join(ROOT, "base", "base.vsdx"), os.path.join(tmp.name, "a.vsdx"), spec_dir=os.path.join(ROOT, "samples"))

    def test_default_proportions_and_all_layer_boxes_are_inside_page(self):
        result = self.build(self.sample())
        self.assertEqual([w for w in result["warnings"] if "pixels per displayed inch" not in w], [])
        panels = {s["key"][6:]: s for s in result["page"].shapes if (s["key"] or "").startswith("layer:")}
        self.assertGreater(panels["control"]["h"], panels["scada"]["h"])
        self.assertGreater(panels["control"]["h"], panels["field"]["h"])
        self.assertTrue(all(s["rounding"] > 0 and s["fill"] == R.BODY for s in panels.values()))
        for s in panels.values():
            self.assertGreaterEqual(s["y"], B.BOTTOM - 1e-6)
            self.assertLessEqual(s["y"] + s["h"], B.TOP + 1e-6)
        headings = [s for s in result["page"].shapes if (s["key"] or "").startswith("layer-heading:")]
        self.assertEqual(len(headings), 3)
        self.assertTrue(all(s["fill"] == R.TAB_BLUE and s["rounding"] > 0 for s in headings))
        for heading in headings:                     # 7.2: a vertical strip inside the left side of its layer frame
            layer = panels[heading['key'].split(':')[1]]
            self.assertGreater(heading['x'], layer['x'])
            self.assertGreater(heading['y'], layer['y'])
            self.assertLess(heading['y'] + heading['h'], layer['y'] + layer['h'])
            self.assertGreater(heading['h'], heading['w'])
        self.assertEqual(len({round(s['w'], 6) for s in headings}), 1)          # the same strip width in every layer
        names = [s for s in result['page'].shapes if (s['key'] or '').startswith('layer-name:')]
        self.assertTrue(all(s['color'] == '#FFFFFF' and s['bold'] and s['text_angle'] == 90 for s in names))

    def test_nested_groups_keep_equipment_inside_parent_boxes(self):
        spec = self.sample()
        shapes, lines, warnings = B.prepare(spec, B.Components(), Cables(), os.path.join(ROOT, "samples"))
        B.apply_layers(spec, shapes, warnings)
        by_id = {s["id"]: s for s in shapes}
        for s in shapes:
            if not s.get("parent"):
                continue
            p = by_id[s["parent"]]
            self.assertGreaterEqual(s["x"], p["x"])
            self.assertGreaterEqual(s["y"], p["y"])
            self.assertLessEqual(s["x"] + s["w"], p["x"] + p["w"] + 1e-6)
            self.assertLessEqual(s["y"] + s["h"], p["y"] + p["h"] + 1e-6)

    def test_root_blocks_fill_layer_width_right_of_the_heading_strip(self):
        spec = self.sample()
        shapes, _, warnings = B.prepare(spec, B.Components(), Cables(), os.path.join(ROOT, 'samples'))
        panels = B.apply_layers(spec, shapes, warnings)
        for panel in panels:
            roots = sorted([s for s in shapes if s.get('layer') == panel['id'] and not s.get('parent')], key=lambda s: s['x'])
            self.assertAlmostEqual(roots[0]['x'], panel['head_w'] + R.HEAD_GAP)
            self.assertAlmostEqual(roots[-1]['x'] + roots[-1]['w'], B.AREA_W - R.PAD)
            for shape in roots:
                self.assertGreaterEqual(shape['y'], panel['y'] + min(R.PAD, panel['h'] * .08) - 1e-6)
                self.assertLessEqual(shape['y'] + shape['h'], panel['y'] + panel['h'] - min(R.PAD, panel['h'] * .08) + 1e-6)

    def test_shared_hardwire_preserves_six_connections_and_ends_at_box_edges(self):
        result = self.build(self.sample())
        logical = [c for c in result["logical_connections"] if c["a"].startswith("p") and c["a"] != "primary" and c["cable"] == "hardwired"]
        self.assertEqual(len(logical), 6)
        shared = [c for c in result["display_connections"] if c["a"] == "instruments"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["b"], "io-box")
        self.assertEqual(len(shared[0]["source_connections"]), 6)
        self.assertEqual(result["lines"], 5)
        self.assertEqual(shared[0]['label'], 'Typical Hardwired Signals \u2014 AI/DI/AO/DO')
        self.assertTrue(any('multiple physical field connections' in n for n in result['notes']))
        self.assertTrue(any(s['text'] == shared[0]['label'] for s in result['page'].shapes))
        page = result["page"]
        wire = next(s for s in page.shapes if (s["key"] or "").startswith("instruments->io-box|logical="))
        for point, key in ((wire["pts"][0], "shape:instruments"), (wire["pts"][-1], "shape:io-box")):
            box = next(s for s in page.shapes if s["key"] == key)
            x, y = point
            on_edge = ((abs(x - box["x"]) < 1e-5 or abs(x - box["x"] - box["w"]) < 1e-5) and box["y"] - 1e-5 <= y <= box["y"] + box["h"] + 1e-5 or
                       (abs(y - box["y"]) < 1e-5 or abs(y - box["y"] - box["h"]) < 1e-5) and box["x"] - 1e-5 <= x <= box["x"] + box["w"] + 1e-5)
            self.assertTrue(on_edge, (point, key))

    def test_individual_override_restores_all_device_connections(self):
        spec = self.sample()
        spec["cable_detail"] = "individual"
        result = self.build(spec)
        self.assertEqual(len(result["display_connections"]), 10)
        self.assertEqual({c["a"] for c in result["display_connections"] if c["cable"] == "hardwired"}, {"fg", "p1", "p2", "p3", "p4", "p5", "p6"})

    def test_per_cable_manual_override_is_not_collapsed(self):
        spec = self.sample()
        spec["lines"][4]["individual"] = True
        result = self.build(spec)
        self.assertTrue(any(c["a"] == "p1" and c["b"] == "io" for c in result["display_connections"]))
        shared = next(c for c in result["display_connections"] if c["a"] == "instruments")
        self.assertEqual(len(shared["source_connections"]), 5)

    def test_distinct_io_racks_are_not_merged_into_one_trunk(self):
        spec = self.sample()
        spec["shapes"].append({"id": "io2", "label": "Second I/O Rack", "parent": "plc-panel", "row": 1, "component": "remote_i_o_drop"})
        spec["lines"][5]["to"] = "io2"
        result = self.build(spec)
        trunks = [c for c in result["display_connections"] if c["a"] == "instruments"]
        self.assertEqual(len(trunks), 2)
        self.assertEqual({c["b"] for c in trunks}, {"io-box", "io2"})            # 7.5: the lone rack has no box of its own
        self.assertEqual(sorted(len(c["source_connections"]) for c in trunks), [1, 5])

    def test_external_device_links_are_promoted_to_visible_container_boundaries(self):
        spec = self.sample()
        result = self.build(spec)
        promoted = [c for c in result["display_connections"] if c.get("source_connections")]
        self.assertTrue(promoted)
        by_key = {s["key"]: s for s in result["page"].shapes if s["key"]}
        for c in promoted:                           # every promoted end is a box that is actually drawn
            for end in (c["a"], c["b"]):
                self.assertIn("shape:" + end, by_key)

    def test_loose_avanceon_equipment_has_no_box(self):
        spec = B.load_json(os.path.join(ROOT, "samples", "reference_quality.json"))
        result = self.build(spec)
        keys = {s["key"] for s in result["page"].shapes if s["key"]}
        self.assertNotIn("shape:__equipment_scada", keys)          # 7.4: equipment sits directly in the layer
        self.assertNotIn("shape:__equipment_control", keys)
        self.assertIn("shape:__equipment_field", keys)              # field group keeps the representative-cable boundary
        wire = next(c for c in result["display_connections"] if {c["a"], c["b"]} & {"plc", "__equipment_control"})
        self.assertEqual({wire["a"], wire["b"]}, {"sw", "plc"})    # a cable never ends on an invisible arrangement

    def test_racks_in_one_common_io_box_share_one_representative_cable(self):
        spec = self.sample()
        spec['shapes'].append({'id': 'io2', 'label': 'Second I/O Rack', 'parent': 'io-box', 'component': 'remote_i_o_drop'})
        spec['lines'][5]['to'] = 'io2'
        shapes, lines, warnings = B.prepare(spec, B.Components(), Cables(), os.path.join(ROOT, 'samples'))
        B.apply_layers(spec, shapes, warnings)
        self.assertFalse(any(s['id'].startswith('__rack_') for s in shapes))      # no box around an individual rack
        display = R.group_connections(spec, shapes, lines)
        trunks = [c for c in display if c.get('representative')]
        self.assertEqual({c['b'] for c in trunks}, {'io-box'})                    # one cable to the common I/O box
        self.assertEqual(len(trunks[0]['source_connections']), 6)                 # every instrument relationship is kept

    def test_optional_panel_is_beside_control_and_never_added_unasked(self):
        spec = self.sample()
        result = self.build(spec)
        main = next(s for s in result["page"].shapes if s["key"] == "shape:plc-panel")
        side = next(s for s in result["page"].shapes if s["key"] == "shape:aux-panel")
        self.assertGreater(side["x"], main["x"] + main["w"])
        self.assertAlmostEqual(side["y"], main["y"])
        spec["shapes"] = [s for s in spec["shapes"] if s["id"] not in ("aux-panel", "ups")]
        without = self.build(spec)
        self.assertFalse(any(s["key"] == "shape:aux-panel" for s in without["page"].shapes))

    def test_cable_palette_is_unchanged_and_matches_legend(self):
        colors = {"ethernet": "#0000FF", "fibre": "#00B000", "modbus": "#FF0000", "bacnet": "#7030A0", "hardwired": "#000000"}
        cables = Cables()
        self.assertEqual({cid: cables.get(cid)["color"] for cid in colors}, colors)
        result = self.build(self.sample())
        for c in result["display_connections"]:
            line = next(s for s in result["page"].shapes if (s["key"] or "").startswith(c["a"] + "->" + c["b"]))
            self.assertEqual(line["line"], colors[c["cable"]])

    def test_layer_weight_overrides_are_respected(self):
        spec = self.sample()
        spec["layer_weights"] = {"scada": 2, "control": 5, "field": 2}
        result = self.build(spec)
        panels = {s["key"][6:]: s for s in result["page"].shapes if (s["key"] or "").startswith("layer:")}
        self.assertAlmostEqual(panels["control"]["h"] / panels["scada"]["h"], 2.5)

    def test_invalid_hierarchy_and_layout_options_are_rejected(self):
        base = self.sample()
        broken = []
        spec = copy.deepcopy(base); spec["shapes"][3]["parent"] = "absent"; broken.append(spec)
        spec = copy.deepcopy(base); spec["shapes"][1]["parent"] = "processors"; broken.append(spec)
        spec = copy.deepcopy(base); spec["layer_weights"] = {"control": 0}; broken.append(spec)
        spec = copy.deepcopy(base); spec["shapes"][2]["columns"] = -1; broken.append(spec)
        spec = copy.deepcopy(base); spec["shapes"][1]["width_weight"] = "bad"; broken.append(spec)
        spec = copy.deepcopy(base); spec["shapes"][3]["row"] = -2; broken.append(spec)
        for spec in broken:
            with self.assertRaises(B.BuildError):
                self.build(spec)

    def test_all_six_layers_still_build_with_compact_boxes(self):
        ids = ["enterprise", "dmz", "operations", "scada", "control", "field"]
        spec = {"layers": ids, "shapes": [{"id": k, "layer": k, "label": k, "component": "industrial_switch"} for k in ids]}
        result = self.build(spec)
        self.assertEqual(sum(1 for s in result["page"].shapes if (s["key"] or "").startswith("layer:")), 6)

    def test_footer_has_three_joined_rectangular_sections_with_complete_metadata(self):
        page = Page()
        fields = dict(client="Client", end_user="End User", project="Project", doc_name="System Architecture", prepared_by="A", checked_by="B", approved_by="C", revision="R3", sheet="2")
        footer.build_footer(page, fields, Cables().legend(["ethernet", "fibre", "hardwired"]), ["Project note"])
        cards = [s for s in page.shapes if (s["key"] or "").startswith("footer-card:")]
        self.assertEqual(len(cards), 3)
        self.assertTrue(all(s["rounding"] == 0 and s["line"] is None for s in cards))
        frame = next(s for s in page.shapes if s['key'] == 'footer-frame')
        self.assertEqual((frame['line'], frame['rounding']), (R.BORDER, 0))
        dividers = [s for s in page.shapes if (s['key'] or '').startswith('footer-divider:')]
        self.assertEqual(len(dividers), 2)
        self.assertTrue(all(s['lw'] == frame['lw'] for s in dividers))
        for a, b in zip(cards, cards[1:]):
            self.assertAlmostEqual(a["x"] + a["w"], b["x"])
        texts = [s["text"] for s in page.shapes]
        for text in ("Client / End User", "Project", "System Architecture", "A", "B", "C", "A3 - R3 / 2", "Notes", "Legend", "Avanceon Scope", "Client Scope"):
            self.assertIn(text, texts)
        client_scope = next(s for s in page.shapes if s["key"] == "scope:other")
        self.assertEqual((client_scope["fill"], client_scope["line"]), (R.CLIENT, R.ORANGE))

    def test_packaging_includes_new_runtime_and_reference_assets(self):
        loader = importlib.util.spec_from_file_location("arch_pack_test", os.path.join(ROOT, "chatgpt-plugin", "make_package.py"))
        pack = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(pack)
        paths = {rel.replace(os.sep, "/") for full, rel in pack.files()}
        for path in ("scripts/reference_layout.py", "scripts/reference_footer.py", "scripts/dev_preview.py", "docs/reference-layout.md", "docs/reference-style.png", "docs/reference-dashes.png", "samples/reference_boxed.json"):
            self.assertIn(path, paths)
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "chatgpt-plugin"))
            with open(os.path.join(ROOT, "chatgpt-plugin", "instructions.md"), encoding="utf-8") as source:
                instructions = source.read()
            with open(os.path.join(tmp, "chatgpt-plugin", "instructions.md"), "w", encoding="utf-8") as target:
                target.write(instructions)
            os.makedirs(os.path.join(tmp, ".claude-plugin"))                 # the release version is read from here
            shutil.copy(os.path.join(ROOT, ".claude-plugin", "plugin.json"), os.path.join(tmp, ".claude-plugin", "plugin.json"))
            with patch.object(pack, "ROOT", tmp):
                pack.write_skill()
            with open(os.path.join(tmp, "skills", "architecture-diagram", "SKILL.md"), encoding="utf-8") as generated:
                rebuilt = generated.read()
            with open(os.path.join(ROOT, "skills", "architecture-diagram", "SKILL.md"), encoding="utf-8") as current:
                self.assertEqual(rebuilt.strip(), current.read().strip())
