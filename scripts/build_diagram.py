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
import qa
import components as components_mod
import pictures
import router
import reference_layout
import cable_labels
from cables import CableError, Cables
from components import Components
from draw import BOX_FILL, BOX_LINE, BOX_SIZES, LABEL_SIZES, LABEL_ZONE, draw_picture, visible_box
from textfit import TextFitError, fit_size
from vsdx_writer import A3_H, A3_W, FONT_FLOOR, Page, png_size, write_vsdx

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MARGIN = footer.X0
TITLE_H, FRAME = 0.50, 0.12                          # title strip height; inset of the blue frame round the whole sheet
TOP, BOTTOM = A3_H - MARGIN - TITLE_H, footer.TOP + 0.12      # the drawing area runs between these page heights
AREA_W, AREA_H = A3_W - 2 * MARGIN, TOP - BOTTOM
DEFAULT_SIZE = {"box": (1.35, 1.25), "picture": (1.35, 1.25), "text": (1.50, 0.30)}   # every device is a picture with its caption underneath
SMALL_EQUIPMENT = 0.50                                  # a displayed device narrower and shorter than this is reported as too small
MIN_DEVICE_H = 0.60                                     # a device cell shorter than this cannot hold a picture and a caption
GENERIC_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "icons", "generic_device.png")
BEHIND = ("zone", "group")                              # drawn first, behind the lines and shapes
SEE_THROUGH = ("zone", "group", "pill", "bus")                 # lines may run over these; they are not obstacles
GROUP_FILL, GROUP_LINE, PILL_BLUE = "#FFFFFF", reference_layout.NAVY, "#1456C0"
PILL_LIGHT_FILL, PILL_LIGHT_LINE, PILL_LIGHT_TEXT = "#D9E9FB", "#2F6FD0", "#0B3C8C"
CABLE_LW = 1.75                                         # bold reference-style cables, in points
BLUE = reference_layout.NAVY
ZONE_FILL, ZONE_LINE = "#F7F9FC", "#9AA5B1"
HEX = re.compile(r"#[0-9A-Fa-f]{6}$")
LAYERS_PATH = os.path.join(ROOT, "data", "layers.json")


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
class Warnings(list):
    """Warnings, plus `notices`: information the operator must pass on (picture fallbacks, missing provenance) that is not a drawing defect."""
    def __init__(self):
        super().__init__()
        self.notices = []


INSTRUMENT_WORDS = re.compile(r"transmitter|sensor|meter|gauge|switch(?!es\b)|valve|detector|analy[sz]er|probe|thermo|\b(?:pt|tt|ft|lt|"
                              r"pit|tit|fit|lit|dpt|mov|xv)\b", re.I)


def is_instrument(s):
    """A field instrument: by declared category, by component layer, or (field layer) by its caption."""
    if s.get("category"):
        return s["category"] == "instrument"
    return s.get("layer") == "field" or bool(INSTRUMENT_WORDS.search(str(s.get("label") or ""))) and "ethernet" not in str(s.get("label")).lower()


def fixed_for_override(s):
    return bool(s.get("image_override"))


def expand_chains(spec):
    """A line entry {"chain": ["plc", "rio-1", "rio-2"], "cable": "ethernet"} is a daisy chain: it becomes one
    line per consecutive pair (plc -> rio-1, rio-1 -> rio-2). Other keys (cable, label, ...) are copied to each
    pair. Only an explicit chain is expanded: neighbouring pictures are never connected just because they are adjacent."""
    out = []
    for n, c in enumerate(spec.get("lines", []), 1):
        if isinstance(c, dict) and "chain" in c:
            ids = c["chain"]
            if not isinstance(ids, list) or len(ids) < 2 or not all(isinstance(i, str) for i in ids) or "from" in c or "to" in c:
                raise BuildError('line %d: "chain" must be a list of two or more shape ids (and replaces "from"/"to")' % n)
            rest = {k: v for k, v in c.items() if k != "chain"}
            out += [dict(rest, **{"from": a, "to": b}) for a, b in zip(ids, ids[1:])]
        else:
            out.append(c)
    spec["lines"] = out


BUS_STEP = .14          # vertical spacing between the trunks of two buses below one row (dual-homed equipment)
BUS_FIRST = .16         # first trunk below the bottom of its members
BUS_DROP = .16          # horizontal offset between the drops of two buses from one device


def parse_buses(spec, shapes, cables, errors):
    """Item 4: common graphical network buses. "buses": [{"id", "members": [device ids in one row], "cable", "label"}]. The engine
    reserves a corridor below the members, draws a trunk with a drop to every member, and lets cables end on the bus id."""
    out = []
    raw = spec.get("buses", [])
    if not isinstance(raw, list):
        errors.append('"buses" must be a list')
        return out
    by_id = {s["id"]: s for s in shapes}
    for n, b in enumerate(raw, 1):
        where = "bus %d" % n
        if not isinstance(b, dict) or not isinstance(b.get("id"), str) or not b["id"].strip():
            errors.append("%s needs a text id" % where)
            continue
        if b["id"] in by_id:
            errors.append("%s: id %r is already a shape id" % (where, b["id"]))
            continue
        members = [str(m) for m in b.get("members", [])]
        bad = [m for m in members if m not in by_id or by_id[m]["kind"] != "box"]
        if len(members) < 2 or bad:
            errors.append("%s: members must be two or more device ids%s" % (where, (" (not devices: %s)" % ", ".join(bad)) if bad else ""))
            continue
        try:
            cables.line_style(b.get("cable"))
        except Exception:
            errors.append("%s: unknown cable %r" % (where, b.get("cable")))
            continue
        out.append({"id": b["id"], "kind": "bus", "members": members, "cable": b["cable"], "label": str(b.get("label", "")).strip(),
                    "key": "bus:" + b["id"], "x": 0., "y": 0., "w": .1, "h": .02, "where": where, "web": False, "pic": None})
    spec["_buses"] = out
    return out


def place_buses(buses, shapes, by_id, spec_lines=()):
    """After layout: trunk geometry for every bus (below its members; several buses sharing members stack downwards)."""
    order = {}
    for b in buses:
        for m in b["members"]:
            order.setdefault(m, []).append(b["id"])
    for b in buses:
        rects = [rect_of(by_id[m]) for m in b["members"]]
        k = max(order[m].index(b["id"]) for m in b["members"])
        bottom = min(r[1] for r in rects)                              # page coordinates (y up)
        y = bottom - BUS_FIRST - k * BUS_STEP
        drops = []
        for m, r in zip(b["members"], rects):
            mine = order[m]
            dx = (mine.index(b["id"]) - (len(mine) - 1) / 2) * BUS_DROP
            pr = picture_rect(by_id[m])
            drops.append((pr[0] + pr[2] / 2 + dx, r[1]))
        xs = [x for x, _ in drops]
        for c in spec_lines:                                          # the trunk reaches every device that connects to the bus,
            for hub_end, bus_end in (("from", "to"), ("to", "from")):  # so its uplink is a straight vertical drop
                if str(c.get(bus_end)) == b["id"] and str(c.get(hub_end)) in by_id:
                    hr = rect_of(by_id[str(c[hub_end])])
                    xs.append(hr[0] + hr[2] / 2)
        # the shape record keeps layout coordinates like every other shape (rect_of converts them back to the page)
        b.update(x=min(xs) - MARGIN, y=TOP - (y + .01), w=max(.1, max(xs) - min(xs)), h=.02, trunk_y=y, drops=drops,
                 layer=by_id[b["members"][0]].get("layer") or layer_of(by_id, b["members"][0]))
        b["parent"] = None
    return buses


def draw_buses(page, buses, cables):
    """Trunks with hops where another bus's drop crosses them, and the drops; returns the polylines (for the drawing checks)."""
    drawn = []
    for b in buses:
        color, pattern = cables.line_style(b["cable"])
        crossings = sorted(x for o in buses if o is not b for x, y0 in o["drops"]
                           if o["trunk_y"] < b["trunk_y"] < y0 and b["x"] + MARGIN + .05 < x < b["x"] + MARGIN + b["w"] - .05)
        x0 = b["x"] + MARGIN
        pts = [(x0, b["trunk_y"])]
        for x in crossings:                                           # the trunk hops over a drop of the other bus
            pts += [(x - .05, b["trunk_y"]), (x - .03, b["trunk_y"] + .04), (x + .03, b["trunk_y"] + .04), (x + .05, b["trunk_y"])]
        pts.append((x0 + b["w"], b["trunk_y"]))
        page.line(pts, color, pattern, lw=CABLE_LW, key="bus:%s" % b["id"])
        drawn.append(pts)
        for x, y0 in b["drops"]:
            page.line([(x, y0), (x, b["trunk_y"])], color, pattern, lw=CABLE_LW, key="bus:%s|drop" % b["id"])
            drawn.append([(x, y0), (x, b["trunk_y"])])
        if b["label"]:
            w = len(b["label"]) * .058 + .06
            page.text(b["x"] + MARGIN - w - .06, b["trunk_y"] - .07, w, .14, b["label"], size=6.5, bold=True, halign=2, key="bus-label:%s" % b["id"])
    return drawn


def prepare(spec, comps, cables, spec_dir):
    """Shapes and lines with every default filled in. Returns (shapes, lines, warnings); raises BuildError for what cannot be drawn."""
    if not isinstance(spec, dict) or not isinstance(spec.get("shapes"), list) or not spec["shapes"]:
        raise BuildError('the file must be a JSON object with a non-empty "shapes" list')
    expand_chains(spec)
    errors, warnings, shapes, ids = [], Warnings(), [], set()
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
        fixed_picture = False
        sub = str(s.get("sublabel", "")).strip() or None
        if sub is None and "\n" in label:                              # "SCADA Server\n(Primary)": first line is the name, the rest the blue line
            label, _, rest = label.partition("\n")
            label, sub = label.strip(), (rest.replace("\n", " ").strip() or None)
        component = s.get('component')
        if kind == 'box' and not component and not s.get('image_override'):
            component = comps.fixed_for(label)
        if s.get('image_override') and not s.get('image'):
            errors.append('%s: image_override requires an image explicitly requested by the user' % where)
            continue
        provenance = None
        use_library = bool(component) and not s.get('image_override')
        if use_library:
            try:
                comp = comps.get(component)
            except KeyError:
                errors.append("%s: component %r is not in the library" % (where, component))
                continue
            if comp.get('fixed') and s.get('image'):
                errors.append('%s: fixed library image cannot be replaced without image_override: true and an explicit user request' % where)
                continue
            if s.get('image') and not comp.get('fixed'):
                label = label or comp["label"]                          # a web-sourced picture for a non-fixed category; the component only supplies the caption
                use_library = False
        if use_library:
            try:
                label, pic, key = label or comp["label"], comps.picture_path(component), "component:%s" % comp["id"]
            except (ValueError, OSError) as e:
                errors.append('%s: %s' % (where, e))
                continue
            fixed_picture = bool(comp.get('fixed'))
            if not fixed_picture and spec.get("image_policy", "web_first") == "web_first":
                warnings.notices.append("%s: library picture %r used as the offline fallback; search the web for the actual equipment image first "
                                "(OEM/model if given), and report this fallback if none can be used" % (where, comp["id"]))
        elif s.get("image") and kind == "box":
            path = str(s["image"])
            path = path if os.path.isabs(path) else os.path.join(spec_dir, path)
            try:
                path = as_png(path)
                png_size(path)
                pic, web = path, True
                key = "image:%s|%s" % (s.get("image_source", "unknown"), sid)
                provenance = {k: str(s[k]).strip() for k in ("image_source", "oem", "model") if str(s.get(k, "")).strip()}
                if not fixed_for_override(s) and "image_source" not in provenance:
                    warnings.notices.append("%s: picture has no image_source (the URL it came from); provenance is required for web pictures" % where)
                if not ({"oem", "model"} <= provenance.keys()) and not s.get("image_override"):
                    warnings.notices.append("%s: give oem and model for this picture, or say it is a representative illustration (generic equipment)" % where)
                if provenance.get("oem") or provenance.get("model"):
                    key += "|%s %s" % (provenance.get("oem", ""), provenance.get("model", ""))
            except (OSError, ValueError) as e:
                warnings.append("%s: picture not usable (%s); drawn as a box" % (where, e))
        if pic and kind == "box" and not fixed_picture:                  # fixed cutouts are embedded byte-for-byte
            background = s.get("background", "auto")
            if background not in ("auto", "keep"):
                errors.append('%s: background must be "auto" or "keep"' % where)
                continue
            pic, note = pictures.prepare(pic, background=background)
            if note:
                warnings.append("%s: %s" % (where, note))
        elif not pic and kind == "box" and is_instrument(s):            # C10: an instrument is never shown as unrelated equipment
            tag = str(s.get("tag") or components_mod.instrument_tag(label or s.get("label")))
            pic = comps.balloons.get(tag) or comps.balloons.get("I")
            key = "balloon:" + tag
            warnings.notices.append("%s: no instrument picture; drawn as its ISA-5.1 balloon %r. Source the actual instrument picture "
                                    "(web first) or give a library component" % (where, tag))
        elif not pic and kind == "box":                                 # no picture given: a generic device icon, never a plain box
            pic, key = GENERIC_ICON, "generic:" + sid
            warnings.append("%s: no picture (give \"component\" or \"image\"); a generic device icon is used" % where)
        x, y = _num(s.get("x")), _num(s.get("y"))
        layer = s.get("layer")
        parent = s.get("parent")
        reference = spec.get("layout_style", "reference") == "reference"
        auto_x = layer is not None and x is None
        if layer is not None:
            if kind in BEHIND and not (reference and kind == "group"):
                errors.append("%s: a %s cannot be placed in a layer" % (where, kind))
                continue
            x, y = (0.0 if x is None else x), 0.0                  # y is set by the layer (centred); x too unless given
        if parent and reference:
            x, y = 0.0, 0.0
        if x is None or y is None:
            errors.append("%s: x and y (inches from the top-left of the drawing area) are required" % where)
            continue
        needs_size = kind in ("zone", "group") and not (reference and kind == "group" and (layer or parent))
        if kind == "pill":
            dw, dh = min(4.0, 0.085 * len(label) + 0.6), 0.26
        else:
            dw, dh = DEFAULT_SIZE["picture" if pic and kind == "box" else "box" if kind == "group" else kind if not needs_size else "box"]
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
                           layer=layer, auto_x=auto_x, line=line, sub=sub, scope=scope if scope in footer.SCOPE else None,
                           parent=str(parent) if parent else None, row=s.get("row"), columns=s.get("columns"),
                           placement=s.get("placement"), width_weight=s.get("width_weight"), solid=bool(s.get("solid")),
                           max_width=s.get("max_width"), max_height=s.get("max_height"), frame=_frame(s, kind, scope, where, warnings),
                           place=_place(s, where, errors), category=s.get("category"), tag=s.get("tag")))
    buses = parse_buses(spec, shapes, cables, errors)
    ids |= {b["id"] for b in buses}
    lines = []
    for n, c in enumerate(spec.get("lines", []), 1):
        where = "line %d" % n
        if not isinstance(c, dict):
            errors.append("%s: not an object" % where)
            continue
        for end in ("from", "to"):
            if str(c.get(end)) not in ids:
                errors.append("%s: %s %r is not a shape id" % (where, end, c.get(end)))
            elif any(x["id"] == str(c.get(end)) and not framed(x) for x in shapes):
                errors.append("%s: %s %r is an invisible arrangement (frame: false); a cable must end on visible equipment or a box" % (where, end, c.get(end)))
        try:
            cables.get(c.get("cable"))
        except CableError as e:
            errors.append("%s: %s" % (where, e))
        via = []
        if c.get("waypoints") is not None and c.get("via") is not None:
            errors.append('%s: give "waypoints" or "via", not both' % where)
        points = c.get("waypoints", c.get("via", []))     # item 6: locked waypoints (followed exactly, corners squared)
        for p in points:
            if isinstance(p, list) and len(p) == 2 and None not in map(_num, p):
                px, py = MARGIN + _num(p[0]), TOP - _num(p[1])
                cx, cy = min(max(px, MARGIN), MARGIN + AREA_W), min(max(py, BOTTOM), TOP)
                if abs(cx - px) > 0.005 or abs(cy - py) > 0.005:
                    warnings.append("%s: via point [%s, %s] is outside the drawing area; moved inside" % (where, p[0], p[1]))
                via.append((cx, cy))
        if len(via) != len(points):
            warnings.append("%s: some via/waypoint points were not [x, y] numbers; ignored" % where)
        sides = {}
        for key in ("from_side", "to_side"):
            v = c.get(key)
            if v is not None and v not in router.SIDES:
                warnings.append('%s: %s must be "left", "right", "top" or "bottom"; ignored' % (where, key))
            elif v is not None:
                sides[key] = v
        arrows = c.get("arrows")
        if arrows not in (None, "none", "end", "both"):
            warnings.append('%s: arrows must be "none", "end" (at the destination) or "both"; ignored' % where)
            arrows = None
        lines.append(dict(a=str(c.get("from")), b=str(c.get("to")), cable=c.get("cable"), via=via, where=where, label=str(c.get('label', '')).strip(),
                          straight=bool(c.get("straight")), individual=bool(c.get("individual")), direct=bool(c.get("direct")), arrows=arrows, **sides))
    if errors:
        raise BuildError("\n  ".join(["cannot draw this file:"] + errors))
    return shapes, lines, warnings


# ---- layers (Purdue bands) ------------------------------------------------------------------------------------------------------
LAYER_GAP, BAND_W, LAYER_PAD, LAYER_R = 0.0, 1.90, 0.15, 0.0      # BAND_W is the width of the label column on the left of each layer
PANEL_FILL, PANEL_LINE = "#FFFFFF", BLUE                     # white rows separated by thin blue lines (the approved reference style)


def load_layers(path=LAYERS_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["layers"]


def level_number(level):
    """'Level 3.5' -> 3.5; a plain number is returned as a float; anything unreadable -> None."""
    if isinstance(level, (int, float)) and not isinstance(level, bool):
        return float(level)
    m = re.search(r"-?\d+(?:\.\d+)?", str(level or ""))
    return float(m.group()) if m else None


def layer_table(spec):
    """The standard layers plus the file's optional "custom_layers", highest level first (top of the page). A custom layer is
    {"id", "level", "name", "desc"}; its level is a number or "Level n" (for example 2.5) and places it between the standard ones."""
    table = [dict(t) for t in load_layers()]
    custom = spec.get("custom_layers", [])
    if not isinstance(custom, list):
        raise BuildError("custom_layers must be a list")
    known = {t["id"] for t in table}
    for c in custom:
        if not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"].strip():
            raise BuildError("each custom_layers entry needs a text id")
        if c["id"] in known:
            raise BuildError("custom layer id %r is already used" % c["id"])
        if level_number(c.get("level")) is None:
            raise BuildError("custom layer %r needs a level such as 2.5 or \"Level 2.5\"" % c["id"])
        known.add(c["id"])
        lv = c["level"] if isinstance(c["level"], str) else "Level %g" % float(c["level"])
        name = str(c.get("name") or c["id"])
        table.append(dict(id=c["id"], label=name, level=lv, name=name, desc=str(c.get("desc", c.get("description", ""))), custom=True))
    return sorted(table, key=lambda t: -(level_number(t.get("level")) or 0.0))     # stable: equal levels keep their listed order


def apply_layers(spec, shapes, warnings, boost=None):
    """Stack the requested layers in the standard order so together they fill the whole drawing area, and place the shapes tagged with
    a layer: spread evenly across the layer's width and centred in its height. Returns the panels [{id, label, x, y, w, h}]
    (inches from the top-left of the drawing area). No "layers" in the file: nothing happens and shapes stay where they were put."""
    style = spec.get("layout_style", "reference")
    if style not in ("reference", "legacy"):
        raise BuildError('layout_style must be "reference" or "legacy"')
    if style == "reference":
        try:
            return reference_layout.apply_layers(spec, shapes, warnings, sys.modules[__name__], boost=boost)
        except reference_layout.PlacementError as e:
            raise BuildError(str(e))
    wanted = spec.get("layers")
    tagged = [s for s in shapes if s["layer"] is not None]
    if wanted is None:
        if tagged:
            raise BuildError('shapes use "layer" but the file has no "layers" list, e.g. "layers": ["scada", "control", "field"]')
        return []
    table = layer_table(spec)
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
        panels.append(dict(id=t["id"], label=t["label"], level=t.get("level", ""), name=t.get("name", t["label"]), desc=t.get("desc", ""),
                           x=0.0, y=y, w=AREA_W, h=h))
        members = [s for s in tagged if s["layer"] == t["id"]]
        if not members:
            continue
        left, width = BAND_W + LAYER_PAD, AREA_W - BAND_W - 2 * LAYER_PAD
        k = min(1.0, (h - 0.30) / max(s["h"] for s in members))      # a shape taller than its layer is scaled down to fit
        groups = [[s for sc in ("avanceon", "other", None) for s in members if s["scope"] == sc]]   # one row, Avanceon first
        auto = any(s["auto_x"] for s in members)
        if auto:
            k = min(k, (width - (len(members) + 1) * 0.15) / sum(s["w"] for s in members))
        if k < 1.0:
            if k < 0.5:
                warnings.append("layer %r is very crowded (%d shapes); shapes were reduced to %.0f%% and may be hard to read" % (t["id"], len(members), 100 * max(k, 0.5)))
                k = max(k, 0.5)
            for s in members:
                s["w"], s["h"] = s["w"] * k, s["h"] * k
        for s in members:
            s["y"] = y + (h - s["h"]) / 2
        if auto:
            g = groups[0]
            gap = (width - sum(s["w"] for s in g)) / (len(g) + 1)
            cx = left + gap
            for s in g:
                s["x"] = cx
                cx += s["w"] + gap
    return panels


def draw_layer(page, p):
    """One layer: a white row between thin blue lines, with the label column on the left: LEVEL n and the name in big blue bold, the
    description under it in small black."""
    if p.get("reference"):
        return reference_layout.draw_layer(page, p, sys.modules[__name__])
    x, y, w, h = MARGIN + p["x"], TOP - p["y"] - p["h"], p["w"], p["h"]
    page.rect("zone", x, y, w, h, fill=PANEL_FILL, line=PANEL_LINE, lw=1.5, key="layer:" + p["id"])
    page.line([(x + BAND_W, y), (x + BAND_W, y + h)], BLUE, lw=1.5, key="layer-divider:" + p["id"])
    head = "%s\n%s" % (p["level"].upper(), p["name"].upper())
    size = fit_size(max(head.split("\n"), key=len), BAND_W - 0.3, 0.3, (16, 14, 13, 12, 11, 10, 9), True)
    cy = y + h / 2
    page.text(x + 0.12, cy + 0.02, BAND_W - 0.2, 0.62, head, size=size, bold=True, color=BLUE, halign=0, valign=2, key="layer-name:" + p["id"])
    if p["desc"]:
        page.text(x + 0.12, cy - 0.62, BAND_W - 0.2, 0.58, p["desc"], size=8, halign=0, valign=0, key="layer-desc:" + p["id"])
    return size


def draw_frame_and_title(page, title):
    """Blue frame round the whole sheet, and the bold blue title in the strip above the layers."""
    page.rect("zone", FRAME, FRAME, A3_W - 2 * FRAME, A3_H - 2 * FRAME, fill=None, line=BLUE, lw=2.25, key="frame")
    top = A3_H - FRAME
    size = fit_size(title, AREA_W - 0.4, top - TOP - 0.1, (24, 22, 20, 18, 16, 14, 12, 10), True)
    page.text(MARGIN, TOP + 0.02, AREA_W, top - TOP - 0.06, title, size=size, bold=True, color=BLUE, key="title")


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
        page.ellipse("ring", ex, ey, ew, eh, fill=RING_FILL, line=color, lw=CABLE_LW, pattern=2, text=label, size=size, bold=True,
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
            page.line(pts, color, pattern, lw=CABLE_LW, key="ring:%s:%s" % (r["id"], v))
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


def _frame(s, kind, scope, where, warnings):
    """A group is a visible box unless "frame": false makes it an invisible arrangement (7.4: no box around equipment
    that needs none). Client/existing scope must stay visible, so such a group keeps its frame."""
    f = s.get("frame", True)
    if not isinstance(f, bool):
        warnings.append("%s: frame must be true or false; a frame is drawn" % where)
        return True
    if not f and kind != "group":
        return True
    if not f and scope == "other":
        warnings.append("%s: a client/existing-scope group keeps its frame so the scope colour stays visible" % where)
        return True
    return f


def _square(pts, jog=0.02):
    """8.2: remove sub-millimetre slants left by routing so every segment is exactly horizontal or vertical."""
    pts = [tuple(p) for p in pts]
    for i in range(1, len(pts)):
        (x0, y0), (x1, y1) = pts[i - 1], pts[i]
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if 0 < dy < jog and dx > dy:
            if i < len(pts) - 1:
                pts[i] = (x1, y0)
            else:
                pts[i - 1] = (x0, y1)
        elif 0 < dx < jog and dy > dx:
            if i < len(pts) - 1:
                pts[i] = (x0, y1)
            else:
                pts[i - 1] = (x1, y0)
    return pts


def separate(lines, paths, rect_of_id, obstacles, gap=0.08, run=0.2):
    """8.3 / 8.6: where two different cables share (almost) the same track, move one of them onto its own parallel track `gap`
    away, keeping every segment orthogonal, its ends on their equipment and clear of other equipment. The hardwired bus into an
    I/O box is shared deliberately and left alone. Returns the adjusted paths."""
    paths = [list(map(tuple, p)) for p in paths]

    def segs():
        out = []
        for n, pts in enumerate(paths):
            for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
                if abs(y0 - y1) < 1e-6 and abs(x1 - x0) > run:
                    out.append((n, i, "h", y0, min(x0, x1), max(x0, x1)))
                elif abs(x0 - x1) < 1e-6 and abs(y1 - y0) > run:
                    out.append((n, i, "v", x0, min(y0, y1), max(y0, y1)))
        return out

    def clash(n, i, axis, pos, lo, hi):
        for a in segs():
            if a[0] != n and a[2] == axis and abs(a[3] - pos) < gap - .004 and min(a[5], hi) - max(a[4], lo) > .02:
                return True
        return False

    def orthogonal(pts):
        return all(abs(x0 - x1) < 1e-6 or abs(y0 - y1) < 1e-6 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))

    def endpoint_ok(n, pts):
        a, b = rect_of_id(lines[n]["a"]), rect_of_id(lines[n]["b"])
        def on(pt, r):
            x, y, w, h = r
            return x - .03 <= pt[0] <= x + w + .03 and y - .03 <= pt[1] <= y + h + .03
        return (on(pts[0], a) and on(pts[-1], b)) or (on(pts[0], b) and on(pts[-1], a))

    for _ in range(30):
        moved = False
        ss = segs()
        for k, a in enumerate(ss):
            for b in ss[k + 1:]:
                if a[0] == b[0] or a[2] != b[2] or abs(a[3] - b[3]) >= gap - .004:
                    continue
                if min(a[5], b[5]) - max(a[4], b[4]) <= run:
                    continue
                if lines[a[0]].get("cable") == lines[b[0]].get("cable") == "hardwired":
                    continue
                n, i, axis, pos = b[0], b[1], b[2], b[3]
                for delta in (gap, -gap, 2 * gap, -2 * gap, 3 * gap, -3 * gap):
                    pts = list(paths[n])
                    p0, p1 = pts[i], pts[i + 1]
                    if axis == "h":
                        pts[i], pts[i + 1] = (p0[0], p0[1] + delta), (p1[0], p1[1] + delta)
                    else:
                        pts[i], pts[i + 1] = (p0[0] + delta, p0[1]), (p1[0] + delta, p1[1])
                    # keep the neighbours orthogonal: a first/last segment slides its end along the equipment edge
                    if not orthogonal(pts) or not endpoint_ok(n, pts):
                        continue
                    own = (rect_of_id(lines[n]["a"]), rect_of_id(lines[n]["b"]))
                    if any(crosses(pts, r) for r in obstacles if r not in own):
                        continue
                    if clash(n, i, axis, pos + delta, min(p0[1 if axis == "v" else 0], p1[1 if axis == "v" else 0]),
                             max(p0[1 if axis == "v" else 0], p1[1 if axis == "v" else 0])):
                        continue
                    paths[n] = pts
                    moved = True
                    break
                if moved:
                    break
            if moved:
                break
        if not moved:
            break
    # Cables ending on the same point of a device read as a junction: slide one end along the device edge.
    for _ in range(30):
        moved = False
        ends = [(n, j) for n, p in enumerate(paths) if len(p) >= 2 for j in (0, len(p) - 1)]
        for k, (n, j) in enumerate(ends):
            for m, jj in ends[k + 1:]:
                p, q = paths[n][j], paths[m][jj]
                if n == m or abs(p[0] - q[0]) >= .05 or abs(p[1] - q[1]) >= .05:
                    continue
                if lines[n].get("cable") == lines[m].get("cable") == "hardwired":
                    continue
                pts = list(paths[m])
                i = 0 if jj == 0 else len(pts) - 2                     # the end segment
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                horizontal = abs(y0 - y1) < 1e-6
                for delta in (gap, -gap, 2 * gap, -2 * gap, 3 * gap, -3 * gap):
                    trial = list(pts)
                    if horizontal:
                        trial[i], trial[i + 1] = (x0, y0 + delta), (x1, y1 + delta)
                    else:
                        trial[i], trial[i + 1] = (x0 + delta, y0), (x1 + delta, y1)
                    if not orthogonal(trial) or not endpoint_ok(m, trial):  # (a straight cable slides both ends and stays straight)
                        continue
                    own = (rect_of_id(lines[m]["a"]), rect_of_id(lines[m]["b"]))
                    if any(crosses(trial, r) for r in obstacles if r not in own):
                        continue
                    others = [e for o, pp in enumerate(paths) if o != m for e in (pp[0], pp[-1])]
                    if any(abs(e[0] - t[0]) < .05 and abs(e[1] - t[1]) < .05 for e in others for t in (trial[0], trial[-1])):
                        continue
                    paths[m] = trial
                    moved = True
                    break
                if moved:
                    break
            if moved:
                break
        if not moved:
            break
    return paths


def picture_rect(d):
    """Page rectangle of the visible equipment picture inside a device (the caption sits below it)."""
    import draw
    x, y, w, h = rect_of(d)
    if d["kind"] != "box" or not d.get("pic"):
        return x, y, w, h
    area_h = h - draw.LABEL_ZONE - (draw.SUB_ZONE if d.get("sub") else 0)
    if area_h <= 0:
        return x, y, w, h
    try:
        vw, vh = draw.visible_size(d["pic"], w, area_h, reference_layout.FILL)
    except Exception:
        return x, y, w, h
    top = y + h
    return x + (w - vw) / 2, top - area_h / 2 - vh / 2, vw, vh


def snap_ends(lines, paths, by_id, margin=.06):
    """Item 6 attachment points: a cable that ends on a device's top or bottom edge does so within the width of its visible picture
    (not over empty caption space), and one on a side edge does so beside the picture. The end segment slides along the edge (a
    straight cable gets a small jog half way so its other end stays put); the path stays orthogonal."""
    def snap_first(c, pts):
        """Snap pts[0] (the path's first end); returns the new path."""
        if len(pts) < 2:
            return pts
        end, nxt = pts[0], pts[1]
        dev = next((by_id[e] for e in (c["a"], c["b"]) if by_id.get(e) is not None and by_id[e]["kind"] == "box"
                    and _on(end, rect_of(by_id[e]), .035)), None)
        if dev is None:
            return pts
        px, py, pw, ph = picture_rect(dev)
        (x0, y0), (x1, y1) = end, nxt
        if abs(x0 - x1) < 1e-6:                                         # vertical end segment: within the picture's width
            lo, hi = px + min(margin, pw / 3), px + pw - min(margin, pw / 3)
            nx = min(max(x0, lo), hi)
            if abs(nx - x0) < 1e-6:
                return pts
            if len(pts) == 2:
                my = (y0 + y1) / 2
                return [(nx, y0), (nx, my), (x1, my), (x1, y1)]
            return [(nx, y0), (nx, y1)] + pts[2:]
        if abs(y0 - y1) < 1e-6:                                         # horizontal end segment: beside the picture
            lo, hi = py + min(margin, ph / 3), py + ph - min(margin, ph / 3)
            ny = min(max(y0, lo), hi)
            edge = px if x1 < px + pw / 2 else px + pw                  # and it reaches the picture's side (not the caption box edge)
            if abs(ny - y0) < 1e-6:
                return [(edge, y0)] + pts[1:] if abs(edge - x0) > 1e-6 and (x1 - edge) * (x1 - x0) > 0 else pts
            x0 = edge if (x1 - edge) * (x1 - x0) > 0 else x0
            if len(pts) == 2:
                mx = (x0 + x1) / 2
                return [(x0, ny), (mx, ny), (mx, y1), (x1, y1)]
            return [(x0, ny), (x1, ny)] + pts[2:]
        return pts
    out = []
    for c, pts in zip(lines, paths):
        pts = snap_first(c, [tuple(p) for p in pts])
        pts = snap_first(c, pts[::-1])[::-1]
        out.append(_square(pts))
    return out


def _on(pt, r, tol=0.03):
    """True when point pt lies on (or just at) the border of rectangle r = (x, y, w, h)."""
    x, y, w, h = r
    px, py = pt
    inside = x - tol <= px <= x + w + tol and y - tol <= py <= y + h + tol
    near = min(abs(px - x), abs(px - x - w), abs(py - y), abs(py - y - h)) <= tol
    return inside and near


def layer_of(by_id, sid):
    s = by_id.get(sid)
    while s is not None and not s.get("layer") and s.get("parent"):
        s = by_id.get(s["parent"])
    return s.get("layer") if s is not None else None


PLACE_KEYS = ("left_of", "right_of", "above", "below")


def _place(s, where, errors):
    """Relative placement constraints (item 3): {"left_of"|"right_of": id} order a row; "above"/"below" are row hints for the
    generator (rows themselves come from "row")."""
    p = s.get("place")
    if p is None:
        return None
    if not isinstance(p, dict) or any(k not in PLACE_KEYS or not isinstance(v, str) for k, v in p.items()):
        errors.append('%s: "place" must be an object with left_of / right_of / above / below shape ids' % where)
        return None
    return dict(p)


def framed(s):
    return s["kind"] != "group" or s.get("frame", True) is not False


def draw_shape(page, s):
    x, y, w, h = rect_of(s)
    warn = None
    if s["kind"] == "group" and not framed(s):
        return None                                                 # an invisible arrangement: its equipment sits directly in the layer
    if s["kind"] == "zone":
        page.rect("zone", x, y, w, h, fill=s["fill"] or ZONE_FILL, line=BLUE, lw=1.5, pattern=2 if s["dashed"] else 1, key=s["key"])
        if s["label"]:
            size, warn = label_size(s, w - 0.1, 0.25, (9, 8, 7, 6.5, 6), True)
            page.text(x + 0.05, y + h - 0.28, w - 0.1, 0.25, s["label"], size=size, bold=True, halign=0, valign=0)
    elif s["kind"] == "group":                                      # dashed rounded blue box with its title in blue bold at the top
        modern = s.get("reference")
        fill = s["fill"] or (reference_layout.CLIENT if s.get("scope") == "other" else reference_layout.BODY) if modern else s["fill"] or GROUP_FILL
        line = reference_layout.ORANGE if modern and s.get("scope") == "other" else reference_layout.BORDER if modern else GROUP_LINE
        page.rect("zone", x, y, w, h, fill=fill, line=line, lw=1.5, pattern=1 if s.get("solid") else 2, rounding=0.12, key=s["key"])
        if s["label"]:
            size, warn = label_size(s, w - 0.3, 0.25, (11, 10, 9, 8, 7, 6.5), True)
            empty = modern and not s.get("has_children")
            page.text(x + 0.1, y + (h - .32) / 2 if empty else y + h - 0.32, w - 0.2, 0.28, s["label"], size=size, bold=True, color=reference_layout.NAVY if modern else BLUE, valign=0, key=s["key"] + ":title")
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
        first = len(page.shapes)
        modern = bool(s.get("reference"))
        draw_picture(page, s["pic"], s["label"], x, y, w, h, s["key"], soft=True, sub=s.get("sub"), bold=True,
                     fill=reference_layout.FILL if modern else 1.0, visible=modern)
        image = page.shapes[first]
        iw, ih = png_size(s["pic"])
        dpi = min(iw / image["w"], ih / image["h"])
        if modern:
            l, t, r, b = visible_box(s["pic"])
            # v1.7.2: picture size is governed by the per-category minimums in data/equipment_sizes.json (blocking, qa.check_sizes);
            # the former single SMALL_EQUIPMENT warning is retired so the two rules cannot disagree.
            if not s["web"] and dpi < 200:
                quality = "%s: picture has %.0f pixels per displayed inch after enlargement; a sharper original would improve fine detail%s" % (
                    s["where"], dpi, " (approved fixed image left unchanged)" if s["key"].startswith("component:") else "")
                warn = (warn + "; " + quality) if warn else quality
        if s["web"] and dpi < 150:
            quality = "%s: picture has only %.0f pixels per displayed inch; obtain a higher-resolution original (300 recommended)" % (s["where"], dpi)
            warn = (warn + "; " + quality) if warn else quality
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


class LayoutDefect(BuildError):
    """A layout or quality problem the engine may correct itself (more room for the layers involved); carries those layers."""
    def __init__(self, message, layers=(), defects=(), need=None, draft=None):
        BuildError.__init__(self, message)
        self.layers, self.defects, self.need, self.draft = set(layers), list(defects), dict(need or {}), draft


CORRECTION_ATTEMPTS = 6
BOOST_STEP = 1.35


def build(spec, base, out, comps=None, cables=None, spec_dir=".", check_template=True, locked_layout=None):
    """Build with mandatory quality checks (v1.7.2). Layout and quality defects are corrected automatically by giving the layers
    involved more room and rebuilding; if defects remain after the correction passes, nothing is written (NOT BUILT). With
    locked_layout (a signature from an approved preview), the Visio file is written only if the layout is identical to it."""
    comps, cables = comps or Components(), cables or Cables()
    boost, history, last, last_draft = {}, [], [], [None]
    for attempt in range(CORRECTION_ATTEMPTS):
        try:
            r = _build_once(spec, comps, cables, spec_dir, check_template, boost)
        except LayoutDefect as e:
            history.append(str(e).split("\n")[0])
            last = e.defects or [str(e)]
            need = e.need or {l: 1.0 for l in (e.layers or set(spec.get("layers") or []))}
            worst = max(need.values()) if need else 1.0
            for layer, ratio in need.items():                    # the layer furthest below its minimum gains most
                boost[layer] = boost.get(layer, 1.0) * (1 + (BOOST_STEP - 1) * ratio / worst)
            if attempt >= 1 and any("below the" in d or "too short" in d for d in (e.defects or [str(e)])):
                boost["_compact"] = 1                                # still short of room: use the compact control arrangement
            if e.draft is not None:
                last_draft[0] = e.draft
            continue
        if attempt:
            r["warnings"].append("automatic correction: %d rebuild(s) giving more room to %s (%s)" %
                                 (attempt, ", ".join(sorted(boost)), "; ".join(history)))
        r["corrections"] = history
        if locked_layout is not None and r["layout"] != locked_layout:
            raise BuildError("the layout differs from the approved preview (layout lock); build a new preview and have it approved, "
                             "or rebuild from the approved diagram.json")
        write_vsdx(r["page"], out, base, title=str(spec.get("project", {}).get("project", "Architecture")))
        r["out"] = out
        return r
    err = BuildError("blocking quality defects remain after %d automatic correction passes (nothing was written):\n  %s" %
                     (CORRECTION_ATTEMPTS, "\n  ".join(last[:15])))
    err.draft = last_draft[0]                                           # for --draft: a preview of the failing layout, never a Visio file
    raise err


def _layers_named(text, shapes, lines=()):
    """Layers of the shapes (or cable labels) a defect message names."""
    by_id = {s["id"]: s for s in shapes}
    found = set()
    for sid in re.findall(r"[\w.:-]+", text):
        s = by_id.get(sid)
        while s is not None and not s.get("layer") and s.get("parent"):
            s = by_id.get(s["parent"])
        if s is not None and s.get("layer"):
            found.add(s["layer"])
    for c in lines:
        if c.get("label") and c["label"] in text:
            for end in (c["a"], c["b"]):
                found |= _layers_named(end, shapes)
    return found


def _build_once(spec, comps, cables, spec_dir, check_template, boost):
    shapes, lines, warnings = prepare(spec, comps, cables, spec_dir)
    try:
        panels = apply_layers(spec, shapes, warnings, boost)
    except BuildError as e:
        if "cannot fit its contents" in str(e):
            raise LayoutDefect(str(e), _layers_named(str(e), shapes))
        raise
    logical_connections = [dict(c) for c in lines]
    by_id = {s["id"]: s for s in shapes}
    buses = place_buses(spec.get("_buses", []), shapes, by_id, spec.get("lines", []))
    for b in buses:                                                    # a cable may end on a bus (routed to its trunk)
        shapes.append(b)
    lines = reference_layout.group_connections(spec, shapes, lines)
    by_id = {s["id"]: s for s in shapes}
    page = Page()
    given_title = spec.get("title") or spec.get("project", {}).get("doc_name") or "Architecture"
    draw_frame_and_title(page, str(given_title).strip().upper())
    notes = [str(n) for n in spec.get("notes", [])]
    if any(c.get('representative') for c in lines) and cable_labels.GROUPED_NOTE not in notes:
        notes.append(cable_labels.GROUPED_NOTE)
    n_web = sum(1 for s in shapes if s["web"])
    if n_web and spec.get("layout_style") == "legacy":
        notes.append("%d picture(s) come from outside the component library; the source is in the shape data." % n_web)
    given = dict(spec.get("project", {}))
    if "contractor" in given and "client" not in given:        # older files: Contractor is now Client
        given["client"] = given["contractor"]
    missing = [k for k in footer.REQUIRED if not str(given.get(k, "")).strip()]
    if missing:
        warnings.append("footer values printing TBC: %s; if the engineer or the documents gave any of them, add them to \"project\"" % ", ".join(missing))
    rings = prepare_rings(spec, shapes, cables)
    used = sorted({c["cable"] for c in lines} | {r["cable"] for r in rings} | {b["cable"] for b in spec.get("_buses", [])})
    try:
        footer.build_footer(page, spec.get("project", {}), cables.legend(used), notes, allow_tbc=True,
                            style="legacy" if spec.get("layout_style") == "legacy" else "reference")
    except footer.FooterError as e:
        raise BuildError("footer: %s" % e)
    n_footer = len(page.shapes)

    for p in panels:                                                      # layer panels at the very back
        draw_layer(page, p)
    containers = [s for s in shapes if s["kind"] in BEHIND]
    containers.sort(key=lambda s: -(s["w"] * s["h"]))                 # parents before nested children
    for s in containers:
        try:
            w = draw_shape(page, s)
        except ValueError as e:                                         # a cell too small to draw: correctable with more room
            raise LayoutDefect("%s: %s" % (s["id"], e), _layers_named(s["id"], shapes))
        if w:
            warnings.append(w)
    placed = draw_rings(page, rings, by_id, cables, shapes, warnings)      # ring ellipses sit behind the lines and shapes
    bus_paths = draw_buses(page, buses, cables)
    n_lines = 0
    obstacles = [rect_of(s) for s in shapes if s["kind"] not in SEE_THROUGH]
    x0 = MARGIN + (BAND_W + 0.05 if panels and spec.get('layout_style') == 'legacy' else 0.0)
    wired = {}
    for c in lines:                                                         # hardwired: the end with most hardwired cables is the hub (I/O); arrows point into it
        if c["cable"] == "hardwired":
            for end in (c["a"], c["b"]):
                wired[end] = wired.get(end, 0) + 1
    for c in lines:
        if c["cable"] == "hardwired":
            c["hub"] = c["a"] if wired[c["a"]] > wired[c["b"]] else c["b"]
    reqs = [dict(a=rect_of(by_id[c["a"]]), b=rect_of(by_id[c["b"]]), a_id=c["a"], b_id=c["b"], via=c["via"], straight=c["straight"],
                 from_side=c.get("from_side"), to_side=c.get("to_side"), bus=c.get("hub")) for c in lines]
    try:
        bounds = (x0, BOTTOM, MARGIN + AREA_W, TOP)
        group_indices = [i for i, c in enumerate(lines) if by_id[c["a"]]["kind"] == "group" or by_id[c["b"]]["kind"] == "group"]
        normal_indices = [i for i in range(len(lines)) if i not in group_indices]
        routed = [None] * len(lines)
        boxes = [rect_of(s) for s in shapes if s["kind"] in ("group", "zone") and framed(s)] + [(MARGIN + p["x"], TOP - p["y"] - p["h"], p["w"], p["h"]) for p in panels]
        boxes += [(b["x"] + MARGIN, b["trunk_y"] - .01, b["w"], .02) for b in buses]     # cables keep clear of bus trunks
        def common_box(c):                                              # innermost group holding both ends: a cable between them stays inside it
            def chain(i):
                out, s = [], by_id[i]
                while s.get("parent"):
                    s = by_id[s["parent"]]
                    out.append(s["id"])
                return out
            up_a, up_b = chain(c["a"]), set(chain(c["b"]))
            for gid in up_a:
                if gid in up_b and framed(by_id[gid]):
                    return rect_of(by_id[gid])
            return None
        panel_rect = {p["id"]: (MARGIN + p["x"], TOP - p["y"] - p["h"], p["w"], p["h"]) for p in panels}

        def corridor(c):
            """Item 6: the band of layers a cable connects (with the gaps between them) is its routing corridor; it never runs
            through a layer it does not serve."""
            rs = [panel_rect.get(layer_of(by_id, e)) for e in (c["a"], c["b"])]
            if not all(rs):
                return None
            lo = min(r[1] for r in rs)
            hi = max(r[1] + r[3] for r in rs)
            return (MARGIN, lo, AREA_W, hi - lo)
        reserved = {}                                                   # item 6: the facing sides of a directly linked pair (e.g. a
        for c in lines:                                                 # redundancy sync link) belong to that link alone
            if c.get("direct") and c["a"] in by_id and c["b"] in by_id:
                ra, rb = rect_of(by_id[c["a"]]), rect_of(by_id[c["b"]])
                if ra[0] + ra[2] <= rb[0]:
                    reserved.setdefault(c["a"], set()).add("right")
                    reserved.setdefault(c["b"], set()).add("left")
                elif rb[0] + rb[2] <= ra[0]:
                    reserved.setdefault(c["a"], set()).add("left")
                    reserved.setdefault(c["b"], set()).add("right")
        for i, c in enumerate(lines):
            if not (c["via"] or c.get("from_side") or c.get("to_side") or c["straight"]):
                reqs[i]["home"] = common_box(c) or corridor(c)
            reqs[i]["corridor"] = corridor(c)
            if not c.get("direct"):
                reqs[i]["a_reserved"], reqs[i]["b_reserved"] = reserved.get(c["a"], ()), reserved.get(c["b"], ())
        keepout = []                                                    # group titles are text a cable must not run through
        for s in shapes:
            if s["kind"] == "group" and s["label"] and s.get("has_children") and framed(s):
                gx, gy, gw, gh = rect_of(s)
                tw = min(gw - .2, len(s["label"]) * .085 + .3)
                keepout.append((gx + (gw - tw) / 2, gy + gh - .36, tw, .32))
        normal_routes = router.route_all([reqs[i] for i in normal_indices], obstacles, bounds, boxes, keepout)
        for i, pts in zip(normal_indices, normal_routes):
            routed[i] = pts
        for i in group_indices:
            c, q = lines[i], reqs[i]
            endpoint_ids = {c["a"], c["b"]}
            def inside_endpoint(s):
                while s.get("parent"):
                    if s["parent"] in endpoint_ids:
                        return True
                    s = by_id[s["parent"]]
                return False
            blockers = [rect_of(s) for s in shapes if s["id"] not in endpoint_ids and s["kind"] not in SEE_THROUGH and not inside_endpoint(s)]
            # A group's own children are inside its boundary and must not block
            # the connector from attaching to the container's outside edge.
            manual = q.get("via") or q.get("from_side") or q.get("to_side") or q.get("straight")
            simple = route(q["a"], q["b"], [])
            if not manual and not any(crosses(simple, r) for r in blockers):
                routed[i] = simple
            else:
                routed[i] = router.route_all([q], blockers + [q["a"], q["b"]], bounds, boxes)[0]
    except Exception as e:                                                  # never lose the drawing over the router
        warnings.append("automatic cable routing failed (%s); plain routes used" % e)
        routed = [None] * len(lines)
    paths = []
    for c, q, pts in zip(lines, reqs, routed):
        if pts is None:
            pts = route(q["a"], q["b"], c["via"])
            if not c["via"]:
                if not any(by_id[e]["kind"] == "bus" for e in (c["a"], c["b"])):   # bus uplinks are drawn directly afterwards
                    warnings.append("%s (%s to %s): no clear square route found; a plain one was drawn" % (c["where"], c["a"], c["b"]))
        paths.append(pts)
    paths = [_square(p) for p in paths]
    if spec.get("layout_style", "reference") == "reference":
        paths = snap_ends(lines, paths, by_id)
    for i, c in enumerate(lines):                                       # a bus uplink is a straight vertical drop to the trunk
        bus = next((by_id[e] for e in (c["a"], c["b"]) if by_id[e]["kind"] == "bus"), None)
        if bus is None:
            continue
        dev = by_id[c["b"] if bus["id"] == c["a"] else c["a"]]
        x, y, w, h = rect_of(dev)
        x = picture_rect(dev)[0] + picture_rect(dev)[2] / 2 - w / 2 if dev["kind"] == "box" else x
        cx, ty = x + w / 2, bus["trunk_y"]
        start = (cx, y) if y > ty else (cx, y + h)
        pts = [start, (cx, ty)]
        paths[i] = pts if bus["id"] == c["b"] else pts[::-1]
    if spec.get("layout_style", "reference") == "reference":
        paths = separate(lines, paths, lambda i: rect_of(by_id[i]), obstacles)
    drawn_paths = []
    for c, pts in zip(lines, router.add_hops(paths)):
        color, pattern = cables.line_style(c["cable"])
        # 8.4 arrowheads: hardwired signals point into the I/O (their destination); a line may ask for "end" (at its
        # "to" device) or "both" (bidirectional, e.g. a redundancy sync link); Ethernet and other network links have none.
        arrows = c.get("arrows")
        arrow = c.get("hub") is not None if arrows is None else arrows in ("end", "both")
        start = arrows == "both"
        if arrows is None and arrow and c["hub"] == c["a"]:
            pts = pts[::-1]                                                 # the arrowhead is on the last point: make that the hub end
        elif arrows == "end" and pts and rect_of(by_id[c["a"]]) and _on(pts[-1], rect_of(by_id[c["a"]])) and not _on(pts[-1], rect_of(by_id[c["b"]])):
            pts = pts[::-1]
        key = "%s->%s" % (c["a"], c["b"])
        if c.get("source_connections"):
            key += "|logical=" + ",".join("%s->%s" % pair for pair in c["source_connections"])
        page.line(pts, color, pattern, lw=CABLE_LW, key=key, arrow=arrow, arrow_start=start)
        drawn_paths.append(pts)
        n_lines += 1
    for c, pts in zip(lines, paths):
        if c["via"]:                                                        # a hand-routed cable may run through a device: say so
            for s in shapes:
                if s["kind"] not in SEE_THROUGH and s["id"] not in (c["a"], c["b"]) and crosses(pts, rect_of(s)):
                    warnings.append("%s (%s to %s) passes through shape %r; add a \"via\" point to route round it" % (c["where"], c["a"], c["b"], s["id"]))
    n_lines += draw_ring_links(page, placed, by_id, cables, shapes, warnings)
    for s in (s for s in shapes if s["kind"] not in BEHIND and s["kind"] != "bus"):
        try:
            w = draw_shape(page, s)
        except ValueError as e:                                         # a cell too small to draw: correctable with more room
            raise LayoutDefect("%s: %s" % (s["id"], e), _layers_named(s["id"], shapes))
        if w:
            warnings.append(w)
    warnings += ["shapes %r and %r overlap" % p for p in overlapping(shapes)]
    try:
        cable_labels.draw(page, lines, paths, shapes, warnings, sys.modules[__name__])
    except BuildError as e:
        if "cannot fit" in str(e):
            raise LayoutDefect(str(e), _layers_named(str(e), shapes, lines), draft={"page": page, "qa": [str(e)]})
        raise
    keep_on_page(page, n_footer, warnings)
    defects = []
    if spec.get("layout_style", "reference") == "reference":           # Phases 8, 9 and 11-E: automatic drawing checks
        defects += qa.check_cables(lines, drawn_paths, lambda i: rect_of(by_id[i]))
        bus_lines = [{"a": b["id"], "b": b["id"], "cable": b["cable"]} for b in buses]
        defects += qa.check_cable_spacing(lines + bus_lines, paths + [bp for bp in bus_paths[:0]] + [
            [(b["x"] + MARGIN, b["trunk_y"]), (b["x"] + MARGIN + b["w"], b["trunk_y"])] for b in buses])
        defects += qa.check_inside(paths + bus_paths, BOTTOM, TOP, MARGIN, MARGIN + AREA_W)
        defects += qa.check_picture_ends(lines, paths, by_id, picture_rect, lambda pt, d: _on(pt, rect_of(d), .035))
        defects += qa.check_attachments(lines, paths)
        defects += qa.check_headings(page, panels)
        defects += qa.check_containers(shapes)
        defects += qa.check_text(page, BOTTOM)
        defects += qa.check_page(page)
        defects += qa.check_sizes(shapes)
        defects += qa.check_clearance(lines, paths, shapes, lambda i: rect_of(by_id[i]))
        defects += qa.check_corridors(lines, paths, [r.get("corridor") for r in reqs], shapes, lambda i: rect_of(by_id[i]))
        if check_template:
            locked = qa.check_template(page)
            if locked:
                raise BuildError("the approved header/footer template must not change:\n  " + "\n  ".join(locked))
        if defects:                                                    # blocking: corrected automatically or NOT BUILT
            need = {}
            for d in defects:
                m = re.search(r"is ([\d.]+) in, below the ([\d.]+) in minimum", d)
                ratio = float(m.group(2)) / max(.01, float(m.group(1))) if m else 1.1
                for layer in _layers_named(d, shapes, lines):
                    need[layer] = max(need.get(layer, 1.0), ratio)
            raise LayoutDefect("%d quality defect(s): %s" % (len(defects), defects[0]), set(need), defects, need,
                               draft={"page": page, "qa": defects})
    return {"out": None, "shapes": len(shapes), "lines": n_lines, "layout": qa.layout_signature(page), "warnings": warnings, "notices": list(getattr(warnings, "notices", [])), "notes": notes, "page": page,
            "logical_connections": logical_connections, "display_connections": lines, "qa": defects}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise BuildError("cannot read %s: %s" % (path, e))


def lock_path(out):
    return os.path.splitext(out)[0] + ".layout.json"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("spec")
    ap.add_argument("--base", default=os.path.join(ROOT, "base", "base.vsdx"))
    ap.add_argument("--out", help="output .vsdx (default: Downloads\\out\\<file name>.vsdx)")
    ap.add_argument("--preview", action="store_true",
                    help="also write the approval preview (PNG, rendered from the same drawing as the Visio file; needs Pillow) and the "
                         "layout lock <out>.layout.json")
    ap.add_argument("--locked-layout", metavar="LAYOUT_JSON",
                    help="write the Visio file only if its layout is identical to this approved preview's lock")
    ap.add_argument("--check-spec", metavar="ARCHITECTURE_SPEC_JSON",
                    help="the questionnaire specification this diagram was generated from: the build is refused if the diagram does not "
                         "show exactly its units, quantities, connections and placement (arch_spec.py verify-diagram)")
    ap.add_argument("--draft", action="store_true",
                    help="if blocking defects remain, render a DRAFT preview of the failing layout to look at (no Visio file is written)")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.expanduser("~"), "Downloads", "out", os.path.splitext(os.path.basename(a.spec))[0] + ".vsdx")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    locked = None
    if a.locked_layout:
        with open(a.locked_layout, encoding="utf-8") as fh:
            locked = json.load(fh)["layout"]
    if a.check_spec:                                                   # hierarchy level 2: the confirmed specification wins
        import arch_spec
        problems = arch_spec.verify_diagram(arch_spec.load(a.check_spec), load_json(a.spec))
        if problems:
            print("NOT BUILT: the diagram does not match the confirmed specification:\n  " + "\n  ".join(problems))
            sys.exit(1)
    try:
        r = build(load_json(a.spec), a.base, out, spec_dir=os.path.dirname(os.path.abspath(a.spec)), locked_layout=locked)
    except BuildError as e:
        print("NOT BUILT: %s" % e)
        draft = getattr(e, "draft", None)
        if a.draft and draft:
            import dev_preview
            png = os.path.splitext(out)[0] + "_DRAFT_preview.png"
            dev_preview.render(draft["page"], png)
            print("draft preview (not deliverable):", png)
        sys.exit(1)
    print("built %s: %d shapes, %d lines" % (r["out"], r["shapes"], r["lines"]))
    for w in r["warnings"]:
        print("  warning:", w)
    for w in r["notices"]:
        print("  notice:", w)
    print("qa: no defects found (blocking checks passed)")
    if a.preview:
        import dev_preview
        png = os.path.splitext(out)[0] + "_preview.png"
        dev_preview.render(r["page"], png)
        with open(lock_path(out), "w", encoding="utf-8") as fh:
            json.dump({"layout": r["layout"], "note": "Layout lock of the approved preview. Export with --locked-layout this file: the "
                                                     "Visio file is written only if its layout is identical."}, fh, indent=1)
        print("preview:", png)
        print("layout lock:", lock_path(out))
    if locked:
        print("layout matches the approved preview")
