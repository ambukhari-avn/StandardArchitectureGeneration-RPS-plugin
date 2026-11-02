"""Draw a free-form diagram file as one editable A3 Visio page.   Standard library only.

    python scripts/build_diagram.py diagram.json [--out Architecture.vsdx] [--preview]

The file lists shapes (position and size in inches, from the top-left corner of the drawing area above the footer) and lines
between them. The program fixes only two things, so they are the same for every diagram the team makes: the footer (title block,
notes, legend) and the cable colours, which come from data/cable_types.json by cable name. Everything else is drawn as written.
Problems that can be repaired (a shape off the page, a missing picture, a label too long for its box) are repaired and reported as
warnings; the build stops only when a line names an unknown shape or cable type, or the file is not usable at all.
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import footer
from cables import CableError, Cables
from components import Components
from draw import BOX_FILL, BOX_LINE, BOX_SIZES, draw_picture
from textfit import TextFitError, fit_size
from vsdx_writer import A3_H, A3_W, FONT_FLOOR, Page, png_size, write_vsdx

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MARGIN = footer.X0
TOP, BOTTOM = A3_H - MARGIN, footer.TOP + 0.12      # the drawing area runs between these page heights
AREA_W, AREA_H = A3_W - 2 * MARGIN, TOP - BOTTOM
DEFAULT_SIZE = {"box": (1.35, 0.55), "picture": (1.00, 0.95), "text": (1.50, 0.30)}
ZONE_FILL, ZONE_LINE = "#F7F9FC", "#9AA5B1"
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")


class BuildError(ValueError):
    pass


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def as_png(path):
    """The picture as a PNG path. Another raster format (WebP, JPEG, GIF...) is converted when Pillow is installed (ChatGPT's sandbox has it)."""
    try:
        png_size(path)
        return path
    except ValueError:
        try:
            from PIL import Image
        except ImportError:
            raise ValueError("%s is not a PNG and Pillow is not installed to convert it" % path)
        out = os.path.join(tempfile.mkdtemp(), "converted.png")
        Image.open(path).convert("RGBA").save(out)
        return out


# ---- reading the file -----------------------------------------------------------------------------------------------------
def prepare(spec, comps, cables, spec_dir):
    """Shapes and lines with every default filled in. Returns (shapes, lines, warnings); raises BuildError for what cannot be drawn."""
    if not isinstance(spec, dict) or not isinstance(spec.get("shapes"), list) or not spec["shapes"]:
        raise BuildError('the file must be a JSON object with a non-empty "shapes" list')
    errors, warnings, shapes, ids = [], [], [], set()
    for n, s in enumerate(spec["shapes"], 1):
        if not isinstance(s, dict):
            errors.append("shape %d: not an object" % n)
            continue
        sid = str(s.get("id", "")).strip()
        where = "shape %r" % (sid or n)
        if not sid or sid in ids:
            errors.append("%s: every shape needs its own id" % where)
            continue
        ids.add(sid)
        kind = s.get("kind", "box")
        if kind not in ("box", "zone", "text"):
            errors.append('%s: kind must be "box", "zone" or "text"' % where)
            continue
        label, pic, key, web = str(s.get("label", "")).strip(), None, "shape:" + sid, False
        if s.get("component"):
            try:
                comp = comps.get(s["component"])
            except KeyError:
                errors.append("%s: component %r is not in the library" % (where, s["component"]))
                continue
            label, pic, key = label or comp["label"], comps.picture_path(s["component"]), "component:%s" % comp["id"]
        elif s.get("image") and kind == "box":
            path = str(s["image"])
            path = path if os.path.isabs(path) else os.path.join(spec_dir, path)
            try:
                path = as_png(path)
                png_size(path)
                pic, web = path, True
                key = "image:%s|%s" % (s.get("image_source", "unknown"), sid)
            except (OSError, ValueError) as e:
                warnings.append("%s: picture not usable (%s); drawn as a box" % (where, e))
        x, y = _num(s.get("x")), _num(s.get("y"))
        if x is None or y is None:
            errors.append("%s: x and y (inches from the top-left of the drawing area) are required" % where)
            continue
        dw, dh = DEFAULT_SIZE["picture" if pic and kind == "box" else kind if kind != "zone" else "box"]
        w, h = _num(s.get("w", dw if kind != "zone" else None)), _num(s.get("h", dh if kind != "zone" else None))
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append("%s: w and h must be positive numbers%s" % (where, " (zones need them)" if kind == "zone" else ""))
            continue
        if w > AREA_W or h > AREA_H:
            warnings.append("%s: larger than the drawing area (%.1f x %.1f in); reduced" % (where, AREA_W, AREA_H))
            w, h = min(w, AREA_W), min(h, AREA_H)
        cx, cy = min(max(x, 0.0), AREA_W - w), min(max(y, 0.0), AREA_H - h)
        if abs(cx - x) > 0.005 or abs(cy - y) > 0.005:
            warnings.append("%s: was outside the drawing area; moved inside" % where)
        fill = s.get("fill")
        if fill is not None and not (isinstance(fill, str) and HEX.match(fill)):
            warnings.append("%s: fill must be #RRGGBB; ignored" % where)
            fill = None
        shapes.append(dict(id=sid, kind=kind, label=label, pic=pic, web=web, key=key, x=cx, y=cy, w=w, h=h, fill=fill,
                           dashed=bool(s.get("dashed")), bold=bool(s.get("bold")), size=_num(s.get("size")), where=where))
    lines = []
    for n, c in enumerate(spec.get("lines", []), 1):
        where = "line %d" % n
        if not isinstance(c, dict):
            errors.append("%s: not an object" % where)
            continue
        for end in ("from", "to"):
            if str(c.get(end)) not in ids:
                errors.append("%s: %s %r is not a shape id" % (where, end, c.get(end)))
        try:
            cables.get(c.get("cable"))
        except CableError as e:
            errors.append("%s: %s" % (where, e))
        via = [(MARGIN + p[0], TOP - p[1]) for p in c.get("via", []) if isinstance(p, list) and len(p) == 2 and None not in map(_num, p)]
        if len(via) != len(c.get("via", [])):
            warnings.append("%s: some via points were not [x, y] numbers; ignored" % where)
        lines.append(dict(a=str(c.get("from")), b=str(c.get("to")), cable=c.get("cable"), via=via, where=where))
    if errors:
        raise BuildError("\n  ".join(["cannot draw this file:"] + errors))
    return shapes, lines, warnings


# ---- geometry (page coordinates, inches, y up) ----------------------------------------------------------------------------
def rect_of(s):
    return MARGIN + s["x"], TOP - s["y"] - s["h"], s["w"], s["h"]


def edge_point(r, target):
    """Midpoint of the side of rectangle r that faces `target`."""
    x, y, w, h = r
    dx, dy = target[0] - (x + w / 2), target[1] - (y + h / 2)
    if abs(dx) * h > abs(dy) * w:
        return (x + w if dx > 0 else x, y + h / 2)
    return (x + w / 2, y + h if dy > 0 else y)


def route(a, b, via):
    """Plain straight or square-cornered line between two rectangles, through the `via` points if given."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if via:
        pts = [edge_point(a, via[0])] + list(via) + [edge_point(b, via[-1])]
    else:
        ox0, ox1, oy0, oy1 = max(ax, bx), min(ax + aw, bx + bw), max(ay, by), min(ay + ah, by + bh)
        if ox1 - ox0 > 0.1:                                     # share a column: one vertical line
            x = (ox0 + ox1) / 2
            pts = [(x, ay), (x, by + bh)] if ay >= by else [(x, ay + ah), (x, by)]
        elif oy1 - oy0 > 0.1:                                   # share a row: one horizontal line
            y = (oy0 + oy1) / 2
            pts = [(ax + aw, y), (bx, y)] if ax < bx else [(ax, y), (bx + bw, y)]
        else:                                                   # elbow through the middle of the gap
            acx, acy, bcx, bcy = ax + aw / 2, ay + ah / 2, bx + bw / 2, by + bh / 2
            if abs(bcx - acx) >= abs(bcy - acy):
                p, q = ((ax + aw, acy), (bx, bcy)) if bcx > acx else ((ax, acy), (bx + bw, bcy))
                m = (p[0] + q[0]) / 2
                pts = [p, (m, p[1]), (m, q[1]), q]
            else:
                p, q = ((acx, ay), (bcx, by + bh)) if bcy < acy else ((acx, ay + ah), (bcx, by))
                m = (p[1] + q[1]) / 2
                pts = [p, (p[0], m), (q[0], m), q]
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


def crosses(pts, r, inset=0.03):
    """True if a horizontal or vertical segment of the line passes through the inside of rectangle r."""
    x, y, w, h = r
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if abs(y1 - y2) < 1e-6 and y + inset < y1 < y + h - inset and min(x1, x2) < x + w - inset and max(x1, x2) > x + inset:
            return True
        if abs(x1 - x2) < 1e-6 and x + inset < x1 < x + w - inset and min(y1, y2) < y + h - inset and max(y1, y2) > y + inset:
            return True
    return False


def overlapping(shapes):
    pairs, boxes = [], [s for s in shapes if s["kind"] != "zone"]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > 0.02 and \
               min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > 0.02:
                pairs.append((a["id"], b["id"]))
    return pairs


# ---- drawing --------------------------------------------------------------------------------------------------------------
def label_size(s, w, h, sizes, bold=False):
    """The shape's own size if it gave one, else the largest that fits; the font floor (with a warning) when nothing fits."""
    if s["size"]:
        return max(s["size"], FONT_FLOOR), None
    try:
        return fit_size(s["label"], w, h, sizes, bold), None
    except TextFitError:
        return FONT_FLOOR, "%s: label may not fit its box; make it larger or shorter" % s["where"]


def draw_shape(page, s):
    x, y, w, h = rect_of(s)
    warn = None
    if s["kind"] == "zone":
        page.rect("zone", x, y, w, h, fill=s["fill"] or ZONE_FILL, line=ZONE_LINE, lw=1.0, pattern=2 if s["dashed"] else 1, key=s["key"])
        if s["label"]:
            size, warn = label_size(s, w - 0.1, 0.25, (9, 8, 7, 6.5, 6), True)
            page.text(x + 0.05, y + h - 0.28, w - 0.1, 0.25, s["label"], size=size, bold=True, halign=0, valign=0)
    elif s["kind"] == "text":
        size, warn = label_size(s, w, h, BOX_SIZES, s["bold"])
        page.text(x, y, w, h, s["label"], size=size, bold=s["bold"], key=s["key"])
    elif s["pic"] and h > 0.4:
        draw_picture(page, s["pic"], s["label"], x, y, w, h, s["key"], soft=True)
    else:
        size, warn = label_size(s, w, h, BOX_SIZES)
        page.rect("icon", x, y, w, h, fill=s["fill"] or BOX_FILL, line=BOX_LINE, lw=0.75, pattern=2 if s["dashed"] else 1,
                  text=s["label"], size=size, bold=s["bold"], key=s["key"])
    return warn


def build(spec, base, out, comps=None, cables=None, spec_dir="."):
    comps, cables = comps or Components(), cables or Cables()
    shapes, lines, warnings = prepare(spec, comps, cables, spec_dir)
    by_id = {s["id"]: s for s in shapes}
    page = Page()
    notes = [str(n) for n in spec.get("notes", [])]
    n_web = sum(1 for s in shapes if s["web"])
    if n_web:
        notes.append("%d picture(s) come from outside the component library; the source is in the shape data." % n_web)
    missing = [k for k in footer.REQUIRED if not str(spec.get("project", {}).get(k, "")).strip()]
    if missing:
        warnings.append("footer values printing TBC: %s; if the engineer or the documents gave any of them, add them to \"project\"" % ", ".join(missing))
    used = sorted({c["cable"] for c in lines})
    try:
        footer.build_footer(page, spec.get("project", {}), cables.legend(used), notes, allow_tbc=True)
    except footer.FooterError as e:
        raise BuildError("footer: %s" % e)

    for s in (s for s in shapes if s["kind"] == "zone"):                  # zones behind, then lines, then everything else on top
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    n_lines = 0
    for c in lines:
        pts = route(rect_of(by_id[c["a"]]), rect_of(by_id[c["b"]]), c["via"])
        color, pattern = cables.line_style(c["cable"])
        page.line(pts, color, pattern, lw=1.25, key="%s->%s" % (c["a"], c["b"]))
        n_lines += 1
        for s in shapes:
            if s["kind"] != "zone" and s["id"] not in (c["a"], c["b"]) and crosses(pts, rect_of(s)):
                warnings.append("%s (%s to %s) passes through shape %r; add a \"via\" point to route round it" % (c["where"], c["a"], c["b"], s["id"]))
    for s in (s for s in shapes if s["kind"] != "zone"):
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    warnings += ["shapes %r and %r overlap" % p for p in overlapping(shapes)]
    write_vsdx(page, out, base, title=str(spec.get("project", {}).get("project", "Architecture")))
    return {"out": out, "shapes": len(shapes), "lines": n_lines, "warnings": warnings, "notes": notes, "page": page}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise BuildError("cannot read %s: %s" % (path, e))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--base", default=os.path.join(ROOT, "base", "base.vsdx"))
    ap.add_argument("--out", help="output .vsdx (default: Downloads\\out\\<file name>.vsdx)")
    ap.add_argument("--preview", action="store_true", help="also write a PNG preview next to the file (needs Pillow; development aid)")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", os.path.splitext(os.path.basename(a.spec))[0] + ".vsdx")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    try:
        r = build(load_json(a.spec), a.base, out, spec_dir=os.path.dirname(os.path.abspath(a.spec)))
    except BuildError as e:
        print("NOT BUILT: %s" % e)
        sys.exit(1)
    print("built %s: %d shapes, %d lines" % (r["out"], r["shapes"], r["lines"]))
    for w in r["warnings"]:
        print("  warning:", w)
    if a.preview:
        import dev_preview
        png = os.path.splitext(out)[0] + "_preview.png"
        dev_preview.render(r["page"], png)
        print("preview:", png)
