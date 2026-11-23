"""Reference layout: content-sized layers, nested equipment frames and shared links.

All geometry stays editable. This module never supplies cable colours.
"""
import math
from cable_labels import TYPICAL_LABEL
from textfit import fit_size
from draw import LABEL_ZONE, SUB_ZONE, visible_size, visible_box
from vsdx_writer import png_size

NAVY, BORDER = "#073878", "#27369B"
LIGHT_BLUE, BODY, CLIENT, ORANGE = "#E4F3FF", "#F5FAFF", "#FFE5B5", "#FF8800"
TAB_BLUE = "#001477"
GAP, PAD, TITLE = .12, .14, .30
LAYER_GAP = .34  # room for tabs above each layer without entering the preceding layer
CHANNEL = .16    # clear band between device rows for cable routing
CABLE_GAP = .50  # band between rows that hold container boxes: a cable keeps ~7 mm from both borders
CABLE_GAP_X = .45  # side-by-side container boxes: room for a vertical cable with clearance
BAND = .36       # clear band above and below a row inside a container whose devices are linked past a neighbour
EDGE = .05       # clearance between the outer rows and the container border
DEVICE_W = 1.35  # relative width weight of one device: every device in a row gets an equal share
FILL = .90       # target occupancy of a device's image area in its limiting dimension (80-90 %)


def natural_height(s):
    """Relative height a device needs: its caption plus a picture height that follows the picture's shape,
    so layers holding tall, narrow equipment (PLCs, racks) get more height than layers of wide equipment (servers, switches)."""
    pic = s.get("pic")
    if not pic:
        return s["h"]
    try:
        l, t, r, b = visible_box(pic)
        iw, ih = png_size(pic)
        ar = (r - l) * iw / ((b - t) * ih)
    except Exception:
        return s["h"]
    return LABEL_ZONE + (SUB_ZONE if s.get("sub") else 0) + min(1.3, max(.55, 1.2 / math.sqrt(ar)))


_WIRED = {"pairs": [], "parent": {}, "cache": {}}


def isgroup(c):
    return c["kind"] == "group"


def _subtree(item):
    """Ids of a shape and everything inside it."""
    key = item["id"]
    cache = _WIRED["cache"]
    if key not in cache:
        cache[key] = {key} | {i for i, p in _WIRED["parent"].items() if _ancestors(i) & {key}}
    return cache[key]


def _ancestors(i):
    out, parents = set(), _WIRED["parent"]
    while parents.get(i):
        i = parents[i]
        out.add(i)
    return out


def _linked(a_items, b_items):
    """True when some cable joins something in `a_items` with something in `b_items`."""
    a = set().union(*[_subtree(i) for i in a_items]) if a_items else set()
    b = set().union(*[_subtree(i) for i in b_items]) if b_items else set()
    return any((x in a and y in b) or (x in b and y in a) for x, y in _WIRED["pairs"])


def edge_for(rs):
    """Clearance between a container's border and its outer rows: wide when a cable must run past a neighbouring
    device in the same row (it needs a band to pass in), otherwise small."""
    for row in rs:
        for i, a in enumerate(row):
            for b in row[i + 2:]:
                if _linked([a], [b]):
                    return BAND
    return EDGE


def vgap(upper, lower):
    """Band between two rows: wide where container borders face each other and a cable runs between them."""
    return CABLE_GAP if any(map(isgroup, upper + lower)) and _linked(upper, lower) else CHANNEL if not any(map(isgroup, upper + lower)) else CABLE_GAP * .5


def hgap(left, right):
    if not (isgroup(left) or isgroup(right)):
        return GAP
    return CABLE_GAP_X if _linked([left], [right]) else CABLE_GAP_X * .5


def apply_layers(spec, shapes, warnings, B):
    wanted = spec.get("layers")
    if wanted is None:
        if any(s.get("layer") or s.get("parent") for s in shapes):
            raise B.BuildError('shapes use "layer" but the file has no "layers" list')
        return []
    table = B.load_layers()
    ids = [t["id"] for t in table]
    if not isinstance(wanted, list) or not wanted or any(w not in ids for w in wanted) or len(set(wanted)) != len(wanted):
        raise B.BuildError('"layers" must be a list of distinct standard layer ids')
    by_id = {s["id"]: s for s in shapes}
    _WIRED.update(pairs=[(str(c.get("from")), str(c.get("to"))) for c in spec.get("lines", []) if isinstance(c, dict)],
                  parent={s["id"]: s.get("parent") for s in shapes}, cache={})
    # Validate the hierarchy before modifying coordinates. Layer inheritance is
    # explicit and cycles/foreign parents never silently produce a broken page.
    def inherit(s, trail):
        if s["id"] in trail:
            raise B.BuildError("container parent cycle at %r" % s["id"])
        parent = s.get("parent")
        if s.get("placement") not in (None, "beside"):
            raise B.BuildError('placement must be "beside" or omitted')
        for key in ("width_weight", "max_width", "max_height"):
            if s.get(key) is not None and (B._num(s[key]) is None or float(s[key]) <= 0):
                raise B.BuildError("%s must be a positive number" % key)
        if parent:
            p = by_id.get(parent)
            if not p or p["kind"] != "group":
                raise B.BuildError("shape %r: parent must name a group" % s["id"])
            inherit(p, trail | {s["id"]})
            if s.get("layer") and s["layer"] != p.get("layer"):
                raise B.BuildError("shape %r and its parent must use the same layer" % s["id"])
            s["layer"] = p.get("layer")
            if not s["layer"]:
                raise B.BuildError("a top-level parent group must specify its layer")
        if s.get("layer") and s["layer"] not in wanted:
            raise B.BuildError("shape layer %r is not in layers" % s["layer"])
    for s in shapes:
        inherit(s, set())
    # Loose equipment is organised into a layer container automatically.
    for layer in wanted:
        loose = [s for s in shapes if s.get("layer") == layer and not s.get("parent") and s["kind"] not in B.BEHIND]
        if loose:
            gid = "__equipment_" + layer
            if gid in by_id:
                raise B.BuildError("reserved generated group id %r" % gid)
            group = _group(gid, layer, "", loose, B)
            shapes.append(group)
            by_id[gid] = group
            for s in loose:
                s["parent"] = gid
    # Give a control device receiving field hardwiring a small rack frame.
    if spec.get("cable_detail", "grouped") not in ("grouped", "individual"):
        raise B.BuildError('cable_detail must be "grouped" or "individual"')
    if spec.get("cable_detail", "grouped") == "grouped":
        racks, fed = set(), {}
        for c in spec.get("lines", []):
            if c.get("cable") != "hardwired" or c.get("individual") or c.get("via") or c.get("from_side") or c.get("to_side") or c.get("straight"):
                continue
            a, b = by_id.get(str(c.get("from"))), by_id.get(str(c.get("to")))
            if a and b and {a.get("layer"), b.get("layer")} == {"field", "control"}:
                target = b if b.get("layer") == "control" else a
                if target["kind"] == "box":
                    fed.setdefault(target.get("parent"), set()).add(target["id"])
        # Racks that share one parent form ONE common I/O box: the parent becomes the
        # solid rack frame and no rack gets a box of its own. Only a lone rack that
        # sits among other equipment still receives a small frame, so grouped
        # field cables have a boundary to end on.
        for pid, members in fed.items():
            parent = by_id.get(pid)
            children = [s for s in shapes if s.get("parent") == pid]
            if parent and parent["kind"] == "group" and {s["id"] for s in children if s["kind"] == "box"} == members == {s["id"] for s in children}:
                parent["solid"] = True          # a dedicated I/O container: one box for all its racks
            elif not parent or not parent.get("solid"):
                racks.update(members)
        for sid in sorted(racks):
            device = by_id[sid]
            gid = "__rack_" + sid
            if gid in by_id:
                raise B.BuildError("reserved generated group id %r" % gid)
            group = _group(gid, "control", "", [device], B)
            group.update(parent=device.get("parent"), solid=True, row=device.get("row"))
            device["parent"] = gid
            device["row"] = None
            shapes.append(group)
            by_id[gid] = group
    # I/O topology is never assumed from placement: every rack in a common I/O box needs an explicit
    # communication line (daisy chain, switch/star or the PLC) - say so when one is missing.
    talk = {str(c.get(k)) for c in spec.get("lines", []) if isinstance(c, dict) and c.get("cable") != "hardwired" for k in ("from", "to")}
    for g in [s for s in shapes if s["kind"] == "group" and s.get("solid") and not s.get("generated")]:
        for rack in [s for s in shapes if s.get("parent") == g["id"] and s["kind"] == "box"]:
            if rack["id"] not in talk and g["id"] not in talk:
                warnings.append("I/O rack %r has no communication line: topology is never assumed from placement; give its "
                                "daisy-chain, star or redundant connections (a \"chain\" line, or from/to lines)" % rack["id"])
    for g in [s for s in shapes if s["kind"] == "group" and not s.get("label") and not s.get("generated")]:
        kids = [s for s in shapes if s.get("parent") == g["id"]]
        if len(kids) == 1 and kids[0]["kind"] == "group":
            warnings.append("group %r is an unlabeled box that only wraps group %r: remove it unless it marks a scope, panel, site or "
                            "security zone (use as few boxes as the drawing allows)" % (g["id"], kids[0]["id"]))
    _WIRED.update(parent={s["id"]: s.get("parent") for s in shapes}, cache={})   # generated groups now exist
    def children(group):
        return [s for s in shapes if s.get("parent") == group["id"]]
    def rows(group):
        members = children(group)
        if not members:
            return []
        cols = group.get("columns")
        if cols is None:
            cols = 3 if group.get("layer") == "control" else min(12, len(members))
        if not isinstance(cols, int) or isinstance(cols, bool) or cols < 1 or cols > 24:
            raise B.BuildError("group %r: columns must be an integer from 1 to 24" % group["id"])
        explicit = any(s.get("row") is not None for s in members)
        if explicit:
            for s in members:
                row = s.get("row", None)
                if row is not None and (not isinstance(row, int) or isinstance(row, bool) or row < 0 or row > 24):
                    raise B.BuildError("shape %r: row must be an integer from 0 to 24" % s["id"])
            return [[s for s in members if (s.get("row") or 0) == i] for i in sorted({s.get("row") or 0 for s in members})]
        return [members[i:i + cols] for i in range(0, len(members), cols)]
    def measure(s):
        if s["kind"] != "group":
            return DEVICE_W, natural_height(s)  # natural size is only a weight: it is never a maximum
        rs = rows(s)
        if not rs:
            return s["w"], .75  # a system summary box needs little height
        dims = [[measure(c) for c in row] for row in rs]
        width = max(sum(w for w, h in row) + sum(hgap(a, b) for a, b in zip(r, r[1:])) for row, r in zip(dims, rs))
        height = sum(max(h for w, h in row) for row in dims) + sum(vgap(a, b) for a, b in zip(rs, rs[1:]))
        return (width + 2 * PAD, height + 2 * (PAD + edge_for(rs)) + (TITLE if s["label"] else 0))
    weights = spec.get("layer_weights", {})
    if not isinstance(weights, dict) or any(k not in wanted or B._num(v) is None or float(v) <= 0 for k, v in weights.items()):
        raise B.BuildError("layer_weights must map included layer ids to positive numbers")
    order = [t for t in table if t["id"] in wanted]
    natural = {}
    for t in order:
        roots = [s for s in shapes if s.get("layer") == t["id"] and not s.get("parent")]
        # A layer's share follows what it must hold (rows of pictures, captions, titles), so large
        # pictures get room and blank space is not reserved for an arbitrary layer proportion.
        need = max([measure(s)[1] for s in roots] or [1.0]) + .32
        natural[t["id"]] = float(weights.get(t["id"], max(need, .9)))
    available = B.AREA_H - LAYER_GAP * (len(order) - 1)
    total = sum(natural.values())
    panels, y = [], 0.0
    options = spec.get("layer_headers", {})
    if not isinstance(options, dict):
        raise B.BuildError("layer_headers must be an object")
    for t in order:
        h = available * natural[t["id"]] / total
        override = options.get(t["id"], {})
        if not isinstance(override, dict):
            raise B.BuildError("each layer_headers entry must be an object")
        default_name = "Control System" if t["id"] == "control" else t["name"]
        p = dict(t, x=0., y=y, w=B.AREA_W, h=h, reference=True,
                 name=str(override.get("name", default_name)), desc=str(override.get("description", "")))
        panels.append(p)
        roots = [s for s in shapes if s.get("layer") == t["id"] and not s.get("parent")]
        side = [s for s in roots if s.get("placement") == "beside"]
        if side and t["id"] != "control":
            raise B.BuildError('placement="beside" is for a requested panel in the control layer')
        roots = [s for s in roots if s not in side] + side
        # Headers occupy a shallow row above equipment, never a full-height
        # left column. Root blocks fill the page width between equal margins.
        x = PAD
        header = min(.60 if p['desc'] else .30, h * .42)
        bottom_pad = min(PAD, h * .08)
        width, height = B.AREA_W - 2 * PAD, h - header - bottom_pad
        shares = [float(s.get("width_weight") or (1 if s in side else 3 if side else 1)) for s in roots]
        if any(not math.isfinite(v) or v <= 0 for v in shares):
            raise B.BuildError("width_weight must be positive")
        usable = width - CABLE_GAP_X * max(0, len(roots) - 1)
        for s, share in zip(roots, shares):
            w = usable * share / sum(shares)
            pw, ph = min(w, float(s.get("max_width") or w)), min(height, float(s.get("max_height") or height))
            place(s, x, y + header + (height - ph) / 2, pw, ph, rows, measure, warnings, B)
            x += w + CABLE_GAP_X
        y += h + LAYER_GAP
    for s in shapes:
        s["reference"] = True
        s["has_children"] = any(c.get("parent") == s["id"] for c in shapes)
    equalise(shapes)
    tighten(shapes)
    return panels


def _group(gid, layer, label, members, B):
    return dict(id=gid, kind="group", label=label, layer=layer, parent=None,
                pic=None, web=False, key="shape:" + gid, x=0., y=0., w=1.35, h=1.25,
                fill=None, dashed=True, bold=True, size=None, where="group %r" % gid,
                auto_x=True, line=None, sub=None, scope="avanceon", generated=True)


def place(s, x, y, w, h, rows, measure, warnings, B):
    """Place a container's children so they fill it. Default device sizes are only relative
    weights: each row gets a share of the height and each device an equal share of the row
    width (nested groups are weighted by the devices they hold)."""
    s.update(x=x, y=y, w=w, h=h)
    if s["kind"] != "group":
        return
    rs = rows(s)
    if not rs:
        return
    padding = min(PAD, h * .08)
    title = min(TITLE, h * .18) if s["label"] else 0
    inner_w, inner_h = w - 2 * padding, h - 2 * padding - title
    dims = [[measure(c) for c in row] for row in rs]
    edge = min(edge_for(rs), inner_h / 6.)
    row_nat = [max(ch for cw, ch in row) for row in dims]
    channels = [vgap(a, b) for a, b in zip(rs, rs[1:])]
    room = inner_h - 2 * edge
    if sum(channels) > .45 * room:                                  # never let the channels crowd the equipment out
        channels = [c * .45 * room / sum(channels) for c in channels]
    avail_h = room - sum(channels)
    if avail_h <= 0 or inner_w <= 0:
        raise B.BuildError("group %r cannot fit its contents on A3" % s["id"])
    heights = [avail_h * n / sum(row_nat) for n in row_nat]
    cy = y + padding + title + edge
    for r, (row, sizes, rh) in enumerate(zip(rs, dims, heights)):
        gaps = [hgap(a, b) for a, b in zip(row, row[1:])]
        if sum(gaps) > .3 * inner_w:
            gaps = [g * .3 * inner_w / sum(gaps) for g in gaps]
        usable = inner_w - sum(gaps)
        total = sum(cw for cw, ch in sizes)
        if usable / total < .55 * DEVICE_W or rh < .5 * min(ch for cw, ch in sizes):
            warnings.append("group %r is crowded; increase its layer weight or reduce equipment" % s["id"])
        cx = x + padding
        for k, (c, (cw, ch)) in enumerate(zip(row, sizes)):
            cell_w = usable * cw / total
            place(c, cx, cy, cell_w, rh, rows, measure, warnings, B)
            cx += cell_w + (gaps[k] if k < len(gaps) else 0)
        cy += rh + (channels[r] if r < len(channels) else 0)


def tighten(shapes):
    """After sizing, shrink every device's rectangle to the footprint it really occupies: the picture's visible
    equipment (at FILL occupancy) plus its caption. Cables then attach to the equipment instead of to empty
    cell space, and the clearance rules measure from the equipment."""
    for d in shapes:
        if d["kind"] != "box" or not d.get("reference") or not d.get("pic"):
            continue
        sub_h = SUB_ZONE if d.get("sub") else 0
        area_h = d["h"] - LABEL_ZONE - sub_h
        if area_h <= 0:
            continue
        try:
            vis_w, vis_h = visible_size(d["pic"], d["w"], area_h, FILL)
        except Exception:
            continue
        caption = max(len(d["label"]), len(d.get("sub") or "")) * .0546 + .08
        new_w = min(d["w"], max(vis_w / FILL, caption))
        new_h = min(d["h"], vis_h / FILL + LABEL_ZONE + sub_h)
        d["x"] += (d["w"] - new_w) / 2
        d["y"] += (d["h"] - new_h) / 2
        d["w"], d["h"] = new_w, new_h


def equalise(shapes):
    """Comparable devices share one displayed cell size: the smallest cell of their category
    (same component or picture). Field instruments also share one height. Different equipment
    types keep their natural proportions because each picture is fitted by aspect ratio."""
    devices = [s for s in shapes if s["kind"] == "box" and s.get("reference")]
    def apply(group, width=True):
        ws, hs = min(d["w"] for d in group), min(d["h"] for d in group)
        for d in group:
            if width:
                d["x"] += (d["w"] - ws) / 2
                d["w"] = ws
            d["y"] += (d["h"] - hs) / 2
            d["h"] = hs
    by_key = {}
    for d in devices:                       # the same picture file means the same equipment type
        by_key.setdefault(d.get("pic") or d.get("key"), []).append(d)
    for key, group in by_key.items():
        if len(group) > 1 and key:
            apply(group)
    field = [d for d in devices if d.get("layer") == "field"]
    if len(field) > 1:
        apply(field, width=False)


def group_connections(spec, shapes, lines):
    """Collapse field hardwiring only; retain all original logical connections."""
    if not spec.get("layers") or spec.get("layout_style") == "legacy" or spec.get("cable_detail", "grouped") == "individual":
        return lines
    by_id = {s["id"]: s for s in shapes}
    def ancestors(s):
        ids = {s["id"]}
        while s.get("parent"):
            s = by_id[s["parent"]]
            ids.add(s["id"])
        return ids
    def boundary(s, other):
        # Keep internal wiring inside the shared container. Across containers,
        # promote endpoints to the outside box so cables do not traverse pictures.
        if s["kind"] == "group":
            return s  # an explicit box endpoint is already the intended boundary
        other_parents = ancestors(other)
        while s.get("parent") and s["parent"] not in other_parents:
            s = by_id[s["parent"]]
        return s
    out, shared = [], {}
    for c in lines:
        a, b = by_id[c["a"]], by_id[c["b"]]
        explicit = c.get("individual") or c.get("direct") or c.get("via") or c.get("from_side") or c.get("to_side") or c.get("straight")
        if explicit:
            out.append(c)
            continue
        if c["cable"] != "hardwired" or {a.get("layer"), b.get("layer")} != {"field", "control"}:
            aa, bb = boundary(a, b), boundary(b, a)
            if (aa["id"], bb["id"]) != (a["id"], b["id"]):
                c = dict(c, a=aa["id"], b=bb["id"], source_connections=[(a["id"], b["id"])])
            out.append(c)
            continue
        source, target = (a, b) if a.get("layer") == "field" else (b, a)
        while source.get("parent"):
            source = by_id[source["parent"]]
        if target["kind"] != "group" and target.get("parent"):
            target = by_id[target["parent"]]
        key = (source["id"], target["id"], c["cable"])
        if key not in shared:
            displayed = dict(c, a=key[0], b=key[1], source_connections=[], representative=True, label=TYPICAL_LABEL)
            shared[key] = displayed
            out.append(displayed)
        shared[key]["source_connections"].append((c["a"], c["b"]))
    return out


def draw_layer(page, p, B):
    x, y, w, h = B.MARGIN + p["x"], B.TOP - p["y"] - p["h"], p["w"], p["h"]
    # A single layer frame, with a navy tab straddling its top border.
    # Descriptions use a shallow header row; equipment fills the width below.
    page.rect("zone", x, y, w, h, fill=BODY, line=BORDER, lw=1.5, rounding=.04, key="layer:" + p["id"])
    label = p["name"]
    tab_w = min(w - .24, max(1.7, min(3.4, .30 + len(label) * .135)))
    tab_h, tab_y = .36, y + h - .18
    size = fit_size(label, tab_w - .20, tab_h - .04, (14, 13, 12, 11, 10, 9, 8), True)
    page.rect("zone", x + .13, tab_y, tab_w, tab_h, fill=TAB_BLUE, line=TAB_BLUE,
              lw=1.5, rounding=.10, key="layer-heading:" + p["id"])
    page.text(x + .23, tab_y + .02, tab_w - .20, tab_h - .04, label,
              size=size, bold=True, color="#FFFFFF", key="layer-name:" + p["id"])
    if p.get("desc"):
        desc_h = min(.28, h * .20)
        desc_size = fit_size(p["desc"], w - 2 * PAD, desc_h, (10, 9, 8, 7, 6), True)
        page.text(x + PAD, y + h - .23 - desc_h, w - 2 * PAD, desc_h, p["desc"],
                  size=desc_size, bold=True, halign=0, valign=2, key="layer-desc:" + p["id"])
    return size
