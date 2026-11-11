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
import imaging
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
LOW_RES = 120                                                # a web picture whose shorter side is under this many pixels draws a "low resolution" warning
RING_FILL, ELLIPSE_POINTS = "#E5F7E8", 72                   # fibre-ring ellipse: light-green fill; drawn as a closed polygon of this many points
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
    errors, warnings, shapes, ids, noted = [], [], [], set(), set()
    cleaned, bg_skipped = {}, {}                                  # picture file -> (cleaned path, status); status -> picture names it applied to
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
        if kind not in ("box", "zone", "text", "ellipse"):
            errors.append('%s: kind must be "box", "zone", "text" or "ellipse"' % where)
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
                px = png_size(path)                              # measured before cleaning: the low-resolution warning is about the original
                if str(s["image"]) not in cleaned:               # web pictures only (never library pictures or the logo); once per file
                    cleaned[str(s["image"])] = imaging.clean(path)
                path, bg_status = cleaned[str(s["image"])]
                if bg_status not in (imaging.REMOVED, imaging.TRANSPARENT):
                    bg_skipped.setdefault(bg_status, [])
                    if os.path.basename(str(s["image"])) not in bg_skipped[bg_status]:
                        bg_skipped[bg_status].append(os.path.basename(str(s["image"])))
                png_size(path)
                pic, web = path, True
                key = "image:%s|%s" % (s.get("image_source", "unknown"), sid)
                src_path = str(s["image"])
                if not str(s.get("image_source") or "").strip() and ("nosrc", src_path) not in noted:
                    noted.add(("nosrc", src_path))
                    warnings.append("picture %s has no \"image_source\" (URL or OEM site name); add one so the source is recorded" % os.path.basename(src_path))
                if min(px) < LOW_RES and ("lowres", src_path) not in noted:
                    noted.add(("lowres", src_path))
                    warnings.append("picture %s is low resolution (%d x %d px); it may look soft; look for a larger one" % (os.path.basename(src_path), px[0], px[1]))
            except (OSError, ValueError) as e:
                warnings.append("%s: picture not usable (%s); drawn as a box" % (where, e))
        x, y = _num(s.get("x")), _num(s.get("y"))
        if x is None or y is None:
            errors.append("%s: x and y (inches from the top-left of the drawing area) are required" % where)
            continue
        sized = kind in ("zone", "ellipse")                      # these have no default size: the file must give w and h
        dw, dh = DEFAULT_SIZE["picture" if pic and kind == "box" else kind if not sized else "box"]
        w, h = _num(s.get("w", dw if not sized else None)), _num(s.get("h", dh if not sized else None))
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append("%s: w and h must be positive numbers%s" % (where, " (zones and ellipses need them)" if sized else ""))
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
        edge = s.get("line")
        if edge is not None and not (isinstance(edge, str) and HEX.match(edge)):
            warnings.append("%s: line must be #RRGGBB; ignored" % where)
            edge = None
        lw = _num(s.get("lw"))
        dashed = bool(s.get("dashed"))
        if kind == "ellipse":                                    # the outline is a cable line: fibre (green, dashed) unless another cable is named
            try:
                st = cables.style(s.get("cable", "fibre"))
            except CableError as e:
                errors.append("%s: %s" % (where, e))
                continue
            edge, dashed = st["color"], st["pattern"] == 2
        shapes.append(dict(id=sid, kind=kind, label=label, pic=pic, web=web, key=key, x=cx, y=cy, w=w, h=h, fill=fill,
                           dashed=dashed, vertical=bool(s.get("vertical")), bold=bool(s.get("bold")), italic=bool(s.get("italic")), size=_num(s.get("size")),
                           edge=edge, lw=min(max(lw, 0.25), 3.0) if lw else None, level=s.get("level"),
                           match=s.get("image_match") if s.get("image_match") in ("exact", "generic") else None,
                           source=str(s.get("image_source") or ""), where=where))
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
        label = c.get("label")
        if label is not None and not isinstance(label, str):
            warnings.append("%s: label must be text; ignored" % where)
            label = None
        label = (label or "").strip() or None
        points = None
        if c.get("points") is not None:                 # a fully explicit route; it bypasses route()
            raw = c["points"]
            pts = [(MARGIN + p[0], TOP - p[1]) for p in raw if isinstance(p, list) and len(p) == 2 and None not in map(_num, p)] \
                if isinstance(raw, list) else []
            if isinstance(raw, list) and len(pts) == len(raw) and len(pts) >= 2:
                points = pts
            else:
                warnings.append("%s: points must be a list of at least two [x, y] numbers; ignored" % where)
        lines.append(dict(a=str(c.get("from")), b=str(c.get("to")), cable=c.get("cable"), via=via, label=label, points=points, where=where))
    for status, names in bg_skipped.items():
        warnings.append("background not removed from %s (%s)%s" % (", ".join(names), status, "; install it once with: pip install pillow"
                                                                 if status == imaging.NO_PILLOW else ""))
    if errors:
        raise BuildError("\n  ".join(["cannot draw this file:"] + errors))
    return shapes, lines, warnings


# ---- geometry (page coordinates, inches, y up) ----------------------------------------------------------------------------
def rect_of(s):
    return MARGIN + s["x"], TOP - s["y"] - s["h"], s["w"], s["h"]


def edge_point(r, target, slot=0, slots=1):
    """The side of rectangle r that faces `target`. With one line on that side (the default) the point is the middle of the side; with
    `slots` lines, line number `slot` (0-based) gets its own evenly spaced point so lines do not stack."""
    x, y, w, h = r
    dx, dy = target[0] - (x + w / 2), target[1] - (y + h / 2)
    f = (slot + 1) / (slots + 1)
    if abs(dx) * h > abs(dy) * w:
        return (x + w if dx > 0 else x, y + h * f)
    return (x + w * f, y + h if dy > 0 else y)


def route(a, b, via, slot_a=(0, 1), slot_b=(0, 1)):
    """Plain straight or square-cornered line between two rectangles, through the `via` points if given. slot_a / slot_b = (slot, slots)
    spread several lines over one side of a shape (see edge_point); the default is the middle of the side."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    if via:
        pts = [edge_point(a, via[0], *slot_a)] + list(via) + [edge_point(b, via[-1], *slot_b)]
    else:
        ox0, ox1, oy0, oy1 = max(ax, bx), min(ax + aw, bx + bw), max(ay, by), min(ay + ah, by + bh)
        custom = tuple(slot_a) != (0, 1) or tuple(slot_b) != (0, 1)      # asked for spread ends: no straight-line shortcut
        if ox1 - ox0 > 0.1 and not custom:                      # share a column: one vertical line
            x = (ox0 + ox1) / 2
            pts = [(x, ay), (x, by + bh)] if ay >= by else [(x, ay + ah), (x, by)]
        elif oy1 - oy0 > 0.1 and not custom:                    # share a row: one horizontal line
            y = (oy0 + oy1) / 2
            pts = [(ax + aw, y), (bx, y)] if ax < bx else [(ax, y), (bx + bw, y)]
        else:                                                   # elbow through the middle of the gap
            fa, fb = (slot_a[0] + 1) / (slot_a[1] + 1), (slot_b[0] + 1) / (slot_b[1] + 1)    # 0.5 for the default single slot
            if abs((bx + bw / 2) - (ax + aw / 2)) >= abs((by + bh / 2) - (ay + ah / 2)):
                p, q = ((ax + aw, ay + ah * fa), (bx, by + bh * fb)) if bx + bw / 2 > ax + aw / 2 else ((ax, ay + ah * fa), (bx + bw, by + bh * fb))
                m = (p[0] + q[0]) / 2
                pts = [p, (m, p[1]), (m, q[1]), q]
            else:
                p, q = ((ax + aw * fa, ay), (bx + bw * fb, by + bh)) if by + bh / 2 < ay + ah / 2 else ((ax + aw * fa, ay + ah), (bx + bw * fb, by))
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
        page.rect("zone", x, y, w, h, fill=s["fill"] or ZONE_FILL, line=s["edge"] or ZONE_LINE, lw=s["lw"] or 1.0,
                  pattern=2 if s["dashed"] else 1, key=s["key"])
        if s["label"] and s["vertical"]:                           # a title strip: white bold text turned to read upwards
            size, warn = label_size(s, h - 0.1, w - 0.04, (9, 8, 7, 6.5, 6), True)
            page.text(x, y, w, h, s["label"], size=size, bold=True, color="#FFFFFF", rot=True)
        elif s["label"]:
            size, warn = label_size(s, w - 0.1, 0.25, (9, 8, 7, 6.5, 6), True)
            page.text(x + 0.05, y + h - 0.28, w - 0.1, 0.25, s["label"], size=size, bold=not s["italic"], italic=s["italic"], halign=0, valign=0)
    elif s["kind"] == "ellipse":
        pts = [(x + w / 2 + w / 2 * math.cos(2 * math.pi * i / ELLIPSE_POINTS), y + h / 2 + h / 2 * math.sin(2 * math.pi * i / ELLIPSE_POINTS))
               for i in range(ELLIPSE_POINTS)]
        page.polygon(pts, fill=s["fill"] or RING_FILL, line=s["edge"], pattern=2 if s["dashed"] else 1, lw=s["lw"] or 1.25, key=s["key"],
                     text=s["label"], size=s["size"] or 8, bold=True)
    elif s["kind"] == "text":
        size, warn = label_size(s, w, h, BOX_SIZES, s["bold"])
        page.text(x, y, w, h, s["label"], size=size, bold=s["bold"], italic=s["italic"], key=s["key"])
    elif s["pic"] and h > 0.4:
        draw_picture(page, s["pic"], s["label"], x, y, w, h, s["key"], soft=True)
    else:
        size, warn = label_size(s, w, h, BOX_SIZES)
        page.rect("icon", x, y, w, h, fill=s["fill"] or BOX_FILL, line=s["edge"] or BOX_LINE, lw=s["lw"] or 0.75, pattern=2 if s["dashed"] else 1,
                  text=s["label"], size=size, bold=s["bold"], key=s["key"])
    return warn


LABEL_SIZE, LABEL_H = 6.5, 0.15
STAMP_W, STAMP_Y, STAMP_H = 4.0, 0.08, 0.18      # version stamp: below the footer frame (which starts at y = 0.30), right-aligned to it


def plugin_version():
    """The plugin version from .claude-plugin/plugin.json ('unknown' if it cannot be read)."""
    try:
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            return str(json.load(fh)["version"])
    except (OSError, ValueError, KeyError):
        return "unknown"


def _hit(a, b, m=0.02):
    return a[0] < b[0] + b[2] + m and b[0] < a[0] + a[2] + m and a[1] < b[1] + b[3] + m and b[1] < a[1] + a[3] + m


def draw_line_label(page, pts, label, taken=None, avoid=()):
    """A small white-backed text on the line (drawn after the line, before the shapes). It goes in the middle of the longest segment; when
    that spot is already used by another label, or lies on a shape or a band header (`avoid`), it slides along the segment or moves to
    another one. `taken` is the list of label rectangles already placed (this label is added to it)."""
    w = len(label) * 0.62 * LABEL_SIZE / 72 + 0.12                  # generous: capitals are wider than the average letter, and a label must stay on one line
    taken = [] if taken is None else taken
    segs = sorted(zip(pts, pts[1:]), key=lambda s: -math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
    cands = []
    for i, (p, q) in enumerate(segs):
        if i and math.hypot(q[0] - p[0], q[1] - p[1]) < w + 0.1:
            continue                                                # a short segment would be hidden by its own label
        for f in (0.5, 0.35, 0.65, 0.25, 0.75):
            mx, my = p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f
            cands.append((mx - w / 2, my - LABEL_H / 2, w, LABEL_H))
    rect = next((c for c in cands if not any(_hit(c, o) for o in list(taken) + list(avoid))), cands[0])
    taken.append(rect)
    page.rect("text", rect[0], rect[1], w, LABEL_H, fill="#FFFFFF", line=None, text=label, size=LABEL_SIZE, key="label:" + label)


def build(spec, base, out, comps=None, cables=None, spec_dir="."):
    comps, cables = comps or Components(), cables or Cables()
    report, v1 = {"added_by_rule": [], "assumed": [], "pictures": [], "warnings": []}, None
    if isinstance(spec, dict) and spec.get("spec_version") == 2:       # meaning-based spec: placed by compile_v2, then drawn as below
        import compile_v2
        try:
            spec = compile_v2.compile_v2(spec, comps, cables, spec_dir, area=(AREA_W, AREA_H))
        except compile_v2.SpecError as e:
            raise BuildError(str(e))
        report.update(spec.pop("_report"))
        v1 = json.loads(json.dumps(spec))                              # what was compiled, for debugging (--emit-v1)
        spec["_source_spec_version"] = 2                                # for the version stamp only; a saved v1 emit still builds on its own
    shapes, lines, warnings = prepare(spec, comps, cables, spec_dir)
    warnings = list(report["warnings"]) + warnings
    by_id = {s["id"]: s for s in shapes}
    page = Page()
    notes = [str(n) for n in spec.get("notes", [])]
    n_web = sum(1 for s in shapes if s["web"])
    n_generic = sum(1 for s in shapes if s["web"] and s["match"] == "generic")
    if n_web:
        notes.append("%d picture(s) from outside the component library%s; sources are in the shape data."
                     % (n_web, " (%d generic)" % n_generic if n_generic else ""))
    proj = spec.get("project", {})
    missing = [k for k in footer.REQUIRED if not str(proj.get(k) or proj.get(next((a for a, v in footer.ALIASES.items() if v == k), k)) or "").strip()]
    if missing:
        warnings.append("footer values printing TBC: %s; if the engineer or the documents gave any of them, add them to \"project\""
                        % ", ".join(footer.FIELD_NAMES.get(k, k) for k in missing))
    used = sorted({c["cable"] for c in lines})
    try:
        footer.build_footer(page, spec.get("project", {}), cables.legend(used), notes, allow_tbc=True)
    except footer.FooterError as e:
        raise BuildError("footer: %s" % e)
    version = plugin_version()
    stamp = "RPS Architecture plugin v%s | spec v%d" % (version, spec.get("_source_spec_version", 1))
    page.text(footer.X1 - STAMP_W, STAMP_Y, STAMP_W, STAMP_H, stamp, size=6, halign=2, valign=1, color="#7F7F7F", key="version-stamp")

    for s in (s for s in shapes if s["kind"] == "zone"):                  # zones behind, then lines, then everything else on top
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    n_lines, taken = 0, []
    avoid = [rect_of(s) for s in shapes if s["kind"] != "zone" or s["id"].startswith("hdr_")]     # labels keep off shapes and band headers
    for c in lines:
        pts = c["points"] or route(rect_of(by_id[c["a"]]), rect_of(by_id[c["b"]]), c["via"])
        st = cables.style(c["cable"])
        page.line(pts, st["color"], st["pattern"], lw=1.25, key="%s->%s" % (c["a"], c["b"]), arrow=st["arrow"])
        n_lines += 1
        if c["label"]:
            draw_line_label(page, pts, c["label"], taken, avoid)
        elif c["cable"] == "modbus":
            warnings.append("%s (%s to %s): Modbus lines should say RTU or TCP; add a \"label\"" % (c["where"], c["a"], c["b"]))
        for s in shapes:
            if s["kind"] != "zone" and s["id"] not in (c["a"], c["b"]) and crosses(pts, rect_of(s)):
                warnings.append("%s (%s to %s) passes through shape %r; add a \"via\" point to route round it" % (c["where"], c["a"], c["b"], s["id"]))
    for s in (s for s in shapes if s["kind"] != "zone"):
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    warnings += ["shapes %r and %r overlap" % p for p in overlapping(shapes)]
    boxes = [s for s in shapes if s["kind"] == "box"]                   # what each picture is, and which items stayed boxes
    names = [s["label"].split("\n")[0] or s["id"] for s in boxes]
    stems = [re.sub(r"-\d\d$", "", n) for n in names]                   # numbered copies ("Pressure transmitter-01 ... -12") are one entry
    stem_count = {b: stems.count(b) for b in stems}
    seen = {}
    for s, name, stem in zip(boxes, names, stems):
        shown = stem if stem_count[stem] > 1 else name
        if s["web"]:
            how = "web, generic picture" if s["match"] == "generic" else "web, exact picture"
            entry = "%s: %s (%s)" % (shown, how, s["source"] or "source not given")
            warn = "generic picture used for %s (exact model not found)" % shown if s["match"] == "generic" else None
        elif s["pic"]:
            entry, warn = "%s: library (%s)" % (shown, s["key"].split(":", 1)[-1]), None
        else:
            entry = "%s: box" % shown
            warn = "BOX: no picture found for %s" % shown if s["level"] == "L0" else None
        if entry in seen:
            seen[entry] += 1
            continue
        seen[entry] = 1
        report["pictures"].append(entry)
        if warn:
            warnings.append(warn)
    if any(v > 1 for v in seen.values()):                               # say how many copies an entry stands for
        report["pictures"] = ["%s [x%d]" % (e, seen[e]) if seen[e] > 1 else e for e in report["pictures"]]
    report["warnings"] = warnings
    write_vsdx(page, out, base, title=str(spec.get("project", {}).get("project", "Architecture")), description=stamp)
    return {"out": out, "shapes": len(shapes), "lines": n_lines, "warnings": warnings, "notes": notes, "page": page, "report": report,
            "v1": v1, "spec_version": spec.get("_source_spec_version", 1)}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise BuildError("cannot read %s: %s" % (path, e))


def print_report(r):
    """The build report. v2 prints ADDED BY RULE / ASSUMED / PICTURES / WARNINGS (the AI pastes ASSUMED, PICTURES and WARNINGS into its reply)."""
    rep = r["report"]
    print("ADDED BY RULE")
    for x in rep["added_by_rule"] or ["(nothing)"]:
        print("  -", x)
    print("ASSUMED")
    for x in rep["assumed"] or ["(nothing)"]:
        print("  -", x)
    print("PICTURES")
    for x in rep["pictures"] or ["(none)"]:
        print("  -", x)
    print("WARNINGS")
    for x in r["warnings"] or ["(none)"]:
        print("  -", x)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--base", default=os.path.join(ROOT, "base", "base.vsdx"))
    ap.add_argument("--out", help="output .vsdx (default: Downloads\\out\\<file name>.vsdx)")
    ap.add_argument("--preview", action="store_true", help="also write a PNG preview next to the file (needs Pillow; development aid)")
    ap.add_argument("--emit-v1", metavar="FILE", help="for a v2 spec: also write the free-form spec the compiler made (debugging aid)")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", os.path.splitext(os.path.basename(a.spec))[0] + ".vsdx")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    try:
        r = build(load_json(a.spec), a.base, out, spec_dir=os.path.dirname(os.path.abspath(a.spec)))
    except BuildError as e:
        print("NOT BUILT: %s" % e)
        sys.exit(1)
    print("built %s: %d shapes, %d lines" % (r["out"], r["shapes"], r["lines"]))
    if r["spec_version"] == 2:
        print_report(r)
    else:
        for w in r["warnings"]:
            print("  warning:", w)
    if a.emit_v1 and r["v1"] is not None:
        with open(a.emit_v1, "w", encoding="utf-8") as fh:
            json.dump(r["v1"], fh, indent=1)
        print("free-form spec:", a.emit_v1)
    if a.preview:
        import dev_preview
        png = os.path.splitext(out)[0] + "_preview.png"
        dev_preview.render(r["page"], png)
        print("preview:", png)
