"""Footer form tests. Run:  python -m unittest discover -s tests"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import footer
import footer_form as ff
from vsdx_writer import Page

FILLED = """End User: King Saud University
Client: CRCC
Project: KSU Utilities and Facilities Relocation Project
Document Name: Architecture
Prepared by: IH
Checked by: SA
Approved by: AP
Revision: R0
Sheet: 1
Notes:
1. Two ASPs are considered for each existing building.
Redundant networking: considered for each building.
"""


class FormTests(unittest.TestCase):
    def test_blank_form_lists_every_question_with_defaults(self):
        text = ff.blank_form_text()
        fields, notes_label = ff.load_template()
        for f in fields:
            self.assertIn(f["label"] + ":", text)
        self.assertIn("Document Name: Architecture", text)
        self.assertIn("Revision: R0", text)
        self.assertIn("Sheet: 1", text)
        self.assertIn(notes_label + ":", text)

    def test_blank_form_parses_to_defaults_only(self):
        fields, notes = ff.parse_form(ff.blank_form_text())
        self.assertEqual(fields, {"doc_name": "Architecture", "revision": "R0", "sheet": "1"})
        self.assertEqual(notes, [])

    def test_filled_text_form(self):
        fields, notes = ff.parse_form(FILLED)
        self.assertEqual(fields["end_user"], "King Saud University")
        self.assertEqual(fields["approved_by"], "AP")
        # numbering stripped (the footer numbers notes itself); a colon inside a note is kept as note text
        self.assertEqual(notes, ["Two ASPs are considered for each existing building.",
                                 "Redundant networking: considered for each building."])

    def test_filled_form_goes_straight_into_the_footer(self):
        fields, notes = ff.parse_form(FILLED)
        pg = Page()
        footer.build_footer(pg, fields, [{"label": "Ethernet Cable", "color": "#0070C0"}], notes)
        texts = [s["text"] for s in pg.shapes]
        self.assertIn("CRCC / King Saud University", texts)
        self.assertIn("KSU Utilities and Facilities Relocation Project", texts)
        self.assertTrue(any(t.startswith("1) Two ASPs") and "\n2) Redundant networking" in t for t in texts))

    def test_label_matching_ignores_case_and_spacing(self):
        fields, _ = ff.parse_form("end user :  A\nCLIENT: B")
        self.assertEqual(fields, {"end_user": "A", "client": "B"})

    def test_unknown_label_or_stray_line_is_rejected(self):
        with self.assertRaises(ff.FormError):
            ff.parse_form("End Usr: typo")
        with self.assertRaises(ff.FormError):
            ff.parse_form("End User: A\nsome stray sentence")

    def test_json_form(self):
        fields, notes = ff.parse_form(json.dumps({"end_user": "A", "project": " ", "notes": ["n1", ""]}))
        self.assertEqual(fields, {"end_user": "A"})
        self.assertEqual(notes, ["n1"])
        with self.assertRaises(ff.FormError):
            ff.parse_form(json.dumps({"end_usr": "A"}))

    def test_missing_required_values_still_stop_the_footer(self):
        fields, notes = ff.parse_form("End User: A")
        with self.assertRaises(footer.FooterError):
            footer.build_footer(Page(), fields, [], notes)


if __name__ == "__main__":
    unittest.main()
