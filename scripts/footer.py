"""Fixed footer for the A3 architecture page: title block + notes + legend. Standard library only.

The footer's geometry and field labels never change. Only the values do, and every value is checked:
a missing field, text that cannot fit above the font floor, or a legend that is too long raises an error
instead of shrinking below the floor or dropping anything.

    from vsdx_writer import Page
    page = Page()
    info = build_footer(page, fields, legend, notes)
    info["top"]        # y (inches) above which the diagram may draw; the footer occupies everything below it
"""
import os
import re

from textfit import TextFitError, fit_size
from vsdx_writer import A3_H, A3_W, FONT_FLOOR, png_size

LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "base", "avanceon_logo.png")

# ---- geometry (inches, origin bottom-left) -------------------------------------------------------------------
X0, Y0, HEIGHT = 0.30, 0.30, 1.10
X1 = A3_W - 0.30
TOP = Y0 + HEIGHT                       # diagram content must stay above this line
LEFT_W, NOTES_W = 6.20, 4.70            # title block / notes widths; the legend takes the rest

REQUIRED = ("end_user", "contractor", "project", "prepared_by", "checked_by", "approved_by")
DEFAULTS = {"doc_name": "Architecture", "rev": "R0/1"}   # Maaden / KSU convention; override per project
LEGEND_ROWS, LEGEND_ROW_H, LEGEND_MAX_COLS = 4, 0.20, 2


class FooterError(ValueError):
    """Bad or missing footer input, or content that does not fit."""


def _fit(text, w, h, sizes, bold=False, what="text"):
    """Largest size from `sizes` (descending) at which `text` fits w x h; raises if none, never goes below the floor."""
    try:
        return fit_size(text, w, h, sizes, bold)
    except TextFitError:
        raise FooterError("%s does not fit at or above %.1f pt: %r" % (what, FONT_FLOOR, text[:60]))


def _clean(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()


def _check_fields(fields, allow_tbc):
    f = dict(DEFAULTS)
    f.update({k: _clean(v) for k, v in fields.items() if v is not None})
    missing = [k for k in REQUIRED if not f.get(k)]
    if missing and not allow_tbc:
        raise FooterError("missing footer field(s): %s" % ", ".join(missing))
    for k in missing:
        f[k] = "TBC"
    return f


def _check_legend(legend):
    if len(legend) > LEGEND_ROWS * LEGEND_MAX_COLS:
        raise FooterError("legend has %d entries; the footer holds at most %d" % (len(legend), LEGEND_ROWS * LEGEND_MAX_COLS))
    for e in legend:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", e.get("color", "")):
            raise FooterError("legend entry %r: colour must be #RRGGBB" % e.get("label"))
        if e.get("kind", "line") not in ("line", "box") or e.get("pattern", 1) not in (1, 2):
            raise FooterError("legend entry %r: kind must be line|box and pattern 1 (solid) or 2 (dashed)" % e.get("label"))
        if not _clean(e.get("label")):
            raise FooterError("legend entry without a label")


def build_footer(page, fields, legend, notes=(), allow_tbc=False, logo_path=LOGO, logo_text="AVANCEON", parent=None):
    """Add the footer shapes to `page` (must be A3). Returns {'top', 'block', 'sizes'}.

    logo_path : PNG placed in the logo cell (default: base/avanceon_logo.png). None -> logo_text is printed instead.
    fields : end_user, contractor, project, prepared_by, checked_by, approved_by (+ optional doc_name, rev)
    legend : [{'label', 'color': '#RRGGBB', 'pattern': 1|2, 'kind': 'line'|'box'}]  - line = cable type, box = scope swatch
    notes  : list of strings; numbered automatically
    Size is always printed as A3 and is not an input.
    """
    if abs(page.w - A3_W) > 0.01 or abs(page.h - A3_H) > 0.01:
        raise FooterError("page must be A3 landscape")
    f = _check_fields(fields, allow_tbc)
    _check_legend(legend)
    sizes = {}
    foot = page.rect("block", X0, Y0, X1 - X0, HEIGHT, parent, fill=None, lw=1.0)

    # ---- title block ------------------------------------------------------------------------------------------
    xl = X0 + LEFT_W
    cells = [  # key, text, x, y, w, h, preferred pt, halign
        ("end_user", "End User:  " + f["end_user"], X0, 1.0333, 3.10, 0.3667, 8, 0),
        ("contractor", "Contractor:  " + f["contractor"], X0 + 3.10, 1.0333, 3.10, 0.3667, 8, 0),
        ("project", "Project:  " + f["project"], X0, 0.6667, LEFT_W, 0.3666, 8, 0),
        ("logo", logo_text, X0, Y0, 1.50, 0.3667, 12, 1),
        ("doc_name", "Documentation Name:  " + f["doc_name"], X0 + 1.50, 0.4833, LEFT_W - 1.50, 0.1834, 7, 0),
        ("prepared_by", "Prepared by:  " + f["prepared_by"], X0 + 1.50, Y0, 1.00, 0.1833, 6.5, 0),
        ("checked_by", "Checked by:  " + f["checked_by"], X0 + 2.50, Y0, 1.00, 0.1833, 6.5, 0),
        ("approved_by", "Approved by:  " + f["approved_by"], X0 + 3.50, Y0, 1.00, 0.1833, 6.5, 0),
        ("size", "Size:  A3", X0 + 4.50, Y0, 0.80, 0.1833, 6.5, 0),
        ("rev", "Rev/Sheet:  " + f["rev"], X0 + 5.30, Y0, 0.90, 0.1833, 6.5, 0),
    ]
    for key, text, x, y, w, h, pref, ha in cells:
        if key == "logo" and logo_path:                     # the logo is a picture, not text
            if not os.path.exists(logo_path):
                raise FooterError("logo file not found: %s" % logo_path)
            page.rect("block", x, y, w, h, foot, fill=None, lw=0.5)
            iw, ih = png_size(logo_path)
            pad = 0.03
            ph = h - 2 * pad
            pw = ph * iw / ih
            if pw > w - 2 * pad:
                pw, ph = w - 2 * pad, (w - 2 * pad) * ih / iw
            page.image(x + (w - pw) / 2, y + (h - ph) / 2, pw, ph, logo_path, foot, key="logo")
            continue
        ladder = [s for s in (12, 10, 8, 7, 6.5, 6) if s <= pref]
        size = _fit(text, w, h, ladder, bold=(key == "logo"), what="footer field '%s'" % key)
        sizes[key] = size
        page.rect("block", x, y, w, h, foot, fill=None, lw=0.5, text=text, size=size, bold=(key == "logo"), halign=ha, valign=1)

    # ---- notes ------------------------------------------------------------------------------------------------
    nb = page.rect("block", xl, Y0, NOTES_W, HEIGHT, foot, fill=None, lw=0.5)
    page.text(xl + 0.03, TOP - 0.20, NOTES_W - 0.06, 0.17, "Notes:", nb, size=7, bold=True, halign=0, valign=0)
    body = "\n".join("%d. %s" % (i, _clean(n)) for i, n in enumerate(notes, 1))
    if body:
        size = _fit(body, NOTES_W - 0.06, HEIGHT - 0.26, (7, 6.5, 6), what="notes")
        sizes["notes"] = size
        page.text(xl + 0.03, Y0 + 0.03, NOTES_W - 0.06, HEIGHT - 0.26, body, nb, size=size, halign=0, valign=0)

    # ---- legend -----------------------------------------------------------------------------------------------
    xg = xl + NOTES_W
    lg = page.rect("block", xg, Y0, X1 - xg, HEIGHT, foot, fill=None, lw=0.5)
    page.text(xg, TOP - 0.22, X1 - xg, 0.20, "Legend", lg, size=8, bold=True)
    cols = 1 if len(legend) <= LEGEND_ROWS else 2
    colw = (X1 - xg - 0.10) / cols
    for i, e in enumerate(legend):
        c, r = divmod(i, LEGEND_ROWS)
        x = xg + 0.10 + c * colw
        y = TOP - 0.30 - LEGEND_ROW_H * (r + 1)
        label = _clean(e["label"])
        size = _fit(label, colw - 0.85, LEGEND_ROW_H - 0.02, (7, 6.5, 6), what="legend entry")
        if e.get("kind", "line") == "line":
            page.line([(x, y + LEGEND_ROW_H / 2), (x + 0.6, y + LEGEND_ROW_H / 2)], e["color"], e.get("pattern", 1), 1.0, lg,
                      key="legend:" + label)
        else:
            page.rect("icon", x, y + 0.03, 0.6, LEGEND_ROW_H - 0.06, lg, fill=e["color"], line="#404040", lw=0.5, key="legend:" + label)
        page.text(x + 0.70, y, colw - 0.80, LEGEND_ROW_H, label, lg, size=size, halign=0)
    return {"top": TOP, "block": foot, "sizes": sizes}


# ---- demo / manual check ----------------------------------------------------------------------------------------
#   python footer.py --print-form                          prints the blank form to fill in
#   python footer.py --form filled.txt --base X.vsdx       writes a footer-only A3 page to <Downloads>\out
if __name__ == "__main__":
    import argparse
    import sys
    from footer_form import blank_form_text, parse_form
    from vsdx_writer import Page, write_vsdx

    ap = argparse.ArgumentParser(description="Write an A3 page containing only the footer.")
    ap.add_argument("--print-form", action="store_true", help="print the blank footer form and exit")
    ap.add_argument("--form", help="filled-in form: .txt ('Label: value' lines) or .json")
    ap.add_argument("--base", default=os.environ.get("ARCH_BASE_VSDX"),
                    help="existing Visio-made .vsdx used as the package skeleton (or set ARCH_BASE_VSDX)")
    ap.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "Downloads", "out", "footer_demo.vsdx"))
    ap.add_argument("--tbc", action="store_true", help="fill missing fields with TBC")
    for k in REQUIRED + ("doc_name", "rev"):
        ap.add_argument("--" + k.replace("_", "-"), help="overrides the form value")
    a = ap.parse_args()
    if a.print_form:
        print(blank_form_text())
        sys.exit(0)
    if not a.base:
        ap.error("--base (or ARCH_BASE_VSDX) is required")
    fields, notes = ({}, []) if not a.form else parse_form(open(a.form, encoding="utf-8-sig").read())
    fields.update({k: getattr(a, k) for k in REQUIRED + ("doc_name", "rev") if getattr(a, k)})
    pg = Page()
    pg.rect("frame", 0.20, 0.20, A3_W - 0.40, A3_H - 0.40, fill=None, lw=1.25)
    from cables import Cables
    legend = Cables().legend(["ethernet", "fibre", "hardwired"])      # demo: three of the client's cable types
    info = build_footer(pg, fields, legend, notes, allow_tbc=a.tbc)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    write_vsdx(pg, a.out, a.base, title="Footer demo")
    print("wrote %s; footer top at %.2f in; font sizes %s" % (a.out, info["top"], info["sizes"]))
