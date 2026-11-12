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
import pictures
import router
from cables import CableError, Cables
from components import Components
from draw import BOX_FILL, BOX_LINE, BOX_SIZES, LABEL_SIZES, LABEL_ZONE, draw_picture
from textfit import TextFitError, fit_size
from vsdx_writer import A3_H, A3_W, FONT_FLOOR, Page, png_size, write_vsdx

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MARGIN = footer.X0
TOP, BOTTOM = A3_H - MARGIN, footer.TOP + 0.12      # the drawing area runs between these page heights
AREA_W, AREA_H = A3_W - 2 * MARGIN, TOP - BOTTOM
DEFAULT_SIZE = {"box": (1.35, 1.25), "picture": (1.35, 1.25), "text": (1.50, 0.30)}   # every device is a picture with its caption underneath
MIN_DEVICE_H = 0.60                                     # a device cell shorter than this cannot hold a picture and a caption
GENERIC_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "icons", "generic_device.png")
BEHIND = ("zone", "group")                              # drawn first, behind the lines and shapes
SEE_THROUGH = ("zone", "group", "pill")                 # lines may run over these; they are not obstacles
GROUP_FILL, GROUP_LINE, PILL_BLUE = "#F3F8FE", "#7FA3D6", "#1456C0"
PILL_LIGHT_FILL, PILL_LIGHT_LINE, PILL_LIGHT_TEXT = "#D9E9FB", "#2F6FD0", "#0B3C8C"
CABLE_LW = 1.5
ZONE_FILL, ZONE_LINE = "#F7F9FC", "#9AA5B1"
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")
LAYERS_PATH = os.path.join(ROOT, "data", "layers.json")
SCOPE_LINE = "#123A7A"                                  # outline on scope-coloured boxes so they stand out on the layer panels


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
        if kind not in ("box", "zone", "text", "group", "pill"):
            errors.append('%s: kind must be "box" (a device: picture with caption), "zone", "group", "pill" or "text"' % where)
            continue
        label, pic, key, web = str(s.get("label", "")).strip(), None, "shape:" + sid, False
        sub = str(s.get("sublabel", "")).strip() or None
        if sub is None and "\n" in label:                              # "SCADA Server\n(Primary)": first line is the name, the rest the blue line
            label, _, rest = label.partition("\n")
            label, sub = label.strip(), (rest.replace("\n", " ").strip() or None)
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
        if pic and kind == "box":                                       # transparent background, trimmed, not oversized
            pic, note = pictures.prepare(pic)
            if note:
                warnings.append("%s: %s" % (where, note))
        elif kind == "box":                                             # no picture given: a generic device icon, never a plain box
            pic, key = GENERIC_ICON, "generic:" + sid
            warnings.append("%s: no picture (give \"component\" or \"image\"); a generic device icon is used" % where)
        x, y = _num(s.get("x")), _num(s.get("y"))
        layer = s.get("layer")
        auto_x = layer is not None and x is None
        if layer is not None:
            if kind in BEHIND:
                errors.append("%s: a %s cannot be placed in a layer" % (where, kind))
                continue
            x, y = (0.0 if x is None else x), 0.0                  # y is set by the layer (centred); x too unless given
        if x is None or y is None:
            errors.append("%s: x and y (inches from the top-left of the drawing area) are required" % where)
            continue
        needs_size = kind in ("zone", "group")
        if kind == "pill":
            dw, dh = min(4.0, 0.085 * len(label) + 0.6), 0.26
        else:
            dw, dh = DEFAULT_SIZE["picture" if pic and kind == "box" else kind if not needs_size else "box"]
        w, h = _num(s.get("w", None if needs_size else dw)), _num(s.get("h", None if needs_size else dh))
        if w is None or h is None or w <= 0 or h <= 0:
            errors.append("%s: w and h must be positive numbers%s" % (where, " (zones and groups need them)" if needs_size else ""))
            continue
        if kind == "box" and h < MIN_DEVICE_H:
            warnings.append("%s: too short for a picture and its caption; raised to %.2f in" % (where, MIN_DEVICE_H))
            h = MIN_DEVICE_H
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
        line = None
        scope = s.get("scope")
        if scope is not None:
            if scope not in footer.SCOPE:
                warnings.append('%s: scope must be "avanceon" or "other"; ignored' % where)
            else:
                pass                                                    # scope is shown as a coloured block per layer (apply_layers), not on the shape
        shapes.append(dict(id=sid, kind=kind, label=label, pic=pic, web=web, key=key, x=cx, y=cy, w=w, h=h, fill=fill,
                           dashed=bool(s.get("dashed")), bold=bool(s.get("bold")), size=_num(s.get("size")), where=where,
                           layer=layer, auto_x=auto_x, line=line, sub=sub, scope=scope if scope in footer.SCOPE else None))
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
        via = []
        for p in c.get("via", []):
            if isinstance(p, list) and len(p) == 2 and None not in map(_num, p):
                px, py = MARGIN + _num(p[0]), TOP - _num(p[1])
                cx, cy = min(max(px, MARGIN), MARGIN + AREA_W), min(max(py, BOTTOM), TOP)
                if abs(cx - px) > 0.005 or abs(cy - py) > 0.005:
                    warnings.append("%s: via point [%s, %s] is outside the drawing area; moved inside" % (where, p[0], p[1]))
                via.append((cx, cy))
        if len(via) != len(c.get("via", [])):
            warnings.append("%s: some via points were not [x, y] numbers; ignored" % where)
        sides = {}
        for key in ("from_side", "to_side"):
            v = c.get(key)
            if v is not None and v not in router.SIDES:
                warnings.append('%s: %s must be "left", "right", "top" or "bottom"; ignored' % (where, key))
            elif v is not None:
                sides[key] = v
        lines.append(dict(a=str(c.get("from")), b=str(c.get("to")), cable=c.get("cable"), via=via, where=where,
                          straight=bool(c.get("straight")), **sides))
    if errors:
        raise BuildError("\n  ".join(["cannot draw this file:"] + errors))
    return shapes, lines, warnings


# ---- layers (Purdue bands) ------------------------------------------------------------------------------------------------------
LAYER_GAP, BAND_W, LAYER_PAD, LAYER_R = 0.12, 0.45, 0.15, 0.08
BLOCK_GAP, BLOCK_PAD = 0.12, 0.08                         # space between scope blocks / between a block and its layer edge
BAND_FILL, PANEL_FILL, PANEL_LINE = "#123A7A", "#E6EEF8", "#8EA9CC"      # dark-blue band, pale panel (the approved layer style)


def load_layers(path=LAYERS_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["layers"]


def apply_layers(spec, shapes, warnings):
    """Stack the requested layers in the standard order so together they fill the whole drawing area, and place the shapes tagged with
    a layer: spread evenly across the layer's width and centred in its height. Returns the panels [{id, label, x, y, w, h}]
    (inches from the top-left of the drawing area). No "layers" in the file: nothing happens and shapes stay where they were put."""
    wanted = spec.get("layers")
    tagged = [s for s in shapes if s["layer"] is not None]
    if wanted is None:
        if tagged:
            raise BuildError('shapes use "layer" but the file has no "layers" list, e.g. "layers": ["scada", "control", "field"]')
        return []
    table = load_layers()
    ids = [t["id"] for t in table]
    if not isinstance(wanted, list) or not wanted or any(w not in ids for w in wanted) or len(set(wanted)) != len(wanted):
        raise BuildError('"layers" must be a list of distinct layer ids from: %s' % ", ".join(ids))
    bad = sorted({s["layer"] for s in tagged if s["layer"] not in wanted})
    if bad:
        raise BuildError("shape layer(s) %s are not in the file's \"layers\" list" % ", ".join(repr(b) for b in bad))
    order = [t for t in table if t["id"] in wanted]                 # standard order, whatever order the file gave
    n = len(order)
    h = (AREA_H - (n - 1) * LAYER_GAP) / n                           # equal bands: the full drawing area, nothing left empty
    panels = []
    for i, t in enumerate(order):
        y = i * (h + LAYER_GAP)
        panels.append(dict(id=t["id"], label=t["label"], x=0.0, y=y, w=AREA_W, h=h, blocks=[]))
        members = [s for s in tagged if s["layer"] == t["id"]]
        if not members:
            continue
        left, width = BAND_W + LAYER_PAD, AREA_W - BAND_W - 2 * LAYER_PAD
        k = min(1.0, (h - 0.30) / max(s["h"] for s in members))      # a shape taller than its layer is scaled down to fit
        groups = [[s for s in members if s["scope"] == sc] for sc in ("avanceon", "other", None)]
        groups = [g for g in groups if g]                            # Avanceon on the left, other scope on the right, unscoped last
        auto = any(s["auto_x"] for s in members)
        if auto:
            fixed = (len(groups) - 1) * BLOCK_GAP + sum((len(g) + 1) * 0.15 for g in groups)
            k = min(k, (width - fixed) / sum(s["w"] for s in members))
        if k < 1.0:
            if k < 0.5:
                warnings.append("layer %r is very crowded (%d shapes); shapes were reduced to %.0f%% and may be hard to read" % (t["id"], len(members), 100 * max(k, 0.5)))
                k = max(k, 0.5)
            for s in members:
                s["w"], s["h"] = s["w"] * k, s["h"] * k
        for s in members:
            s["y"] = y + (h - s["h"]) / 2
        by, bh = y + BLOCK_PAD, h - 2 * BLOCK_PAD
        if auto:
            need = [sum(s["w"] for s in g) + (len(g) + 1) * 0.15 for g in groups]
            extra = max(0.0, width - sum(need) - (len(groups) - 1) * BLOCK_GAP)
            x = left
            for g, nd in zip(groups, need):
                bw = nd + extra * nd / sum(need)
                gap = (bw - sum(s["w"] for s in g)) / (len(g) + 1)
                cx = x + gap
                for s in g:
                    s["x"] = cx
                    cx += s["w"] + gap
                if g[0]["scope"]:
                    panels[-1]["blocks"].append(dict(scope=g[0]["scope"], x=x, y=by, w=bw, h=bh))
                x += bw + BLOCK_GAP
        else:                                                        # positions given by the file: block = the span of that scope's shapes
            for g in groups:
                if g[0]["scope"]:
                    x0, x1 = min(s["x"] for s in g) - 0.15, max(s["x"] + s["w"] for s in g) + 0.15
                    panels[-1]["blocks"].append(dict(scope=g[0]["scope"], x=max(x0, left), y=by, w=min(x1, left + width) - max(x0, left), h=bh))
    return panels


def draw_layer(page, p):
    """One layer panel: pale rounded body, dark-blue band on the left with the layer name in white, rotated to read bottom to top."""
    x, y, w, h = MARGIN + p["x"], TOP - p["y"] - p["h"], p["w"], p["h"]
    page.rect("zone", x, y, w, h, fill=PANEL_FILL, line=PANEL_LINE, lw=0.75, rounding=LAYER_R, key="layer:" + p["id"])
    r = LAYER_R
    pts = [(x + BAND_W, y)]                                                      # band: square on the right, rounded on the left
    pts += [(x + r + r * math.cos(math.radians(270 - 15 * k)), y + r + r * math.sin(math.radians(270 - 15 * k))) for k in range(7)]
    pts += [(x + r + r * math.cos(math.radians(180 - 15 * k)), y + h - r + r * math.sin(math.radians(180 - 15 * k))) for k in range(7)]
    pts.append((x + BAND_W, y + h))
    page.poly("zone", pts, fill=BAND_FILL, line=None, key="layer-band:" + p["id"])
    for b in p.get("blocks", []):                                                # scope blocks: light blue Avanceon, light pink other scope, no text
        page.rect("zone", MARGIN + b["x"], TOP - b["y"] - b["h"], b["w"], b["h"], fill=footer.SCOPE[b["scope"]][1], line=SCOPE_LINE, lw=0.75,
                  rounding=0.06, key="scope-block:%s:%s" % (p["id"], b["scope"]))
    size = fit_size(p["label"], h - 0.1, BAND_W - 0.06, (12, 11, 10, 9, 8, 7, 6.5, 6), True)
    page.rect("text", x, y, BAND_W, h, fill=None, line=None, text=p["label"], size=size, bold=True, text_angle=90, color="#FFFFFF",
              key="layer-name:" + p["id"])
    return size


# ---- fibre rings ------------------------------------------------------------------------------------------------------------
RING_FILL = "#E5F8E5"                                   # light green inside the ring (approved ring illustration)
RING_GAP, RING_H, RING_MARGIN, RING_MIN_W = 0.50, 0.60, 0.90, 3.0


def prepare_rings(spec, shapes, cables):
    """Validated rings: [{'id', 'label', 'cable', 'nodes': [shape ids in connection order], 'box': None | (x, y, w, h)}].
    Raises BuildError for what cannot be drawn."""
    raw = spec.get("rings", [])
    if not isinstance(raw, list):
        raise BuildError('"rings" must be a list')
    by_id = {s["id"]: s for s in shapes}
    errors, rings = [], []
    for n, r in enumerate(raw, 1):
        where = "ring %d" % n
        if not isinstance(r, dict):
            errors.append("%s: not an object" % where)
            continue
        nodes = [str(v) for v in r.get("nodes", [])] if isinstance(r.get("nodes"), list) else []
        cable = r.get("cable", "fibre")
        try:
            cables.get(cable)
        except CableError as e:
            errors.append("%s: %s" % (where, e))
        if len(nodes) < 2:
            errors.append('%s: a ring needs its connected elements listed in "nodes" (at least 2)' % where)
        bad = [v for v in nodes if v not in by_id or by_id[v]["kind"] in SEE_THROUGH]
        if bad:
            errors.append("%s: node(s) %s are not shapes" % (where, ", ".join(repr(v) for v in bad)))
        if len(set(nodes)) != len(nodes):
            errors.append("%s: a node is listed twice; list each element once" % where)
        box = None
        if any(k in r for k in ("x", "y", "w", "h")):
            vals = [_num(r.get(k)) for k in ("x", "y", "w", "h")]
            if None in vals or vals[2] <= 0 or vals[3] <= 0:
                errors.append("%s: x, y, w and h must all be given as numbers (w and h positive), or all left out" % where)
            else:
                box = tuple(vals)
        rings.append(dict(id=str(r.get("id", "ring%d" % n)), label=str(r.get("label", "Fiber Optic Ring")).strip(), cable=cable,
                          nodes=nodes, box=box, where=where))
    if errors:
        raise BuildError("\n  ".join(["cannot draw this file:"] + errors))
    return rings


def ring_ellipse(rects, box, warnings, where):
    """The ring ellipse, always inside the drawing area. See _ring_ellipse."""
    x, y, w, h = _ring_ellipse(rects, box, warnings, where)
    w, h = min(w, AREA_W), min(h, AREA_H)
    nx, ny = min(max(x, MARGIN), MARGIN + AREA_W - w), min(max(y, BOTTOM), TOP - h)
    if abs(nx - x) > 0.005 or abs(ny - y) > 0.005:
        warnings.append("%s: the ring ellipse did not fit in the drawing area; moved inside" % where)
    return nx, ny, w, h


def _ring_ellipse(rects, box, warnings, where):
    """The ring ellipse (x, y, w, h in page inches). From the ring's own x/y/w/h if given; otherwise sized to its nodes: between the
    upper and lower groups of nodes, or just below (else above) the row when all nodes are on one side."""
    if box:
        x, y, w, h = box
        return MARGIN + x, TOP - y - h, w, h
    cx = [r[0] + r[2] / 2 for r in rects]
    cy = [r[1] + r[3] / 2 for r in rects]
    x0, x1 = min(cx) - RING_MARGIN, max(cx) + RING_MARGIN
    w = max(RING_MIN_W, x1 - x0)
    x0 = min(max((x0 + x1) / 2 - w / 2, MARGIN), MARGIN + AREA_W - w)
    if max(cy) - min(cy) > 0.5:                                   # nodes above and below the ring
        mid = (max(cy) + min(cy)) / 2
        upper_bottom = min(r[1] for r in rects if r[1] + r[3] / 2 > mid)
        lower_top = max(r[1] + r[3] for r in rects if r[1] + r[3] / 2 <= mid)
        gap = upper_bottom - lower_top
        h = min(0.9, max(0.35, gap - 2 * 0.25))
        if gap < 0.6:
            warnings.append("%s: the rows of nodes are only %.2f in apart; move them apart so the ring ellipse fits between them" % (where, gap))
        return x0, (upper_bottom + lower_top) / 2 - h / 2, w, h
    below = min(r[1] for r in rects) - RING_GAP - RING_H          # one row: ring below it, or above if there is no room
    if below < BOTTOM:
        below = max(r[1] + r[3] for r in rects) + RING_GAP
    return x0, below, w, RING_H


def draw_rings(page, rings, by_id, cables, shapes, warnings):
    """Behind-the-shapes part of each ring: the dashed ellipse with its label. Returns [(ring, ellipse)] for draw_ring_links."""
    out = []
    for r in rings:
        rects = [rect_of(by_id[v]) for v in r["nodes"]]
        ex, ey, ew, eh = ring_ellipse(rects, r["box"], warnings, r["where"])
        color, pattern = cables.line_style(r["cable"])
        label = r["label"]
        size = fit_size(label, ew * 0.7, eh * 0.6, (10, 9, 8, 7, 6.5, 6), True) if label else 8
        page.ellipse("ring", ex, ey, ew, eh, fill=RING_FILL, line=color, lw=1.5, pattern=2, text=label, size=size, bold=True,
                     key="ring:%s" % r["id"])
        out.append((r, (ex, ey, ew, eh)))
    return out


def draw_ring_links(page, placed, by_id, cables, shapes, warnings):
    """Straight links (in the ring cable's colour and dash, so green dashed for fibre) from each node to the ring ellipse, coming out of the ring the way the approved illustration shows it:
    nodes above the ring join its top, nodes below join its bottom. Returns the link count."""
    n = 0
    for r, (ex, ey, ew, eh) in placed:
        color, pattern = cables.line_style(r["cable"])        # the node links use the ring cable's own colour and dash (fibre: green dashed)
        ecx, ecy, a, b = ex + ew / 2, ey + eh / 2, ew / 2, eh / 2
        for v in r["nodes"]:
            nx, ny, nw, nh = rect_of(by_id[v])
            px = nx + nw / 2
            above = ny + nh / 2 > ecy
            dx = max(-0.98, min(0.98, (px - ecx) / a))
            if abs(px - ecx) >= a:
                warnings.append("%s: node %r lies beyond the end of the ring ellipse; widen the ring (x, w) or move the node" % (r["where"], v))
            ye = ecy + (1 if above else -1) * b * math.sqrt(1 - dx * dx)
            pts = [(px, ny if above else ny + nh), (px, ye)]
            page.line(pts, color, pattern, lw=1.25, key="ring:%s:%s" % (r["id"], v))
            n += 1
            for s in shapes:
                if s["kind"] not in SEE_THROUGH and s["id"] != v and crosses(pts, rect_of(s)):
                    warnings.append("%s: the link from %r to the ring passes through shape %r; move one of them" % (r["where"], v, s["id"]))
    return n


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
    pairs, boxes = [], [s for s in shapes if s["kind"] not in SEE_THROUGH]
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


def pill(page, x, y, w, h, text, solid, key):
    """A rounded label: solid blue with white text (a group's title) or light blue with dark-blue text (a bus label)."""
    size = fit_size(text, w - 0.2, h - 0.04, (10, 9, 8, 7, 6.5, 6), True)
    page.rect("icon", x, y, w, h, fill=PILL_BLUE if solid else PILL_LIGHT_FILL, line=None if solid else PILL_LIGHT_LINE, lw=0.75,
              rounding=h / 2, text=text, size=size, bold=True, color="#FFFFFF" if solid else PILL_LIGHT_TEXT, key=key)


def draw_shape(page, s):
    x, y, w, h = rect_of(s)
    warn = None
    if s["kind"] == "zone":
        page.rect("zone", x, y, w, h, fill=s["fill"] or ZONE_FILL, line=ZONE_LINE, lw=1.0, pattern=2 if s["dashed"] else 1, key=s["key"])
        if s["label"]:
            size, warn = label_size(s, w - 0.1, 0.25, (9, 8, 7, 6.5, 6), True)
            page.text(x + 0.05, y + h - 0.28, w - 0.1, 0.25, s["label"], size=size, bold=True, halign=0, valign=0)
    elif s["kind"] == "group":                                      # dashed rounded container with a blue title pill on its top edge
        page.rect("zone", x, y, w, h, fill=s["fill"] or GROUP_FILL, line=GROUP_LINE, lw=1.0, pattern=2, rounding=0.12, key=s["key"])
        # no title pill: the dashed container stands on its own
    elif s["kind"] == "pill":
        pass                                                        # label pills are not drawn any more (kind kept so older files still build)
    elif s["kind"] == "text":
        size, warn = label_size(s, w, h, BOX_SIZES, s["bold"])
        page.text(x, y, w, h, s["label"], size=size, bold=s["bold"], key=s["key"])
    else:                                                           # a device: its picture with the caption underneath, never a box
        try:
            fit_size(s["label"], w, LABEL_ZONE, LABEL_SIZES, True)
        except TextFitError:
            warn = "%s: label may not fit under its picture; shorten it or widen the shape (w)" % s["where"]
        draw_picture(page, s["pic"], s["label"], x, y, w, h, s["key"], soft=True, sub=s.get("sub"), bold=True)
    return warn


PAGE_INSET = 0.10                                        # nothing may come closer than this to the sheet edge


def keep_on_page(page, first_content, warnings):
    """Last safety net: every shape and line after the footer (page.shapes[first_content:]) is moved inside the A3 sheet and kept clear of the
    footer; a shape bigger than that region is shrunk. Without it, Visio may enlarge the page to fit a stray element. Returns how many moved."""
    x0, x1 = PAGE_INSET, A3_W - PAGE_INSET
    y0, y1 = footer.TOP + 0.02, A3_H - PAGE_INSET
    moved = 0
    for s in page.shapes[first_content:]:
        name = s["key"] or s["text"] or s["kind"]
        if s["pts"]:                                         # lines and polygons: pull each point inside
            new = [(min(max(px, x0), x1), min(max(py, y0), y1)) for px, py in s["pts"]]
            if any(abs(a - b) > 1e-6 or abs(c - d) > 1e-6 for (a, c), (b, d) in zip(new, s["pts"])):
                xs, ys = [p[0] for p in new], [p[1] for p in new]
                s["pts"], s["x"], s["y"], s["w"], s["h"] = new, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
                moved += 1
                warnings.append("%s: was outside the page; moved inside" % name)
            continue
        w, h = min(s["w"], x1 - x0), min(s["h"], y1 - y0)
        nx, ny = min(max(s["x"], x0), x1 - w), min(max(s["y"], y0), y1 - h)
        if (abs(nx - s["x"]) > 1e-6 or abs(ny - s["y"]) > 1e-6 or abs(w - s["w"]) > 1e-6 or abs(h - s["h"]) > 1e-6):
            s["x"], s["y"], s["w"], s["h"] = nx, ny, w, h
            moved += 1
            warnings.append("%s: was outside the page; moved inside" % name)
    return moved


def build(spec, base, out, comps=None, cables=None, spec_dir="."):
    comps, cables = comps or Components(), cables or Cables()
    shapes, lines, warnings = prepare(spec, comps, cables, spec_dir)
    panels = apply_layers(spec, shapes, warnings)
    by_id = {s["id"]: s for s in shapes}
    page = Page()
    notes = [str(n) for n in spec.get("notes", [])]
    n_web = sum(1 for s in shapes if s["web"])
    if n_web:
        notes.append("%d picture(s) come from outside the component library; the source is in the shape data." % n_web)
    given = dict(spec.get("project", {}))
    if "contractor" in given and "client" not in given:        # older files: Contractor is now Client
        given["client"] = given["contractor"]
    missing = [k for k in footer.REQUIRED if not str(given.get(k, "")).strip()]
    if missing:
        warnings.append("footer values printing TBC: %s; if the engineer or the documents gave any of them, add them to \"project\"" % ", ".join(missing))
    rings = prepare_rings(spec, shapes, cables)
    used = sorted({c["cable"] for c in lines} | {r["cable"] for r in rings})
    try:
        footer.build_footer(page, spec.get("project", {}), cables.legend(used), notes, allow_tbc=True)
    except footer.FooterError as e:
        raise BuildError("footer: %s" % e)
    n_footer = len(page.shapes)

    for p in panels:                                                      # layer panels at the very back
        draw_layer(page, p)
    for s in (s for s in shapes if s["kind"] in BEHIND):                  # zones and groups behind, then lines, then everything else on top
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    placed = draw_rings(page, rings, by_id, cables, shapes, warnings)      # ring ellipses sit behind the lines and shapes
    n_lines = 0
    obstacles = [rect_of(s) for s in shapes if s["kind"] not in SEE_THROUGH]
    x0 = MARGIN + (BAND_W + 0.05 if panels else 0.0)
    reqs = [dict(a=rect_of(by_id[c["a"]]), b=rect_of(by_id[c["b"]]), a_id=c["a"], b_id=c["b"], via=c["via"], straight=c["straight"],
                 from_side=c.get("from_side"), to_side=c.get("to_side")) for c in lines]
    try:
        routed = router.route_all(reqs, obstacles, (x0, BOTTOM, MARGIN + AREA_W, TOP))
    except Exception as e:                                                  # never lose the drawing over the router
        warnings.append("automatic cable routing failed (%s); plain routes used" % e)
        routed = [None] * len(lines)
    paths = []
    for c, q, pts in zip(lines, reqs, routed):
        if pts is None:
            pts = route(q["a"], q["b"], c["via"])
            if not c["via"]:
                warnings.append("%s (%s to %s): no clear square route found; a plain one was drawn" % (c["where"], c["a"], c["b"]))
        paths.append(pts)
    for c, pts in zip(lines, router.add_hops(paths)):
        color, pattern = cables.line_style(c["cable"])
        page.line(pts, color, pattern, lw=CABLE_LW, key="%s->%s" % (c["a"], c["b"]))
        n_lines += 1
    for c, pts in zip(lines, paths):
        if c["via"]:                                                        # a hand-routed cable may run through a device: say so
            for s in shapes:
                if s["kind"] not in SEE_THROUGH and s["id"] not in (c["a"], c["b"]) and crosses(pts, rect_of(s)):
                    warnings.append("%s (%s to %s) passes through shape %r; add a \"via\" point to route round it" % (c["where"], c["a"], c["b"], s["id"]))
    n_lines += draw_ring_links(page, placed, by_id, cables, shapes, warnings)
    for s in (s for s in shapes if s["kind"] not in BEHIND):
        w = draw_shape(page, s)
        if w:
            warnings.append(w)
    warnings += ["shapes %r and %r overlap" % p for p in overlapping(shapes)]
    keep_on_page(page, n_footer, warnings)
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
