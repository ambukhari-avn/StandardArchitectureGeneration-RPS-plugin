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

FIELDS = dict(end_user="King Saud University", contractor="CRCC", project="KSU Utilities and Facilities Relocation Project",
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

    def test_missing_field_fails_unless_tbc(self):
        bad = dict(FIELDS, end_user="  ")
        with self.assertRaisesRegex(footer.FooterError, "client"):
            build(fields=bad)
        pg, _ = build(fields=bad, allow_tbc=True)
        self.assertIn("Client:  TBC", [s["text"] for s in pg.shapes])

    def test_client_replaces_end_user_and_there_is_no_contractor_cell(self):
        pg, _ = build()
        texts = [s["text"] for s in pg.shapes]
        self.assertIn("Client:  King Saud University", texts)
        self.assertFalse([t for t in texts if "Contractor" in t or "End User" in t])
        new_key = dict(FIELDS)
        new_key.pop("end_user")
        new_key["client"] = "New Client"                                       # the new key works too
        self.assertIn("Client:  New Client", [s["text"] for s in build(fields=new_key)[0].shapes])
        no_contractor = {k: v for k, v in FIELDS.items() if k != "contractor"}  # contractor is no longer required
        build(fields=no_contractor)
        cell = next(s for s in pg.shapes if s["text"].startswith("Client:"))   # the Client cell takes the full title-block width
        self.assertAlmostEqual(cell["w"], footer.LEFT_W)

    def test_the_scope_legend_is_two_stacked_boxes_with_the_document_colours(self):
        pg, _ = build()
        boxes = {s["text"]: s for s in pg.shapes if s["text"] in ("Avanceon Scope", "Client Scope")}
        self.assertEqual(set(boxes), {"Avanceon Scope", "Client Scope"})
        self.assertEqual(boxes["Avanceon Scope"]["fill"], "#E7E6E6")
        self.assertEqual(boxes["Client Scope"]["fill"], "#F2DCDB")
        self.assertEqual(boxes["Avanceon Scope"]["fill"], footer.SCOPE_FILL["avanceon"])
        self.assertGreater(boxes["Avanceon Scope"]["y"], boxes["Client Scope"]["y"])       # stacked: grey above pink
        self.assertAlmostEqual(boxes["Avanceon Scope"]["x"], boxes["Client Scope"]["x"])
        self.assertTrue(all(b["bold"] and b["size"] >= 8 for b in boxes.values()))

    def test_a_legend_entry_with_an_arrow_draws_an_arrowhead(self):
        pg, _ = build(legend=[{"label": "Hardwired (Inst Cable)", "color": "#000000", "arrow": True},
                              {"label": "Ethernet Cable", "color": "#0000FF", "pattern": 2}])
        samples = {s["key"]: s for s in pg.shapes if s["role"] == "line"}
        self.assertTrue(samples["legend:Hardwired (Inst Cable)"]["arrow"])
        self.assertFalse(samples["legend:Ethernet Cable"]["arrow"])

    def test_all_five_cables_fit_the_legend_at_a_legible_size(self):
        from cables import Cables
        c = Cables()
        pg, _ = build(legend=c.legend(list(c.by_id)))
        for s in pg.shapes:
            if s["text"] in [e["label"] for e in c.legend(list(c.by_id))]:
                self.assertGreaterEqual(s["size"], FONT_FLOOR)
        self.assertEqual(sum(1 for s in pg.shapes if s["role"] == "line"), 5)

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
