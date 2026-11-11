"""The AI's instruction text, the generated Claude skill and the ChatGPT package. Run:  python -m unittest discover -s tests"""
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(__file__)
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "chatgpt-plugin"))
sys.path.insert(0, HERE)
import build_diagram as B
import compile_v2 as C
import make_package as M
from cables import Cables

INSTRUCTIONS = os.path.join(ROOT, "chatgpt-plugin", "instructions.md")
SKILL = os.path.join(ROOT, "skills", "architecture-diagram", "SKILL.md")
BASE = os.path.join(ROOT, "base", "base.vsdx")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class InstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read(INSTRUCTIONS)

    def test_every_swap_sentence_is_still_in_the_instruction(self):
        for old, _ in M.SWAPS:
            self.assertIn(old, self.text, "SWAPS in make_package.py is out of date: %r" % old)

    def test_it_names_the_five_cable_ids_the_spec_version_and_the_rules_that_matter(self):
        for cid in Cables().by_id:
            self.assertIn(cid, self.text)
        self.assertEqual(sorted(Cables().by_id), ["bacnet", "ethernet", "fibre", "hardwired", "modbus"])
        for word in ("spec_version", "assumed", "find_component.py", "diagram-format-v2.md", "redundancy", "rings", "band_colors", "image_source",
                     "image_match", "ASSUMED", "PICTURES", "WARNINGS", "ADDED BY RULE", "NOT BUILT", "Primary Controller", "Secondary Controller",
                     "Main PLC", "no coordinates", "Draw only what the prompt asks for"):
            self.assertIn(word, self.text, word)

    def test_it_lists_every_level_and_both_scopes(self):
        for level in ("L0", "L1", "L2", "L3", "L3.5", "L4", "L5"):
            self.assertIn(level, self.text)
        self.assertIn("avanceon", self.text)
        self.assertIn("other", self.text)

    def test_it_fits_a_custom_gpt_instruction_field(self):
        self.assertLessEqual(len(self.text), 8000)            # ChatGPT's custom-GPT instruction limit

    def test_it_states_the_platform_differences(self):
        for phrase in ("${CLAUDE_PLUGIN_ROOT}", "/mnt/data", "no internet", "pip install pillow"):
            self.assertIn(phrase, self.text)

    def test_it_does_not_promise_what_the_program_cannot_do(self):
        # the programs and files it tells the AI to use all exist
        for rel in ("scripts/build_diagram.py", "scripts/find_component.py", "docs/diagram-format-v2.md", "samples/diagram_example_v2.json"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, rel)), rel)
            self.assertIn(rel.split("/")[-1], self.text) if rel.startswith(("scripts", "docs")) else None
        # and every component id it names is in the library
        from components import Components
        comps = Components()
        for cid in re.findall(r'"component": "([a-z0-9_]+)"', self.text):
            self.assertIn(cid, comps.by_id)

    def test_the_old_rule_that_the_library_is_only_a_fallback_is_gone(self):
        self.assertNotIn("always search the web for a picture of every item before anything else", self.text)
        self.assertNotIn("including items the component library also covers", self.text)
        self.assertIn("a library picture always wins", self.text)

    def test_the_worked_example_is_a_valid_spec_that_builds_as_the_text_says(self):
        block = re.search(r"\n(    \{\"spec_version\": 2.*?\})\n\nResult", self.text, re.S).group(1)
        spec = json.loads(block)
        errors, questions, _ = C.validate(spec)
        self.assertEqual((errors, questions), ([], []))
        d = tempfile.mkdtemp()
        from test_compile_v2 import write_png
        write_png(os.path.join(d, "pt.png"), 300, 240)
        r = B.build(spec, BASE, os.path.join(d, "o.vsdx"), spec_dir=d)
        self.assertEqual(r["spec_version"], 2)
        v1 = C.compile_v2(spec, spec_dir=d)
        self.assertEqual(sorted(s["id"] for s in v1["shapes"] if s["kind"] != "zone"), ["an", "plc1", "plc2", "pt-01", "pt-02", "ws-01", "ws-02"])
        self.assertEqual(sorted(s["id"] for s in v1["shapes"] if s["id"].startswith("band_")), ["band_L0", "band_L1", "band_L2"])
        self.assertEqual(len([l for l in v1["lines"] if {l["from"], l["to"]} == {"plc1", "plc2"}]), 2)
        self.assertFalse([s for s in v1["shapes"] if s["kind"] == "ellipse" or s.get("component") == "network_switch_approved"])
        self.assertTrue(any("link pt -> plc1" in x for x in r["report"]["assumed"]))
        self.assertTrue(any(x.startswith("Pressure transmitter") and "web, exact picture" in x for x in r["report"]["pictures"]))


class SkillTests(unittest.TestCase):
    def test_skill_md_is_exactly_what_make_package_generates_so_it_was_not_hand_edited(self):
        self.assertEqual(read(SKILL), M.skill_text())

    def test_the_skill_uses_the_plugin_folder_variable_not_the_zip_paths(self):
        s = read(SKILL)
        self.assertIn('python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py"', s)
        self.assertIn('python "${CLAUDE_PLUGIN_ROOT}/scripts/find_component.py"', s)
        self.assertNotIn("python arch_plugin/scripts", s)
        self.assertNotIn("in the attached arch_plugin.zip", s)
        self.assertIn("in this plugin's folder", s)
        self.assertIn("Tell the user where Architecture.vsdx is (in the working folder).", s)
        self.assertNotIn("Give the user only Architecture.vsdx.", s)

    def test_the_skill_has_its_front_matter(self):
        s = read(SKILL)
        self.assertTrue(s.startswith("---\nname: architecture-diagram\ndescription: "))
        self.assertEqual(s.split("---")[1].count("\n"), 3)

    def test_a_changed_instruction_that_loses_a_swap_sentence_stops_the_generator(self):
        real = M.SWAPS
        try:
            M.SWAPS = real + (("a sentence that is not there", "x"),)
            with self.assertRaises(SystemExit):
                M.skill_text()
        finally:
            M.SWAPS = real


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zip = os.path.join(tempfile.mkdtemp(), "arch_plugin.zip")
        files = list(M.files())
        with zipfile.ZipFile(cls.zip, "w") as z:
            for full, rel in files:
                z.write(full, "arch_plugin/" + rel.replace(os.sep, "/"))
        with zipfile.ZipFile(cls.zip) as z:
            cls.names = set(z.namelist())

    def test_the_zip_holds_what_the_instruction_tells_the_ai_to_use(self):
        for rel in ("scripts/build_diagram.py", "scripts/compile_v2.py", "scripts/find_component.py", "scripts/imaging.py", "scripts/levels.py",
                    "data/components.json", "data/components_extra.json", "data/icons/network_switch_approved.png", "data/level_hints.json",
                    "data/cable_types.json", "base/base.vsdx", "samples/diagram_example_v2.json", "samples/diagram_example_ring_v2.json",
                    "docs/diagram-format.md", "docs/diagram-format-v2.md", ".claude-plugin/plugin.json"):
            self.assertIn("arch_plugin/" + rel, self.names, rel)

    def test_development_aids_and_caches_are_left_out(self):
        for n in self.names:
            self.assertNotIn("dev_preview.py", n)
            self.assertNotIn("import_dataset.py", n)
            self.assertNotIn("xlsx_reader.py", n)
            self.assertNotIn("__pycache__", n)

    def test_the_zip_alone_builds_the_example(self):
        d = tempfile.mkdtemp()
        with zipfile.ZipFile(self.zip) as z:
            z.extractall(d)
        import subprocess
        out = os.path.join(d, "Architecture.vsdx")
        p = subprocess.run([sys.executable, os.path.join(d, "arch_plugin", "scripts", "build_diagram.py"),
                            os.path.join(d, "arch_plugin", "samples", "diagram_example_v2.json"), "--out", out],
                           capture_output=True, text=True, timeout=120, cwd=d)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(os.path.exists(out))

    def test_a_missing_kept_path_is_an_error_not_a_silent_skip(self):
        real = M.KEEP
        try:
            M.KEEP = real + ("docs/does-not-exist.md",)
            with self.assertRaises(SystemExit):
                list(M.files())
        finally:
            M.KEEP = real


if __name__ == "__main__":
    unittest.main()
