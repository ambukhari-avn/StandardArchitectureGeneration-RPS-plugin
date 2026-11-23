"""Reference layout: content-sized layers, nested equipment frames and shared links.

All geometry stays editable. This module never supplies cable colours.
"""
import math
from cable_labels import TYPICAL_LABEL
from textfit import fit_size

NAVY, BORDER = "#073878", "#27369B"
LIGHT_BLUE, BODY, CLIENT, ORANGE = "#E4F3FF", "#F5FAFF", "#FFE5B5", "#FF8800"
TAB_BLUE = "#001477"
GAP, PAD, TITLE = .12, .18, .32
LAYER_GAP = .26  # room for tabs above each layer without entering the preceding layer
CHANNEL = .16    # clear band between device rows for cable routing
EDGE = .05       # clearance between the outer rows and the container border
DEVICE_W = 1.35  # relative width weight of one device: every device in a row gets an equal share
FILL = .90       # target occupancy of a device's image area in its limiting dimension (80-90 %)


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
        racks = set()
        for c in spec.get("lines", []):
            if c.get("cable") != "hardwired" or c.get("individual") or c.get("via") or c.get("from_side") or c.get("to_side") or c.get("straight"):
                continue
            a, b = by_id.get(str(c.get("from"))), by_id.get(str(c.get("to")))
            if a and b and {a.get("layer"), b.get("layer")} == {"field", "control"}:
                target = b if b.get("layer") == "control" else a
                if target["kind"] == "box":
                    parent = by_id.get(target.get("parent"))
                    if not parent or not parent.get("solid") or sum(s.get('parent') == parent['id'] and s['kind'] == 'box' for s in shapes) > 1:
                        racks.add(target["id"])
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
            return DEVICE_W, s["h"]  # natural size is only a weight: it is never a maximum
        rs = rows(s)
        if not rs:
            return s["w"], .75  # a system summary box needs little height
        dims = [[measure(c) for c in row] for row in rs]
        return (max(sum(w for w, h in row) + GAP * (len(row) - 1) for row in dims) + 2 * PAD,
                sum(max(h for w, h in row) for row in dims) + CHANNEL * (len(dims) - 1) + 2 * (PAD + EDGE) + (TITLE if s["label"] else 0))
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
        usable = width - GAP * max(0, len(roots) - 1)
        for s, share in zip(roots, shares):
            w = usable * share / sum(shares)
            pw, ph = min(w, float(s.get("max_width") or w)), min(height, float(s.get("max_height") or height))
            place(s, x, y + header + (height - ph) / 2, pw, ph, rows, measure, warnings, B)
            x += w + GAP
        y += h + LAYER_GAP
    for s in shapes:
        s["reference"] = True
        s["has_children"] = any(c.get("parent") == s["id"] for c in shapes)
    equalise(shapes)
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
    channel = min(CHANNEL, max(.04, inner_h / (4. * (len(rs) + 1))))
    edge = min(EDGE, channel)
    row_nat = [max(ch for cw, ch in row) for row in dims]
    avail_h = inner_h - channel * (len(rs) - 1) - 2 * edge
    if avail_h <= 0 or inner_w <= 0:
        raise B.BuildError("group %r cannot fit its contents on A3" % s["id"])
    heights = [avail_h * n / sum(row_nat) for n in row_nat]
    cy = y + padding + title + edge
    for row, sizes, rh in zip(rs, dims, heights):
        gap = min(GAP, inner_w * .02)
        usable = inner_w - gap * (len(row) - 1)
        total = sum(cw for cw, ch in sizes)
        if usable / total < .65 * DEVICE_W or rh < .65 * min(ch for cw, ch in sizes):
            warnings.append("group %r is crowded; increase its layer weight or reduce equipment" % s["id"])
        cx = x + padding
        for c, (cw, ch) in zip(row, sizes):
            cell_w = usable * cw / total
            place(c, cx, cy, cell_w, rh, rows, measure, warnings, B)
            cx += cell_w + gap
        cy += rh + channel


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
    for d in devices:
        by_key.setdefault(d.get("key"), []).append(d)
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
        explicit = c.get("individual") or c.get("via") or c.get("from_side") or c.get("to_side") or c.get("straight")
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
    tab_w = min(w - .24, max(1.7, min(3.15, .22 + len(label) * .11)))
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
