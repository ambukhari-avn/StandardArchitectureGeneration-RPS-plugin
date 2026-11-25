"""Reference layout: content-sized layers, nested equipment frames and shared links.

All geometry stays editable. This module never supplies cable colours.
"""
import math
from cable_labels import TYPICAL_LABEL
from textfit import fit_size, TextFitError, lines_needed
from draw import LABEL_ZONE, SUB_ZONE, visible_size, visible_box
from vsdx_writer import png_size

NAVY, BORDER = "#073878", "#27369B"
LIGHT_BLUE, BODY, CLIENT, ORANGE = "#E4F3FF", "#F5FAFF", "#FFE5B5", "#FF8800"
TAB_BLUE = "#001477"
GAP, PAD, TITLE = .12, .14, .30
LAYER_GAP = .16  # clear gap between consecutive layer frames
HEAD_W = .46     # width of the vertical navy heading strip on the left of every layer (same for all layers)
HEAD_W_DESC = .70  # strip width when any layer also shows a description line
HEAD_GAP = .14   # clearance between the heading strip and the equipment area
CHANNEL = .16    # clear band between device rows for cable routing
CABLE_GAP = .50  # band between rows that hold container boxes: a cable keeps ~7 mm from both borders
CABLE_GAP_X = .45  # side-by-side container boxes: room for a vertical cable with clearance
BAND = .36       # clear band above and below a row inside a container whose devices are linked past a neighbour
EDGE = .05       # clearance between the outer rows and the container border
DEVICE_W = 1.35  # relative width weight of one device: every device in a row gets an equal share
PIC_FLOOR = .25     # every picture area keeps at least this height (very wide equipment cannot collapse to its caption)
TIGHT_RATIO = .82   # below this share of comfortable size, margins shrink to their minimum
MIN_CHANNEL = .45  # a cable channel may shrink to this share of its comfortable width when equipment needs the room
MAX_CELL = 2.4   # widest cell a device gets in a row of equipment (keeps related equipment together)
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
    import qa                                                      # item 7: PLCs and remote I/O get visual priority in their row
    spec_ = qa.sizes().get(qa.category_of(s), qa.sizes()["default"])
    caption = LABEL_ZONE + (SUB_ZONE if s.get("sub") else 0)
    # The minimum displayed size is a requirement, not a weight: the picture area must be tall enough for the picture's longest
    # side to reach it (a tall PLC needs the full minimum in height, a wide server only minimum / aspect ratio).
    required = spec_["min"] / FILL * (1.0 if ar <= 1 else 1.0 / ar) * 1.08
    return caption + max(min(1.3, max(.55, 1.2 / math.sqrt(ar))) * spec_.get("weight", 1.0), required)


def required_height(s):
    """Height a device must get: caption plus the picture height that meets its category's minimum displayed size."""
    pic = s.get("pic")
    caption = LABEL_ZONE + (SUB_ZONE if s.get("sub") else 0)
    if not pic:
        return min(s["h"], caption + .35)
    try:
        l, t, r, b = visible_box(pic)
        iw, ih = png_size(pic)
        ar = (r - l) * iw / ((b - t) * ih)
    except Exception:
        return caption + .35
    import qa
    spec_ = qa.sizes().get(qa.category_of(s), qa.sizes()["default"])
    return caption + max(PIC_FLOOR, spec_["min"] / FILL * (1.0 if ar <= 1 else 1.0 / ar) * 1.25)


def two_tier(total, req, nat):
    """Two-tier allocation: every part first gets its required size, the rest of `total` goes by natural weight.
    If even the requirements do not fit, the parts shrink in proportion to their requirements (a defect is then reported)."""
    need = sum(req)
    if need <= 0:
        return [total * n / max(1e-9, sum(nat)) for n in nat]
    if need > total:
        return [total * r / need for r in req]
    extra = [max(0.0, n - r) for n, r in zip(nat, req)]
    pool = sum(extra)
    left = total - need
    return [r + (left * e / pool if pool > 0 else left / len(req)) for r, e in zip(req, extra)]


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


LABEL_ROOM = .34   # reserved under the I/O that receives a labelled representative hardwired connection


def order_row_constraints(rows_, group):
    """Item 3: relative placement constraints. A shape may say {"place": {"left_of": id}} or {"right_of": id} for a neighbour in the
    same container row; rows are reordered to satisfy them (stable otherwise). Conflicting constraints stop the build."""
    out = []
    for row in rows_:
        ids = [s["id"] for s in row]
        cons = []
        for s in row:
            p = s.get("place") or {}
            if p.get("left_of") in ids:
                cons.append((s["id"], p["left_of"]))
            if p.get("right_of") in ids:
                cons.append((p["right_of"], s["id"]))
        if not cons:
            out.append(row)
            continue
        order = list(ids)
        for _ in range(len(order) * len(order)):
            moved = False
            for a, b in cons:
                if order.index(a) > order.index(b):
                    order.remove(a)
                    order.insert(order.index(b), a)
                    moved = True
            if not moved:
                break
        else:
            raise PlacementError("placement constraints in %r conflict: %s" % (group["id"], cons))
        if any(order.index(a) > order.index(b) for a, b in cons):
            raise PlacementError("placement constraints in %r conflict: %s" % (group["id"], cons))
        by = {s["id"]: s for s in row}
        out.append([by[i] for i in order])
    return out


class PlacementError(Exception):
    pass


def bus_room(row):
    """Item 4/6: reserved corridors under a row: one trunk per network bus its devices hang on, and room for the label of a
    representative hardwired connection arriving at I/O in this row (so the label never has to sit on a layer border)."""
    n = max([len(_WIRED.get("buses", {}).get(s["id"], [])) for s in row] or [0])
    room = 0.0 if not n else .16 + .14 * (n - 1) + .16
    targets = _WIRED.get("hw_targets", set())
    if targets and any(_subtree(s) & targets for s in row):
        room += LABEL_ROOM
    return room


def vgap(upper, lower):
    """Band between two rows: wide where container borders face each other and a cable runs between them; rows joined by cables get
    a visible channel (a short link between neighbouring rows must not read as a stub); a bus corridor is added below bus members."""
    base = CABLE_GAP if any(map(isgroup, upper + lower)) and _linked(upper, lower) else \
        (BAND if _linked(upper, lower) else CHANNEL) if not any(map(isgroup, upper + lower)) else CABLE_GAP * .5
    return base + bus_room(upper)


def hgap(left, right):
    if not (isgroup(left) or isgroup(right)):
        label = _WIRED.get("labels", {}).get((left["id"], right["id"])) or _WIRED.get("labels", {}).get((right["id"], left["id"]))
        if label:                                                    # a labelled direct link (e.g. redundancy sync) between neighbours
            return max(GAP, max(len(x) for x in label.split("\n")) * .062 + .95)   # label plus room for cables crossing the link
        return GAP
    return CABLE_GAP_X if _linked([left], [right]) else CABLE_GAP_X * .5


def apply_layers(spec, shapes, warnings, B, boost=None):
    wanted = spec.get("layers")
    if wanted is None:
        if any(s.get("layer") or s.get("parent") for s in shapes):
            raise B.BuildError('shapes use "layer" but the file has no "layers" list')
        return []
    table = B.layer_table(spec)
    ids = [t["id"] for t in table]
    if not isinstance(wanted, list) or not wanted or any(w not in ids for w in wanted) or len(set(wanted)) != len(wanted):
        raise B.BuildError('"layers" must be a list of distinct layer ids (standard or custom_layers) from: %s' % ", ".join(ids))
    by_id = {s["id"]: s for s in shapes}
    _WIRED.update(pairs=[(str(c.get("from")), str(c.get("to"))) for c in spec.get("lines", []) if isinstance(c, dict)],
                  parent={s["id"]: s.get("parent") for s in shapes}, cache={},
                  labels={(str(c.get("from")), str(c.get("to"))): str(c["label"]) for c in spec.get("lines", [])
                          if isinstance(c, dict) and c.get("direct") and c.get("label")}, buses={})
    for b in spec.get("_buses", []):
        for m in b["members"]:
            _WIRED["buses"].setdefault(m, []).append(b["id"])

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
            # 7.4: Avanceon equipment sits directly in its layer (an invisible arrangement). Client/existing scope keeps a
            # visible box, and so do field instruments, whose representative hardwired connection needs a boundary.
            group["frame"] = layer == "field" or any(s.get("scope") == "other" for s in loose)
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
            if parent and parent["kind"] == "group" and parent.get("frame") is not False and \
                    {s["id"] for s in children if s["kind"] == "box"} == members == {s["id"] for s in children}:
                parent["solid"] = True          # a dedicated I/O container: one box for all its racks
            # 7.5: a rack among other equipment gets no box of its own; the representative cable ends at the rack itself.
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
    for g in [s for s in shapes if s["kind"] == "group" and not s.get("label") and not s.get("generated") and s.get("frame") is not False]:
        kids = [s for s in shapes if s.get("parent") == g["id"]]
        if len(kids) == 1 and kids[0]["kind"] == "group":
            warnings.append("group %r is an unlabeled box that only wraps group %r: remove it unless it marks a scope, panel, site or "
                            "security zone (use as few boxes as the drawing allows)" % (g["id"], kids[0]["id"]))
    _WIRED.update(parent={s["id"]: s.get("parent") for s in shapes}, cache={})   # generated groups now exist
    field = {s["id"] for s in shapes if s.get("layer") == "field"}                # layers are inherited by now
    _WIRED["hw_targets"] = {str(c.get(end)) for c in spec.get("lines", []) if isinstance(c, dict) and c.get("cable") == "hardwired"
                            for end in ("from", "to") if str(c.get(end)) not in field and str(c.get("to" if end == "from" else "from")) in field}
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
            out = [[s for s in members if (s.get("row") or 0) == i] for i in sorted({s.get("row") or 0 for s in members})]
            if (boost or {}).get("_compact") and len(out) > 1:
                # Over the page budget: functional rows are a placement preference (7.6), so they may share a row.
                import qa
                if all(x["kind"] == "box" for r_ in out for x in r_) and group.get("layer") != "control" and group.get("frame") is False:
                    out = [[x for r_ in out for x in r_]]                 # e.g. DMZ: server and firewall side by side
                elif all(qa.category_of(x) == "fo_panel" for x in out[0] if x["kind"] == "box") and all(x["kind"] == "box" for x in out[0]):
                    half = (len(out[0]) + 1) // 2                         # control: patch panels on the outer ends of the switch row,
                    out = [out[0][:half] + out[1] + out[0][half:]] + out[2:]  # so the switches stay above their PLCs
            return order_row_constraints(out, group)
        return order_row_constraints([members[i:i + cols] for i in range(0, len(members), cols)], group)
    def measure(s):
        if s["kind"] != "group":
            return DEVICE_W, natural_height(s)  # natural size is only a weight: it is never a maximum
        rs = rows(s)
        if not rs:
            return s["w"], .75  # a system summary box needs little height
        dims = [[measure(c) for c in row] for row in rs]
        width = max(sum(w for w, h in row) + sum(hgap(a, b) for a, b in zip(r, r[1:])) for row, r in zip(dims, rs))
        height = sum(max(h for w, h in row) for row in dims) + sum(vgap(a, b) for a, b in zip(rs, rs[1:])) + bus_room(rs[-1])
        return (width + 2 * PAD, height + 2 * (PAD + edge_for(rs)) + (TITLE if s["label"] else 0))
    def measure_req(s):
        if s["kind"] != "group":
            return DEVICE_W, required_height(s)
        rs = rows(s)
        if not rs:
            return s["w"], .75
        dims = [[measure_req(c) for c in row] for row in rs]
        width = max(sum(w for w, h in row) + sum(hgap(a, b) for a, b in zip(r, r[1:])) for row, r in zip(dims, rs))
        # minimum workable cable channels (place() caps channels at 45 % of the room; comfort space is shared out later)
        height = sum(max(h for w, h in row) for row in dims) + sum(MIN_CHANNEL * vgap(a, b) for a, b in zip(rs, rs[1:])) + bus_room(rs[-1])
        return (width + 2 * PAD, height + 2 * (PAD * .6 + edge_for(rs) * .5) + (TITLE if s["label"] else 0))
    measure.req = measure_req
    weights = spec.get("layer_weights", {})
    if not isinstance(weights, dict) or any(k not in wanted or B._num(v) is None or float(v) <= 0 for k, v in weights.items()):
        raise B.BuildError("layer_weights must map included layer ids to positive numbers")
    order = [t for t in table if t["id"] in wanted]
    natural, required = {}, {}
    for t in order:
        roots = [s for s in shapes if s.get("layer") == t["id"] and not s.get("parent")]
        # A layer's share follows what it must hold (rows of pictures, captions, titles), so large
        # pictures get room and blank space is not reserved for an arbitrary layer proportion.
        need = max([measure(s)[1] for s in roots] or [1.0]) + .32
        # 7.3: cables running in a layer need routing clearance too, so busy layers get extra height.
        layer_of = {x["id"]: x.get("layer") for x in shapes}
        ends = [(str(c.get("from")), str(c.get("to"))) for c in spec.get("lines", []) if isinstance(c, dict) and "from" in c]
        ends += [(a, b) for c in spec.get("lines", []) if isinstance(c, dict) and c.get("chain") for a, b in zip(c["chain"], c["chain"][1:])]
        busy = sum(1 for a, b in ends if t["id"] in (layer_of.get(a), layer_of.get(b)))
        need += min(.5, .03 * busy)
        natural[t["id"]] = float(weights.get(t["id"], max(need, .9))) * float((boost or {}).get(t["id"], 1.0))
        required[t["id"]] = max([measure_req(s)[1] for s in roots] or [.8]) + .10 + min(.2, .015 * busy)
    available = B.AREA_H - LAYER_GAP * (len(order) - 1)
    total = sum(natural.values())
    panels, y = [], 0.0
    options = spec.get("layer_headers", {})
    if not isinstance(options, dict):
        raise B.BuildError("layer_headers must be an object")
    any_desc = any(isinstance(options.get(t["id"]), dict) and options[t["id"]].get("description") for t in order)
    head_w = HEAD_W_DESC if any_desc else HEAD_W
    # Spare room beyond the requirements is shared by natural need, capped at 1.6x the requirement so one busy layer cannot
    # take it all; the correction boost then steers spare room (never requirements) towards layers that still fall short.
    explicit = weights and all(t["id"] in weights for t in order) and not boost
    plain = {t["id"]: available * natural[t["id"]] / total for t in order}
    if explicit and all(plain[t["id"]] >= required[t["id"]] for t in order):
        heights = plain                                              # the user's proportions, exactly, when they meet every minimum
    else:
        heights = dict(zip([t["id"] for t in order], two_tier(available, [required[t["id"]] for t in order],
                                                         [min(max(natural[t["id"]], required[t["id"]]), 1.6 * required[t["id"]] *
                                                              float((boost or {}).get(t["id"], 1.0))) for t in order])))
        if explicit:
            warnings.append("layer_weights adjusted so every layer meets its equipment minimum sizes")
    for t in order:
        h = heights[t["id"]]
        override = options.get(t["id"], {})
        if not isinstance(override, dict):
            raise B.BuildError("each layer_headers entry must be an object")
        default_name = "Control System" if t["id"] == "control" else t["name"]
        p = dict(t, x=0., y=y, w=B.AREA_W, h=h, reference=True, head_w=head_w,
                 name=str(override.get("name", default_name)), desc=str(override.get("description", "")))
        panels.append(p)
        roots = [s for s in shapes if s.get("layer") == t["id"] and not s.get("parent")]
        side = [s for s in roots if s.get("placement") == "beside"]
        if side and t["id"] != "control":
            raise B.BuildError('placement="beside" is for a requested panel in the control layer')
        roots = [s for s in roots if s not in side] + side
        # The heading is a vertical navy strip on the left of the layer (7.2); the equipment
        # area starts to its right and uses the full layer height.
        x = head_w + HEAD_GAP
        header = min(PAD, h * .08)
        bottom_pad = min(PAD, h * .08)
        width, height = B.AREA_W - x - PAD, h - header - bottom_pad
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
    dims = [[measure(c) for c in row] for row in rs]
    edge = min(edge_for(rs), (h - 2 * padding - title) / 6.)
    if hasattr(measure, "req") and h < measure.req(s)[1] / TIGHT_RATIO:
        padding, edge = min(padding, PAD * .6), min(edge, edge_for(rs) * .5)   # equipment minimums come before comfortable margins
    inner_w, inner_h = w - 2 * padding, h - 2 * padding - title
    row_nat = [max(ch for cw, ch in row) for row in dims]
    channels = [vgap(a, b) for a, b in zip(rs, rs[1:])]
    room = inner_h - 2 * edge - bus_room(rs[-1])                    # the bus corridor under the last row is kept clear
    if sum(channels) > .45 * room:                                  # never let the channels crowd the equipment out
        channels = [c * .45 * room / sum(channels) for c in channels]
    row_need = sum(max(measure.req(c)[1] for c in row) for row in rs) if hasattr(measure, "req") else 0
    if row_need and room - sum(channels) < row_need:                # equipment minimums come before comfortable channels
        floor = [MIN_CHANNEL * c for c in channels]
        spare = max(0.0, room - row_need - sum(floor))
        channels = [f + min(c - f, spare * (c - f) / max(1e-9, sum(channels) - sum(floor))) for c, f in zip(channels, floor)]
    avail_h = room - sum(channels)
    if avail_h <= 0 or inner_w <= 0:
        raise B.BuildError("group %r cannot fit its contents on A3" % s["id"])
    row_req = [max((measure.req(c)[1] if hasattr(measure, "req") else ch) for c, (cw, ch) in zip(row, dr)) for row, dr in zip(rs, dims)]
    heights = two_tier(avail_h, row_req, [max(n, r) for n, r in zip(row_nat, row_req)])
    cy = y + padding + title + edge
    for r, (row, sizes, rh) in enumerate(zip(rs, dims, heights)):
        gaps = [hgap(a, b) for a, b in zip(row, row[1:])]
        if sum(gaps) > .3 * inner_w:
            gaps = [g * .3 * inner_w / sum(gaps) for g in gaps]
        usable = inner_w - sum(gaps)
        total = sum(cw for cw, ch in sizes)
        if usable / total < .55 * DEVICE_W or rh < .5 * min(ch for cw, ch in sizes):
            warnings.append("group %r is crowded; increase its layer weight or reduce equipment" % s["id"])
        cells = [usable * cw / total for cw, ch in sizes]
        if all(c["kind"] != "group" for c in row):
            # A row of equipment stays compact and centred instead of being stretched across the page, so related
            # equipment (a redundant PLC pair, its switches) sits together and cables stay short.
            cells = [min(cw, MAX_CELL) for cw in cells]
        cx = x + padding + (usable - sum(cells)) / 2
        for k, (c, cell_w) in enumerate(zip(row, cells)):
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
    def visible(g):
        return g.get("frame") is not False
    def boundary(s, other):
        # Keep internal wiring inside the shared container. Across containers,
        # promote endpoints to the outside VISIBLE box so cables do not traverse pictures;
        # invisible arrangements are never an endpoint (a cable must end on something drawn).
        if s["kind"] == "group":
            return s  # an explicit box endpoint is already the intended boundary
        other_parents = ancestors(other)
        best, cur = s, s
        while cur.get("parent") and cur["parent"] not in other_parents:
            cur = by_id[cur["parent"]]
            if visible(cur):
                best = cur
        return best
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
        top, cur = source, source
        while cur.get("parent"):
            cur = by_id[cur["parent"]]
            if visible(cur):
                top = cur
        source = top
        if target["kind"] != "group" and target.get("parent") and visible(by_id[target["parent"]]) and by_id[target["parent"]].get("solid"):
            target = by_id[target["parent"]]    # the common I/O box; never a PLC system or panel box (8.7: end at the I/O)
        key = (source["id"], target["id"], c["cable"])
        if key not in shared:
            displayed = dict(c, a=key[0], b=key[1], source_connections=[], representative=True, label=TYPICAL_LABEL)
            shared[key] = displayed
            out.append(displayed)
        shared[key]["source_connections"].append((c["a"], c["b"]))
    return out


HEAD_SIZES = (14, 13, 12, 11, 10, 9, 8, 7, 6.5)


def heading_text(label, length, across):
    """Largest size at which the heading fits the strip on one line; otherwise two lines split at a word boundary
    (written with an explicit line break so Visio and the preview agree). Returns (text, size) or (label, None)."""
    for size in HEAD_SIZES:
        if lines_needed(label, length, size, True) == 1 and size * 1.2 / 72 <= across + .01:
            return label, size
    words = label.split()
    for size in HEAD_SIZES:
        if 2 * size * 1.2 / 72 > across + .01:
            continue
        for i in range(1, len(words)):
            a, b = " ".join(words[:i]), " ".join(words[i:])
            if lines_needed(a, length, size, True) == 1 and lines_needed(b, length, size, True) == 1:
                return a + "\n" + b, size
    return label, None


def draw_layer(page, p, B):
    """One layer: a light frame with a vertical navy heading strip along its left side (7.2). The layer name is turned
    90 degrees (reading upwards) and fitted inside the strip; the strip has the same width in every layer and stays
    inside the frame, clear of equipment and cables."""
    x, y, w, h = B.MARGIN + p["x"], B.TOP - p["y"] - p["h"], p["w"], p["h"]
    page.rect("zone", x, y, w, h, fill=BODY, line=BORDER, lw=1.5, rounding=.04, key="layer:" + p["id"])
    hw = p.get("head_w", HEAD_W)
    inset = .05
    sx, sy, sh = x + inset, y + inset, h - 2 * inset
    page.rect("zone", sx, sy, hw - inset, sh, fill=TAB_BLUE, line=TAB_BLUE, lw=1.0, rounding=.06, key="layer-heading:" + p["id"])
    label = p["name"]
    name_w = (hw - inset) if not p.get("desc") else (hw - inset) * .58
    if p.get("desc") or hw > HEAD_W:                              # two text columns: name, then the smaller description
        name_w = (hw - inset) * .58
    length = sh - .16
    label, size = heading_text(label, length, name_w - .06)
    if size is None:
        raise B.BuildError("layer name %r does not fit its heading strip; shorten it or give the layer more height (layer_weights)" % p["name"])
    # A text block turned 90 degrees: its own width runs along the strip (length), its height across it.
    page.text(sx + .03, sy + .08, name_w - .06, length, label, size=size, bold=True, color="#FFFFFF",
              text_angle=90, key="layer-name:" + p["id"])
    if p.get("desc"):
        dw = hw - inset - name_w
        try:
            dsize = fit_size(p["desc"], length, dw - .04, (9, 8, 7, 6.5, 6), False)
        except TextFitError:
            raise B.BuildError("layer description %r does not fit its heading strip; shorten it" % p["desc"])
        page.text(sx + name_w, sy + .08, dw - .04, length, p["desc"], size=dsize, color="#DCE8FF",
                  text_angle=90, key="layer-desc:" + p["id"])
    return size
