"""One release, one version: Claude manifest, marketplace, root plugin.json, ChatGPT instructions, Claude skill and README agree."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "chatgpt-plugin"))
import make_package as M


class VersionTests(unittest.TestCase):
    def test_every_copy_shows_the_same_version(self):
        self.assertEqual(M.version_mismatches(), [])

    def test_skill_carries_the_version(self):
        with open(os.path.join(ROOT, "skills", "architecture-diagram", "SKILL.md"), encoding="utf-8") as fh:
            self.assertIn("version %s** (Claude plugin" % M.version(), fh.read())

    def test_package_contains_version_file(self):
        out = os.path.join(tempfile.mkdtemp(), "p.zip")
        subprocess.run([sys.executable, os.path.join(ROOT, "chatgpt-plugin", "make_package.py"), out], check=True, capture_output=True)
        with zipfile.ZipFile(out) as z:
            self.assertEqual(z.read("arch_plugin/VERSION").decode().strip(), M.version())


if __name__ == "__main__":
    unittest.main()
