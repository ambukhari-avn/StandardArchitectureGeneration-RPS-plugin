"""Footer tests. Run:  python -m unittest discover -s tests   (from the repo root)
Set ARCH_BASE_VSDX=<path to any Visio-made .vsdx> to also exercise the file writer."""
import os
import re
import sys
import tempfile
import unittest
import zipfile
import xml.dom.minidom

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import footer
from vsdx_writer import A3_H, A3_W, FONT_FLOOR, Page, png_size, write_vsdx

FIELDS = dict(end_user="King Saud University", client="CRCC", project="KSU Utilities and Facilities Relocation Project",
              prepared_by="IH", checked_by="SA", approved_by="AP")
LEGEND = [{"label": "Ethernet Cable", "color": "#0070C0"}, {"label": "Fiber Optical Cable", "color": "#00B050", "pattern": 2}]


def build(**kw):
    pg = Page()
    info = footer.build_footer(pg, kw.pop("fields", FIELDS), kw.pop("legend", LEGEND), kw.pop("notes", ["First note."]), **kw)
    return pg, info


def inter(a, b, eps=0.005):
    return (a["x"] + eps < b["x"] + b["w"] and b["x"] + eps < a["x"] + a["w"] and
            a["y"] + eps < b["y"] + b["h"] and b["y"] + eps < a["y"] + a["h"])


class FooterTests(unittest.TestCase):
    def test_a3_constants(self):
        self.assertAlmostEqual(A3_W, 420 / 25.4, 3)
        self.assertAlmostEqual(A3_H, 297 / 25.4, 3)

    def test_everything_inside_footer_box_and_above_floor(self):
        pg, info = build()
        for s in pg.shapes:
            self.assertGreaterEqual(s["x"], footer.X0 - 1e-6, s)
            self.assertGreaterEqual(s["y"], footer.Y0 - 1e-6, s)
            self.assertLessEqual(s["x"] + s["w"], footer.X1 + 1e-6, s)
            self.assertLessEqual(s["y"] + s["h"], footer.TOP + 1e-6, s)
            if s["text"]:
                self.assertGreaterEqual(s["size"], FONT_FLOOR)
        self.assertAlmostEqual(info["top"], 1.40)

    def test_no_overlapping_text_or_cells(self):
        pg, _ = build()
        items = [s for s in pg.shapes if s["role"] in ("text",) or (s["role"] == "block" and s["text"])]
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                self.assertFalse(inter(a, b), (a["text"], b["text"]))

    def test_size_is_always_a3_text(self):
        pg, _ = build()
        self.assertIn("Size:  A3", [s["text"] for s in pg.shapes])

    def test_new_labels_and_separate_revision_and_sheet(self):
        pg, _ = build()
        texts = [s["text"] for s in pg.shapes]
        for t in ("End User:  King Saud University", "Client:  CRCC", "Document Name:  Architecture", "Revision:  R0", "Sheet:  1"):
            self.assertIn(t, texts)
        self.assertFalse(any("Documentation Name" in t or "Rev/Sheet" in t or "Contractor" in t for t in texts))
        pg, _ = build(fields=dict(FIELDS, revision="R2", sheet="3"))
        self.assertIn("Revision:  R2", [s["text"] for s in pg.shapes])
        self.assertIn("Sheet:  3", [s["text"] for s in pg.shapes])

    def test_old_contractor_and_rev_keys_still_work(self):
        old = {k: v for k, v in FIELDS.items() if k != "client"}
        pg, _ = build(fields=dict(old, contractor="CRCC", rev="R1/2"))
        texts = [s["text"] for s in pg.shapes]
        for t in ("Client:  CRCC", "Revision:  R1", "Sheet:  2"):
            self.assertIn(t, texts)

    def test_scope_boxes_are_fixed_colours_inside_the_footer_and_clear_of_the_legend(self):
        pg, _ = build()
        boxes = {s["key"]: s for s in pg.shapes if (s.get("key") or "").startswith("scope:")}
        self.assertEqual(set(boxes), {"scope:avanceon", "scope:other"})
        self.assertEqual(boxes["scope:avanceon"]["text"], "Avanceon Scope")
        self.assertEqual(boxes["scope:other"]["text"], "Other Scope")
        self.assertEqual(boxes["scope:avanceon"]["fill"].upper(), "#CFE8F7")
        self.assertEqual(boxes["scope:other"]["fill"].upper(), "#D5EFD3")
        legend_x = footer.X0 + footer.LEFT_W + footer.NOTES_W + footer.SCOPE_W
        for b in boxes.values():
            self.assertLessEqual(b["x"] + b["w"], legend_x + 1e-6)
            self.assertGreaterEqual(b["x"], footer.X0 + footer.LEFT_W + footer.NOTES_W)
        self.assertFalse(inter(boxes["scope:avanceon"], boxes["scope:other"]))
        self.assertAlmostEqual(footer.X0 + footer.LEFT_W + footer.NOTES_W + footer.SCOPE_W + (footer.X1 - legend_x), footer.X1)

    def test_footer_outer_size_unchanged(self):
        self.assertAlmostEqual(footer.HEIGHT, 1.10)
        self.assertAlmostEqual(footer.X1 - footer.X0, A3_W - 0.60, 3)

    def test_missing_field_fails_unless_tbc(self):
        bad = dict(FIELDS, client="  ")
        with self.assertRaisesRegex(footer.FooterError, "client"):
            build(fields=bad)
        pg, _ = build(fields=bad, allow_tbc=True)
        self.assertIn("Client:  TBC", [s["text"] for s in pg.shapes])

    def test_overflow_fails_loudly(self):
        with self.assertRaises(footer.FooterError):
            build(fields=dict(FIELDS, project="X" * 900))
        with self.assertRaises(footer.FooterError):
            build(notes=["long note " * 60] * 6)

    def test_legend_limits(self):
        many = [{"label": "c%d" % i, "color": "#112233"} for i in range(9)]
        with self.assertRaises(footer.FooterError):
            build(legend=many)
        with self.assertRaises(footer.FooterError):
            build(legend=[{"label": "x", "color": "0070C0"}])         # missing '#'
        pg, _ = build(legend=[{"label": "c%d" % i, "color": "#112233"} for i in range(8)])   # exactly full: ok
        self.assertEqual(sum(1 for s in pg.shapes if s["role"] == "line"), 8)

    def test_non_a3_page_refused(self):
        with self.assertRaises(footer.FooterError):
            footer.build_footer(Page(16, 9), FIELDS, LEGEND)

    def test_logo_is_a_picture_inside_its_cell_with_true_aspect(self):
        pg, _ = build()
        self.assertNotIn("AVANCEON", [s["text"] for s in pg.shapes])
        imgs = [s for s in pg.shapes if s["kind"] == "image"]
        self.assertEqual(len(imgs), 1)
        im = imgs[0]
        iw, ih = png_size(footer.LOGO)
        self.assertAlmostEqual(im["w"] / im["h"], iw / ih, 3)
        self.assertGreaterEqual(im["x"], footer.X0)
        self.assertLessEqual(im["x"] + im["w"], footer.X0 + 1.50)
        self.assertGreaterEqual(im["y"], footer.Y0)
        self.assertLessEqual(im["y"] + im["h"], footer.Y0 + 0.3667)

    def test_no_logo_path_prints_text_and_bad_path_fails(self):
        pg, _ = build(logo_path=None)
        self.assertIn("AVANCEON", [s["text"] for s in pg.shapes])
        self.assertEqual([s for s in pg.shapes if s["kind"] == "image"], [])
        with self.assertRaises(footer.FooterError):
            build(logo_path=os.path.join(tempfile.gettempdir(), "no_such_logo.png"))

    def test_png_size_rejects_non_png(self):
        p = os.path.join(tempfile.mkdtemp(), "x.png")
        with open(p, "wb") as fh:
            fh.write(b"not a png at all, just text bytes")
        with self.assertRaises(ValueError):
            png_size(p)

    @unittest.skipUnless(os.environ.get("ARCH_BASE_VSDX"), "set ARCH_BASE_VSDX to test the file writer")
    def test_logo_is_embedded_once_with_relationship_and_content_type(self):
        pg, _ = build()
        out = os.path.join(tempfile.mkdtemp(), "logo.vsdx")
        write_vsdx(pg, out, os.environ["ARCH_BASE_VSDX"], "t")
        z = zipfile.ZipFile(out)
        media = [n for n in z.namelist() if n.startswith("visio/media/")]
        self.assertEqual(media, ["visio/media/image1.png"])
        with open(footer.LOGO, "rb") as fh:
            self.assertEqual(z.read(media[0]), fh.read())
        rels = z.read("visio/pages/_rels/page1.xml.rels").decode()
        self.assertIn('Id="rId1"', rels)
        self.assertIn('Target="../media/image1.png"', rels)
        page = z.read("visio/pages/page1.xml").decode()
        self.assertIn("Type='Foreign'", page)
        self.assertIn("<Rel r:id='rId1'/>", page)
        self.assertRegex(z.read("[Content_Types].xml").decode(), r"Extension=[\"']png[\"']")

    @unittest.skipUnless(os.environ.get("ARCH_BASE_VSDX"), "set ARCH_BASE_VSDX to test the file writer")
    def test_vsdx_is_a3_and_well_formed(self):
        pg, _ = build()
        out = os.path.join(tempfile.mkdtemp(), "footer.vsdx")
        write_vsdx(pg, out, os.environ["ARCH_BASE_VSDX"], "t")
        z = zipfile.ZipFile(out)
        self.assertIsNone(z.testzip())
        for n in z.namelist():
            if n.endswith((".xml", ".rels")):
                xml.dom.minidom.parseString(z.read(n))
        p = z.read("visio/pages/pages.xml").decode()
        self.assertAlmostEqual(float(re.search(r"N='PageWidth' V='([\d.]+)'", p).group(1)), A3_W, 3)
        self.assertAlmostEqual(float(re.search(r"N='PageHeight' V='([\d.]+)'", p).group(1)), A3_H, 3)
        self.assertNotIn("_rels.rels", z.namelist())
        with self.assertRaises(ValueError):
            write_vsdx(Page(16, 9), out, os.environ["ARCH_BASE_VSDX"])


if __name__ == "__main__":
    unittest.main()
