"""Meaning-based spec (spec_version 2) -> the free-form spec that build_diagram.py draws.   Standard library only.

The AI describes what exists, where it belongs and how it connects (items, levels, scope, links, ring, redundancy, assumptions). It writes
no coordinates. This module checks that description (validate), refuses what cannot be drawn or must be asked first, and places everything
(compile_v2). The result is an ordinary free-form spec, so the one drawing path (prepare / route / write_vsdx) is unchanged.

    validate(spec)                              -> (errors, questions, warnings)
    compile_v2(spec, comps, cables, spec_dir)   -> free-form spec (shapes + lines), with the build report under "_report"
"""
import json
import math
import os
import re
from collections import defaultdict

import levels
from cables import Cables
from components import Components
from draw import LABEL_ZONE
from vsdx_writer import png_size

HINTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "level_hints.json")
KINDS = ("instrument", "controller", "rio", "workstation", "server", "switch", "patch_panel", "firewall", "other")
KIND_LEVEL = {"instrument": "L0", "controller": "L1", "rio": "L1", "workstation": "L2"}      # the level a kind normally lives on
KIND_DEFAULT = {"server": "rack_server", "workstation": "client_operator_workstation", "firewall": "industrial_firewall"}   # generic library pictures, used only when the item names no component and no picture of its own (decision D57)
APPROVED = {"switch": "network_switch_approved", "patch_panel": "fo_patch_panel"}     # kinds that always use the approved library symbol (task 9)
MAX_EXPANDED = 12                                  # qty up to this draws that many items; more draws one item labelled "x N" (decision F)


class SpecError(ValueError):
    """The spec cannot be built. `errors` are mistakes to fix; `questions` are for the user and must be asked before building."""

    def __init__(self, errors=(), questions=()):
        self.errors, self.questions = list(errors), list(questions)
        parts = []
        if self.errors:
            parts.append("cannot draw this spec:\n  - " + "\n  - ".join(self.errors))
        if self.questions:
            parts.append("questions for the user:\n" + "\n".join("  %d. %s" % (i, q) for i, q in enumerate(self.questions, 1)))
        super().__init__("\n".join(parts))


def _s(v):
    return v.strip() if isinstance(v, str) else ""


def _hint_patterns(path=HINTS):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for level, words in raw.items():
        if level.startswith("_"):
            continue
        out[level] = [re.compile((r"\b%s(s)?\b" if len(w) <= 4 else r"\b%s") % re.escape(w), re.I) for w in words]
    return out


def looks_like(item, patterns):
    """Levels an item looks like it belongs to, from its label and kind (empty when nothing matches)."""
    text = "%s %s" % (_s(item.get("label")), _s(item.get("kind")))
    found = {level for level, pats in patterns.items() if any(p.search(text) for p in pats)}
    if item.get("kind") in KIND_LEVEL:
        found.add(KIND_LEVEL[item["kind"]])
    return found


def validate(spec, comps=None, cables=None):
    """(errors, questions, warnings) for a v2 spec. Errors stop the build; questions stop it too and go to the user; warnings are reported."""
    errors, questions, warnings = [], [], []
    if not isinstance(spec, dict):
        return ["the file must be a JSON object"], questions, warnings
    if spec.get("spec_version") != 2:
        errors.append('"spec_version" must be 2')
    items = spec.get("items")
    if not isinstance(items, list) or not items:
        errors.append('"items" must be a non-empty list')
        return errors, questions, warnings
    comps, cables, patterns = comps or Components(), cables or Cables(), _hint_patterns()
    ids, by_id = set(), {}
    for n, it in enumerate(items, 1):
        if not isinstance(it, dict):
            errors.append("item %d: not an object" % n)
            continue
        iid = _s(it.get("id"))
        name = "item %r" % (iid or n)
        if not iid:
            errors.append("%s: every item needs an id" % name)
            continue
        if iid in ids:
            errors.append("%s: duplicate item id" % name)
            continue
        ids.add(iid)
        by_id[iid] = it
        label = _s(it.get("label"))
        if it.get("kind") in APPROVED:
            sym = APPROVED[it["kind"]]
            if sym not in comps.by_id:
                errors.append("%s: the approved symbol %r is missing from the library (data/components_extra.json)" % (name, sym))
            elif not label:
                label = comps.get(sym)["label"]
        elif it.get("component") is not None:
            if it["component"] not in comps.by_id:
                errors.append("%s: component %r is not in the library (run scripts/find_component.py)" % (name, it["component"]))
            elif not label:
                label = comps.get(it["component"])["label"]
        if not label:
            errors.append("%s: needs a label" % name)
        qty = it.get("qty", 1)
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            errors.append("%s: qty must be a whole number of 1 or more, not %r" % (name, qty))
        if it.get("kind") is not None and it["kind"] not in KINDS:
            warnings.append("%s: kind %r is not one of %s; treated as other" % (name, it["kind"], ", ".join(KINDS)))
        if it.get("image_match") not in (None, "exact", "generic"):
            warnings.append('%s: image_match must be "exact" or "generic"' % name)
        lv = it.get("level")
        if lv in (None, ""):
            questions.append("Which Purdue level (%s) does %s belong to?" % (", ".join(levels.LEVEL_IDS), label or iid))
        elif lv not in levels.LEVEL_IDS:
            errors.append("%s: unknown level %r (use %s)" % (name, lv, ", ".join(levels.LEVEL_IDS)))
        try:
            levels.check_scope(dict(it, label=label or iid))
        except levels.ScopeQuestion as q:
            questions.append(q.question)
        if it.get("kind") in APPROVED and (it.get("image") or it.get("component")):
            warnings.append("%s: %s is ignored; switches and patch panels always use the approved symbol" % (
                name, "image" if it.get("image") else "component"))
        if it.get("kind") not in APPROVED and it.get("component") in comps.by_id and it.get("image"):
            try:
                has_pic = comps.picture_path(it["component"]) is not None
            except FileNotFoundError:
                has_pic = False
            if has_pic:
                warnings.append("%s: the library picture of %r is used; the image given is ignored (library pictures always win)" % (name, it["component"]))
        if it.get("kind") == "patch_panel" and not it.get("near") and not it.get("generated"):
            warnings.append("%s: a patch panel is placed beside the item it serves; add \"near\": <that item's id>" % name)
        if lv in levels.LEVEL_IDS and not it.get("generated"):
            found = looks_like(dict(it, label=label), patterns)
            if found and lv not in found:
                warnings.append("%s (%s) is on %s but looks like a %s item; check its level" % (
                    name, label, lv, "/".join(l for l in levels.LEVEL_IDS if l in found)))
    for iid, it in by_id.items():
        for key in ("group", "near"):
            if it.get(key) is not None and it[key] not in ids:
                errors.append("item %r: %s %r is not an item id" % (iid, key, it[key]))

    def known(ref, where, what="item id"):
        if ref not in ids:
            errors.append("%s: %r is not an %s" % (where, ref, what))
            return False
        return True

    links = spec.get("links", [])
    if not isinstance(links, list):
        errors.append('"links" must be a list')
        links = []
    for n, lk in enumerate(links, 1):
        where = "link %d" % n
        if not isinstance(lk, dict):
            errors.append("%s: not an object" % where)
            continue
        a, b = known(lk.get("from"), where + " from"), known(lk.get("to"), where + " to")
        if a and b and lk["from"] == lk["to"]:
            errors.append("%s: from and to are the same item" % where)
        if lk.get("cable") not in cables.by_id:
            errors.append("%s: cable %r is not one of %s" % (where, lk.get("cable"), ", ".join(sorted(cables.by_id))))
        if lk.get("label") is not None and not isinstance(lk["label"], str):
            errors.append("%s: label must be text" % where)

    red = spec.get("redundancy", [])
    if not isinstance(red, list):
        errors.append('"redundancy" must be a list')
        red = []
    for n, r in enumerate(red, 1):
        where = "redundancy %d" % n
        if not isinstance(r, dict):
            errors.append("%s: not an object" % where)
            continue
        a, b = known(r.get("primary"), where + " primary"), known(r.get("secondary"), where + " secondary")
        if a and b:
            if r["primary"] == r["secondary"]:
                errors.append("%s: primary and secondary are the same item" % where)
            else:
                pa, sb = by_id[r["primary"]], by_id[r["secondary"]]
                if pa.get("qty", 1) != 1 or sb.get("qty", 1) != 1:
                    errors.append("%s: a redundant pair is two single items (qty 1)" % where)
                if pa.get("level") != sb.get("level") or _s(pa.get("scope")).lower() != _s(sb.get("scope")).lower():
                    errors.append("%s: primary and secondary must be on the same level and in the same scope" % where)
        if r.get("cable", "ethernet") not in cables.by_id:
            errors.append("%s: cable %r is not one of %s" % (where, r.get("cable"), ", ".join(sorted(cables.by_id))))
        n_links = r.get("links", 2)
        if isinstance(n_links, bool) or not isinstance(n_links, int) or n_links < 1:
            errors.append("%s: links must be a whole number of 1 or more" % where)
        elif n_links != 2:
            warnings.append("%s: %d redundancy link(s); the document shows two" % (where, n_links))

    rings = spec.get("rings", [])
    if not isinstance(rings, list):
        errors.append('"rings" must be a list')
        rings = []
    for n, rg in enumerate(rings, 1):
        where = "ring %d" % n
        if not isinstance(rg, dict):
            errors.append("%s: not an object" % where)
            continue
        members = rg.get("members")
        if not isinstance(members, list) or len(members) < 2:
            errors.append("%s: a ring needs at least 2 members besides the first node" % where)
            members = members if isinstance(members, list) else []
        nodes = [rg.get("first")] + list(members)
        ok = [known(x, where) for x in nodes]
        if all(ok):
            if len(set(nodes)) != len(nodes):
                errors.append("%s: the first node and the members must all be different items" % where)
            if any(by_id[x].get("qty", 1) != 1 for x in nodes):
                errors.append("%s: every ring node is a single item (qty 1); list each RIO as its own item" % where)
            if len({by_id[x].get("level") for x in nodes}) > 1:
                errors.append("%s: the first node and the members must be on the same level" % where)
            if len({_s(by_id[x].get("scope")).lower() for x in nodes}) > 1:
                errors.append("%s: the first node and the members must be in the same scope (one ring is drawn in one scope box)" % where)
            for node, pair in (rg.get("switches") or {}).items():
                if node not in nodes or not isinstance(pair, list) or len(pair) != 2 or not all(p in ids for p in pair):
                    errors.append("%s: switches must map a ring node to the ids of its two ring switches" % where)
                elif any(by_id[p].get("qty", 1) != 1 or by_id[p].get("level") != by_id[node].get("level") for p in pair):
                    errors.append("%s: the ring switches of %r must be two single items on the same level as it" % (where, node))
        rid = _s(rg.get("id")) or "ring%d" % n
        if "ring_" + rid in ids:
            errors.append("%s: the id %r collides with an item id (ring_%s)" % (where, rid, rid))
        if "fibre" not in cables.by_id:
            errors.append("%s: the cable table has no 'fibre' cable for the ring" % where)
    if len(rings) > 1:
        warnings.append("%d rings: each is drawn as its own block in the same band" % len(rings))

    switch_groups = {}
    for it in by_id.values():
        if it.get("kind") == "switch" and not it.get("generated"):
            switch_groups.setdefault(it.get("level"), []).append(it)
    ring_switches = {p for rg in rings if isinstance(rg, dict) and isinstance(rg.get("switches"), dict)
                     for pair in rg["switches"].values() if isinstance(pair, list) for p in pair}
    for lv, group in switch_groups.items():
        group = [g for g in group if g.get("id") not in ring_switches]
        if len(group) == 1 and group[0].get("qty", 1) == 1:
            warnings.append("only one switch on %s (%s); the document default is two" % (lv, _s(group[0].get("label")) or group[0].get("id")))

    levels.header_colours(spec, warnings)
    for key in ("notes", "assumptions"):
        if spec.get(key) is not None and not (isinstance(spec[key], list) and all(isinstance(x, str) for x in spec[key])):
            warnings.append('"%s" must be a list of text; ignored' % key)
    qs = spec.get("questions", [])
    if isinstance(qs, list):
        questions += [str(q) for q in qs if str(q).strip()]
    elif qs:
        questions.append(str(qs))
    return errors, questions, warnings


# ================================================================================================================================
# Placement. Coordinates below are inches from the top-left of the drawing area (y grows downwards), like the free-form format.
# ================================================================================================================================
PICTURE, BOX = (1.00, 0.95), (1.35, 0.55)               # item sizes at scale 1.0 (the free-form defaults)
SCALES = (1.0, 0.8, 0.65)                                # item size steps when the page is too full; the font never goes below 6 pt
GAP, RED_GAP, ROW_GAP, BAND_GAP = 0.35, 1.15, 0.18, 0.30  # between items / between a redundant pair / between rows / between bands
BAND_PAD_X, SCOPE_PAD_X, SCOPE_GAP = 0.15, 0.12, 0.20
TOP_PAD, CAPTION_H, BOTTOM_PAD = 0.08, 0.20, 0.12       # band: header, then this padding, then the scope-box caption, then the rows
SCOPE_BOTTOM_MARGIN = 0.04                               # the scope boxes stop this far above the band's lower edge (so they clear the last row)
LANE = 0.08                                              # one routing lane (a horizontal line between rows)
SPREAD_MAX = 2.8                                         # widest pitch between items that have nothing to hang under
ELLIPSE_H = 0.55                                         # the ring ellipse is this tall (inches at scale 1.0)
RING_MARGIN, RING_SW_GAP, RING_PITCH, RING_END_INSET = 0.8, 0.30, 3.0, 0.7   # ellipse overhang / space between a pair of switches / member pitch / main switches inset
SLOT_PITCH = 0.13                                        # attachment points: wanted spacing; they never fan out wider than the shape itself
LABEL_ONCE = 4                                           # a link that expands to more lines than this is labelled on its first line only
MAX_EXTRA_GAP = 0.9                                      # most spare height added to one gap between bands


class TooLarge(SpecError):
    """Everything listed does not fit one A3 page, even at the smallest item size."""

    def __init__(self):
        msg = 'too large for one A3 page; ask the user to split it or use "x N" counts'
        super().__init__([msg])
        self.args = (msg,)


class Node:
    """One drawn item (a `qty` of 3 makes three nodes)."""

    def __init__(self, **kw):
        self.tier, self.want, self.partner, self.near_node, self.generated = None, None, None, None, False
        self.assumed, self.ring, self.ring_role, self.slot0 = False, None, None, None
        self.__dict__.update(kw)
        self.slot0 = self.slot0 or self.w0

    def scale(self, s):
        self.w, self.h, self.slot = self.w0 * s, self.h0 * s, self.slot0 * s
        if self.pic:
            area_h = self.h - LABEL_ZONE
            self.pw = min(self.w, area_h * self.aspect)
            self.ph = self.pw / self.aspect
        else:
            self.pw, self.ph, area_h = self.w, self.h, self.h
        self.pic_dy = (area_h - self.ph) / 2 if self.pic else 0.0          # picture top below the cell top
        self.mid_dy = self.pic_dy + self.ph / 2                            # centre of the picture (or box) below the cell top


class Ring:
    """A closed fibre ring: the main node first, then the members in order, and back to the main node (task 8). The geometry (cx, a, cy, b:
    centre and half-axes of the ellipse, inches) is filled in by the layout."""

    def __init__(self, rid, label, first, members, switches, src):
        self.id, self.label, self.first, self.members, self.sw, self.src = rid, label, first, members, switches, src
        self.shape_id = "ring_" + rid
        self.cx = self.cy = self.a = self.b = self.row = None

    def switches(self):
        return [s for node in [self.first] + self.members for s in self.sw[node]]


class Link:
    def __init__(self, a, b, cable, label=None, assumed=False, src=None):
        self.a, self.b, self.cable, self.label, self.assumed, self.src = a, b, cable, label, assumed, src
        self.kind, self.lane, self.xf, self.explicit, self.slots = None, {}, None, None, {}


class Row:
    def __init__(self, band, tier, sub, kind="nodes"):
        self.band, self.tier, self.sub, self.kind = band, tier, sub, kind
        self.nodes, self.h, self.y, self.gi, self.ri, self.ring = [], 0.0, 0.0, 0, 0, None


class Band:
    def __init__(self, level, nodes):
        self.level, self.nodes, self.rows, self.col_x = level, nodes, [], {}
        self.cols = [sc for sc in ("avanceon", "other") if any(n.scope == sc for n in nodes)]
        self.ellipse_tiers = {}                     # tier -> ring: the row that holds a ring's ellipse (task 8)
        self.rings = []
        self.y = self.h = 0.0


def place_1d(desired, widths, gaps, lo, hi):
    """Centres left to right: each as close to its desired x as the bounds and the no-overlap rule allow. Items that collide form a
    cluster that is re-centred on the mean of its members' wishes, so a family of items hangs centred under its parent.
    gaps[i] is the clear space between item i-1 and item i."""
    n = len(desired)
    clusters = [[i] for i in range(n)]

    def geometry(idxs):
        offs, pos = [], 0.0
        for j, i in enumerate(idxs):
            if j:
                pos += gaps[i]
            offs.append(pos + widths[i] / 2)
            pos += widths[i]
        left = sum(desired[i] - o for i, o in zip(idxs, offs)) / len(idxs)
        return min(max(left, lo), max(lo, hi - pos)), offs, pos

    while True:
        geo = [geometry(c) for c in clusters]
        for k in range(len(clusters) - 1):
            if geo[k][0] + geo[k][2] + gaps[clusters[k + 1][0]] > geo[k + 1][0] + 1e-9:
                clusters[k:k + 2] = [clusters[k] + clusters[k + 1]]
                break
        else:
            break
    out = [0.0] * n
    for c, (left, offs, _) in zip(clusters, geo):
        for i, o in zip(c, offs):
            out[i] = left + o
    return out


def gap_between(a, b, s):
    return (RED_GAP if (a.partner is b or b.partner is a) else GAP) * s


def order_nodes(nodes, members_cx, nbr_up):
    """(ordered nodes, {node: desired x or None}). Input order, but a redundant partner or a `near` item follows its anchor, and items
    that hang under a parent (`group`, or for level 0 a link to a higher level) are sorted by where that parent is."""
    want = {}
    for n in nodes:
        w = n.want() if n.want else None
        if w is None and n.group:
            xs = [m.cx for m in members_cx.get(n.group, []) if getattr(m, "cx", None) is not None]
            w = sum(xs) / len(xs) if xs else None
        if w is None and n.level == "L0":
            xs = [m.cx for m in nbr_up.get(n, []) if getattr(m, "cx", None) is not None]
            w = sum(xs) / len(xs) if xs else None
        want[n] = w
    present = set(nodes)

    def anchor(n):
        seen = 0
        while seen < 10:
            a = n.partner if (n.partner is not None and n.is_secondary) else n.near_node
            if a is None or a not in present or a is n:
                return n
            n, seen = a, seen + 1
        return n

    roots = sorted({anchor(n) for n in nodes}, key=lambda r: r.idx)
    vals = [want[r] for r in roots]
    if any(v is not None for v in vals):                   # fill the gaps from the neighbours so those items stay beside them
        prev = None
        for i, v in enumerate(vals):
            if v is None and prev is not None:
                vals[i] = prev + 1e-3
            prev = vals[i] if vals[i] is not None else prev
        nxt = None
        for i in range(len(vals) - 1, -1, -1):
            if vals[i] is None and nxt is not None:
                vals[i] = nxt - 1e-3
            nxt = vals[i] if vals[i] is not None else nxt
        rank = dict(zip(roots, vals))
        key = lambda n: (rank[anchor(n)], anchor(n).idx, n is not anchor(n), n.idx)
    else:
        rank = None
        key = lambda n: (anchor(n).idx, n is not anchor(n), n.idx)
    ordered = sorted(nodes, key=key)
    if rank is None:
        return ordered, {n: None for n in ordered}
    return ordered, {n: (rank[anchor(n)] if n is anchor(n) or want[n] is None else want[n]) for n in ordered}


def chunk_rows(nodes, gaps, inner):
    """Split an ordered list into the fewest rows that fit `inner` inches, then spread the items evenly over those rows."""
    rows, cur = 1, 0.0
    for i, n in enumerate(nodes):
        need = n.slot + (gaps[i] if cur else 0.0)
        if cur and cur + need > inner + 1e-9:
            rows, cur = rows + 1, n.slot
        else:
            cur += need
    per = max(1, math.ceil(len(nodes) / rows))
    return [nodes[i:i + per] for i in range(0, len(nodes), per)]


class Layout:
    """Everything placed for one item scale: bands, scope columns, rows, node positions, routed links."""

    def __init__(self, nodes, links, s, area_w, area_h, members, rings=()):
        self.nodes, self.links, self.s, self.area_w, self.area_h, self.members = nodes, links, s, area_w, area_h, members
        self.rings = list(rings)
        self.bands, self.rows = [], []
        self.gap_geom, self.lanes = {}, defaultdict(list)
        self.total_h, self.extra = 0.0, 0.0
        for n in nodes:
            n.scale(s)
            n.cx = None
        self.nbr_up = defaultdict(list)

    # ---- x: bands, scope columns, rows ---------------------------------------------------------------------------------------
    def make_bands(self):
        for lv in levels.order({n.level for n in self.nodes}):
            bn = [n for n in self.nodes if n.level == lv]
            self.bands.append(Band(lv, bn))
        for bi, b in enumerate(self.bands):
            b.index = bi
            for n in b.nodes:
                n.band = b
        for r in self.rings:
            r.cx = r.cy = r.a = r.b = r.row = None
            r.first.band.rings.append(r)
        for lk in self.links:                                   # neighbours in a higher band, for the level-0 ordering
            for x, y in ((lk.a, lk.b), (lk.b, lk.a)):
                if levels.LEVEL_IDS.index(y.level) < levels.LEVEL_IDS.index(x.level):
                    self.nbr_up[x].append(y)

    def assign_tiers(self, b):
        base = [n for n in b.nodes if n.tier is None and n.ring is None]          # ring nodes are placed by place_ring
        has_other = any(n.kind != "switch" for n in base)
        for n in base:
            n.tier = 1 if (n.kind == "switch" and has_other) else 0       # switches sit on the band's lower tier, under what they serve
        for n in base:
            if n.near_node is not None and n.near_node.band is b and n.near_node.tier is not None:
                n.tier = n.near_node.tier

    def columns(self, b):
        n_by = {c: sum(1 for n in b.nodes if n.scope == c) for c in b.cols}
        avail = self.area_w - levels.STRIP_W - 2 * BAND_PAD_X - (len(b.cols) - 1) * SCOPE_GAP * self.s
        min_w = max(n.slot for n in b.nodes) + 2 * SCOPE_PAD_X
        total = sum(n_by.values())
        widths = {c: avail * n_by[c] / total for c in b.cols}
        low = [c for c in b.cols if widths[c] < min_w]
        if low and len(low) < len(b.cols):
            rest = [c for c in b.cols if c not in low]
            left = avail - min_w * len(low)
            for c in low:
                widths[c] = min_w
            for c in rest:
                widths[c] = left * n_by[c] / sum(n_by[r] for r in rest)
        x = levels.STRIP_W + BAND_PAD_X
        for c in b.cols:
            b.col_x[c] = (x, x + widths[c])
            x += widths[c] + SCOPE_GAP * self.s

    def place_band(self, b):
        self.assign_tiers(b)
        self.columns(b)
        plain = [n for n in b.nodes if n.ring is None]
        tiers = sorted({n.tier for n in plain})
        rows = {}
        for t in tiers:
            per_col = {}
            for c in b.cols:
                nodes_tc = [n for n in plain if n.tier == t and n.scope == c]
                if nodes_tc:
                    per_col[c] = nodes_tc
            for c, nodes_tc in per_col.items():
                lo, hi = b.col_x[c][0] + SCOPE_PAD_X, b.col_x[c][1] - SCOPE_PAD_X
                ordered, desired = order_nodes(nodes_tc, self.members, self.nbr_up)
                gaps = [0.0] + [gap_between(ordered[i - 1], ordered[i], self.s) for i in range(1, len(ordered))]
                chunks = chunk_rows(ordered, gaps, hi - lo)
                for k, ch in enumerate(chunks):
                    row = rows.setdefault((t, k), Row(b, t, k))
                    g = [0.0] + [gap_between(ch[i - 1], ch[i], self.s) for i in range(1, len(ch))]
                    widths = [n.slot for n in ch]
                    if all(desired[n] is None for n in ch):             # nothing to hang under: spread around the middle of the column
                        pitch = max(max(widths) + GAP * self.s, min((hi - lo) / len(ch), SPREAD_MAX * self.s ** 0.5))
                        mid = (lo + hi) / 2
                        off = [0.0]                                      # an item marked `near` another sits right beside it, not a full pitch away
                        for j in range(1, len(ch)):
                            beside = ch[j].near_node is not None and (ch[j].near_node is ch[j - 1] or ch[j - 1].near_node is ch[j].near_node)
                            off.append(off[-1] + ((widths[j - 1] + widths[j]) / 2 + GAP * self.s if beside else pitch))
                        des = [mid + o - off[-1] / 2 for o in off]
                    else:
                        step = (max(widths) + GAP * self.s) / 2 if len(chunks) > 1 and k % 2 else 0.0   # stagger the second row
                        base = [desired[n] if desired[n] is not None else None for n in ch]
                        fill = [v for v in base if v is not None]
                        des = [(v if v is not None else fill[0]) + step for v in base]
                    xs = place_1d(des, widths, g, lo, hi)
                    for n, x in zip(ch, xs):
                        n.cx, n.row = x, row
                        row.nodes.append(n)
        next_tier = (tiers[-1] + 1) if tiers else 0
        for ring in b.rings:                                     # each ring is a block of four rows below the ordinary items of the band
            next_tier = self.place_ring(b, ring, rows, next_tier)
        for t, ring in b.ellipse_tiers.items():
            r = Row(b, t, 0, "ellipse")
            r.ring = ring
            ring.row = r
            rows[(t, 0)] = r
        b.rows = [rows[k] for k in sorted(rows)]
        for r in b.rows:
            r.nodes.sort(key=lambda n: n.cx)

    def place_ring(self, b, ring, rows, t0):
        """Four rows, top to bottom: (a) the main node with its two ring switches, (b) the ellipse, (c) the switches of every member,
        (d) the members themselves. The members are spread evenly; the ellipse is as wide as the switches of the outer members plus a
        margin, and the main node's switches sit near its two ends so the loop visibly closes on both sides. Returns the next free tier."""
        s = self.s
        lo, hi = b.col_x[ring.first.scope][0] + SCOPE_PAD_X, b.col_x[ring.first.scope][1] - SCOPE_PAD_X
        margin, mods = RING_MARGIN * s, ring.members
        sw_w = max(n.slot for n in ring.switches())
        pair_w = 2 * sw_w + RING_SW_GAP * s
        unit = max([m.slot for m in mods] + [pair_w])
        n = len(mods)
        avail = (hi - lo) - 2 * margin
        pitch = min((avail - unit) / (n - 1), RING_PITCH * s) if n > 1 else RING_PITCH * s
        if unit + GAP * s > pitch + 1e-9 or unit > avail + 1e-9:
            raise TooLarge()
        mid = (lo + hi) / 2
        d = (sw_w + RING_SW_GAP * s) / 2                        # a member's two switches sit this far either side of its centre
        mrow, srow, arow = Row(b, t0 + 3, 0), Row(b, t0 + 2, 0), Row(b, t0, 0)
        for i, m in enumerate(mods):
            x = mid + (i - (n - 1) / 2) * pitch
            m.cx, m.row = x, mrow
            for sw, dx in zip(ring.sw[m], (-d, d)):
                sw.cx, sw.row = x + dx, srow
        xl, xr = min(sw.cx for m in mods for sw in ring.sw[m]), max(sw.cx for m in mods for sw in ring.sw[m])
        cx, a = (xl + xr) / 2, (xr - xl) / 2 + margin
        off = a - RING_END_INSET * s                            # the main node's switches: near the two ends of the ellipse
        need = (ring.first.slot + sw_w) / 2 + GAP * s
        if off < need:
            a, off = a + (need - off), need
        if cx - a < lo - margin - 1e-9 or cx + a > hi + margin + 1e-9:
            raise TooLarge()
        ring.cx, ring.a = cx, a
        ring.first.cx, ring.first.row = cx, arow
        for sw, dx in zip(ring.sw[ring.first], (-off, off)):
            sw.cx, sw.row = cx + dx, arow
        for row, nodes in ((arow, [ring.first] + ring.sw[ring.first]), (srow, [sw for m in mods for sw in ring.sw[m]]), (mrow, mods)):
            row.nodes = list(nodes)
            rows[(row.tier, 0)] = row
        b.ellipse_tiers[t0 + 1] = ring
        return t0 + 4

    def spoke(self, ring, sw):
        """The fibre line from a ring switch to the ellipse: straight up or down to the perimeter at the switch's x."""
        u = max(-0.98, min(0.98, (sw.cx - ring.cx) / ring.a))
        dy = ring.b * math.sqrt(1 - u * u)
        if sw.row.gi < ring.row.gi:
            return [(sw.cx, sw.y + sw.h), (sw.cx, ring.cy - dy)]
        return [(sw.cx, sw.y + sw.pic_dy), (sw.cx, ring.cy + dy)]

    # ---- links: classification, attachment slots, lanes -------------------------------------------------------------------
    def plan_links(self):
        ends = defaultdict(list)
        for lk in self.links:
            a, b = lk.a, lk.b
            if lk.explicit:
                continue
            if a.row is b.row:
                row = sorted(a.row.nodes, key=lambda n: n.cx)
                if abs(row.index(a) - row.index(b)) == 1:
                    lk.kind = "h"
                    left, right = (a, b) if a.cx < b.cx else (b, a)
                    ends[(left, "right")].append((0.0, lk, left))
                    ends[(right, "left")].append((0.0, lk, right))
                else:
                    lk.kind = "d"
                    ends[(a, "bottom")].append((b.cx, lk, a))
                    ends[(b, "bottom")].append((a.cx, lk, b))
            else:
                lk.kind = "v"
                up, lo = (a, b) if a.row.gi < b.row.gi else (b, a)
                lk.up, lk.lo = up, lo
                ends[(up, "bottom")].append((lo.cx, lk, up))
                ends[(lo, "top")].append((up.cx, lk, lo))
        self.ends = ends
        for (n, side), lst in ends.items():
            lst.sort(key=lambda e: e[0])
            m = len(lst)
            for i, (_, lk, node) in enumerate(lst):
                if side in ("top", "bottom"):
                    span = min(max(node.pw if side == "top" else node.w - 0.1, SLOT_PITCH * m), node.w - 0.1)   # many lines fan out, but stay on the shape
                    x0, x1 = node.cx - span / 2, node.cx + span / 2
                    x = node.cx if m == 1 else x0 + (i + 1) * (x1 - x0) / (m + 1)
                    pos = ("x", x, side)
                else:
                    sp = min(0.16, node.ph * 0.8 / max(1, m - 1))
                    pos = ("y", (i - (m - 1) / 2) * sp, side)
                lk.slots[id(node)] = pos
        # lane requests
        self.requests = defaultdict(list)
        for lk in self.links:
            if lk.explicit or lk.kind == "h":
                continue
            if lk.kind == "d":
                xa, xb = lk.slots[id(lk.a)][1], lk.slots[id(lk.b)][1]
                self.requests[self.gap_pad(lk.a.row)].append((min(xa, xb), max(xa, xb), lk, "main"))
                continue
            xu, xl = lk.slots[id(lk.up)][1], lk.slots[id(lk.lo)][1]
            lk.xu, lk.xl = xu, xl
            between = self.rows[lk.up.row.gi + 1:lk.lo.row.gi]
            if not between:
                if abs(xu - xl) > 0.01:
                    self.requests[self.gap_below(lk.up.row)].append((min(xu, xl), max(xu, xl), lk, "main"))
            else:
                xf = self.free_column(between, (xu + xl) / 2)
                lk.xf = xf
                if abs(xu - xf) > 0.01:
                    self.requests[self.gap_below(lk.up.row)].append((min(xu, xf), max(xu, xf), lk, "first"))
                if abs(xf - xl) > 0.01:
                    self.requests[self.gap_above(lk.lo.row)].append((min(xf, xl), max(xf, xl), lk, "second"))
        for key, reqs in self.requests.items():
            for lo, hi, lk, which in sorted(reqs, key=lambda r: (r[0], r[1])):
                lanes = self.lanes[key]
                for i, lane in enumerate(lanes):
                    if all(hi < a - 0.12 or lo > b + 0.12 for a, b in lane):
                        lane.append((lo, hi))
                        break
                else:
                    lanes.append([(lo, hi)])
                    i = len(lanes) - 1
                lk.lane[which] = i

    def gap_below(self, row):
        b = row.band
        return ("in", b.index, row.ri) if row is not b.rows[-1] else ("band", b.index)

    def gap_above(self, row):
        b = row.band
        return ("in", b.index, row.ri - 1) if row is not b.rows[0] else ("band", b.index - 1)

    def gap_pad(self, row):
        b = row.band
        return ("in", b.index, row.ri) if row is not b.rows[-1] else ("pad", b.index)

    def free_column(self, between, target):
        spans = sorted((n.cx - n.w / 2 - 0.12, n.cx + n.w / 2 + 0.12) for r in between for n in r.nodes)
        free, x = [], 0.1
        for a, b in spans:
            if a > x:
                free.append((x, a))
            x = max(x, b)
        free.append((x, self.area_w - 0.1))
        best = None
        for a, b in free:
            if b - a < 0.05:
                continue
            c = min(max(target, a + 0.03), b - 0.03)
            if best is None or abs(c - target) < abs(best - target):
                best = c
        return target if best is None else best

    # ---- y ------------------------------------------------------------------------------------------------------------------
    def assign_y(self):
        s, cursor = self.s, 0.0
        self.rows = [r for b in self.bands for r in b.rows]
        for gi, r in enumerate(self.rows):
            r.gi = gi
        for b in self.bands:
            for ri, r in enumerate(b.rows):
                r.ri = ri
        nl = lambda key: len(self.lanes.get(key, ()))
        for b in self.bands:
            b.y = cursor
            cursor += levels.HEADER_H + TOP_PAD + CAPTION_H
            for r in b.rows:
                r.h = ELLIPSE_H * s + 0.1 if r.kind == "ellipse" else max(n.h for n in r.nodes)
                r.y = cursor
                if r.kind == "ellipse":
                    r.ring.cy, r.ring.b = r.y + r.h / 2, ELLIPSE_H * s / 2
                for n in r.nodes:
                    n.y = r.y + (r.h - n.h) / 2
                cursor += r.h
                if r is not b.rows[-1]:
                    h = ROW_GAP * s + LANE * nl(("in", b.index, r.ri))
                    self.gap_geom[("in", b.index, r.ri)] = (cursor, h)
                    cursor += h
            h = BOTTOM_PAD + LANE * nl(("pad", b.index))
            self.gap_geom[("pad", b.index)] = (cursor, h)
            cursor += h
            b.h = cursor - b.y
            if b is not self.bands[-1]:
                h = BAND_GAP * s + LANE * nl(("band", b.index)) + self.extra
                self.gap_geom[("band", b.index)] = (cursor, h)
                cursor += h
        self.total_h = cursor

    def lane_y(self, key, i):
        top, h = self.gap_geom[key]
        n = len(self.lanes[key])
        return top + (h - (n - 1) * LANE) / 2 + i * LANE

    # ---- routes -----------------------------------------------------------------------------------------------------------------
    def route(self, lk):
        a, b = lk.a, lk.b
        if lk.explicit:
            return lk.explicit
        sl = lambda n: lk.slots[id(n)]
        if lk.kind == "h":
            left, right = (a, b) if a.cx < b.cx else (b, a)
            yl = left.y + left.mid_dy + sl(left)[1]
            yr = right.y + right.mid_dy + sl(right)[1]
            x1, x2 = left.cx + left.pw / 2, right.cx - right.pw / 2
            pts = [(x1, yl), (x2, yr)] if abs(yl - yr) < 1e-6 else [(x1, yl), ((x1 + x2) / 2, yl), ((x1 + x2) / 2, yr), (x2, yr)]
        elif lk.kind == "d":
            y = self.lane_y(self.gap_pad(a.row), lk.lane["main"])
            pts = [(sl(a)[1], a.y + a.h), (sl(a)[1], y), (sl(b)[1], y), (sl(b)[1], b.y + b.h)]
        else:
            up, lo = lk.up, lk.lo
            y0, y3 = up.y + up.h, lo.y + lo.pic_dy
            if lk.xf is None:
                if "main" in lk.lane:
                    y = self.lane_y(self.gap_below(up.row), lk.lane["main"])
                    pts = [(lk.xu, y0), (lk.xu, y), (lk.xl, y), (lk.xl, y3)]
                else:
                    pts = [(lk.xu, y0), (lk.xl, y3)]
            else:
                y1 = self.lane_y(self.gap_below(up.row), lk.lane["first"]) if "first" in lk.lane else y0
                y2 = self.lane_y(self.gap_above(lo.row), lk.lane["second"]) if "second" in lk.lane else y3
                pts = [(lk.xu, y0), (lk.xu, y1), (lk.xf, y1), (lk.xf, y2), (lk.xl, y2), (lk.xl, y3)]
            if up is b:
                pts = pts[::-1]
        out = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
                out.append(p)
        return out

    def run(self):
        self.make_bands()
        for b in self.bands:
            self.place_band(b)
        self.rows = [r for b in self.bands for r in b.rows]
        for gi, r in enumerate(self.rows):
            r.gi = gi
        for b in self.bands:
            for ri, r in enumerate(b.rows):
                r.ri = ri
        self.plan_links()
        self.assign_y()
        if self.total_h > self.area_h + 1e-9:
            raise TooLarge()
        if len(self.bands) > 1 and self.total_h < self.area_h:         # spare page height goes between the bands, so lanes and labels breathe
            self.extra = min((self.area_h - self.total_h) / (len(self.bands) - 1), MAX_EXTRA_GAP)
            self.assign_y()
        return self


# ================================================================================================================================
# Items -> nodes, links -> link instances
# ================================================================================================================================
def _aspect(path):
    try:
        w, h = png_size(path)
        return w / h
    except (OSError, ValueError):
        return 1.0


def expand_items(spec, comps, spec_dir):
    nodes, members = [], {}
    for idx, it in enumerate(spec["items"]):
        iid = it["id"].strip()
        kind = it.get("kind") if it.get("kind") in KINDS else "other"
        comp = APPROVED.get(kind) or it.get("component") or (None if it.get("image") else KIND_DEFAULT.get(kind))           # switches and patch panels: always the approved symbol, never a web picture
        label = _s(it.get("label")) or comps.get(comp)["label"]
        qty = it.get("qty", 1)
        path, image = (comps.picture_path(comp) if comp else None), None
        if path is None and it.get("image") and kind not in APPROVED:   # a library picture always wins; a library entry that has none ("box only") lets the web picture in
            image = str(it["image"])
            image = image if os.path.isabs(image) else os.path.join(spec_dir, image)
            path, comp = image, None
        pic = path is not None
        size = PICTURE if pic else BOX
        count = qty if qty <= MAX_EXPANDED else 1
        members[iid] = []
        for k in range(count):
            suffix = "-%02d" % (k + 1) if 1 < qty <= MAX_EXPANDED else ""
            text = label + suffix + (" x %d" % qty if qty > MAX_EXPANDED else "")
            if _s(it.get("model")):
                text += "\n" + _s(it["model"])
            n = Node(id=iid + suffix, src=iid, idx=idx, label=text, level=it["level"], scope=levels.check_scope(it), kind=kind,
                     comp=comp, image=image, image_source=it.get("image_source"), image_match=it.get("image_match"), pic=pic,
                     w0=size[0], h0=size[1], aspect=_aspect(path) if pic else 1.0, group=it.get("group"), near=it.get("near"),
                     assumed=bool(it.get("assumed")), generated=bool(it.get("generated")), is_secondary=False, item=it)
            nodes.append(n)
            members[iid].append(n)
    ids = [n.id for n in nodes]
    if len(set(ids)) != len(ids):
        raise SpecError(["an item id collides with a numbered copy of another item (for example 'pt' with qty 2 makes 'pt-01'); rename one"])
    for n in nodes:
        if n.near and members.get(n.near):
            n.near_node = members[n.near][0]
    return nodes, members


def pair_up(A, B):
    """Which unit meets which: equal counts pair one to one; a single unit meets every unit of the other side; otherwise each unit of
    the larger side meets the nearest unit of the smaller side."""
    if len(A) == len(B):
        return list(zip(A, B))
    if len(A) == 1:
        return [(A[0], b) for b in B]
    if len(B) == 1:
        return [(a, B[0]) for a in A]
    if len(A) > len(B):
        return [(a, B[min(len(B) - 1, i * len(B) // len(A))]) for i, a in enumerate(A)]
    return [(A[min(len(A) - 1, i * len(A) // len(B))], b) for i, b in enumerate(B)]


def make_links(spec, members, report=None):
    out = []
    for lk in spec.get("links", []):
        pairs = pair_up(members[lk["from"]], members[lk["to"]])
        for i, (a, b) in enumerate(pairs):
            link = Link(a, b, lk["cable"], _s(lk.get("label")) or None, bool(lk.get("assumed")), lk)
            link.quiet = i > 0 and len(pairs) > LABEL_ONCE             # one label for a bundle of identical lines, not twenty
            out.append(link)
        if len(pairs) > LABEL_ONCE and (_s(lk.get("label")) or lk.get("assumed")) and report is not None:
            report["added_by_rule"].append("link %s -> %s: %d lines; its label%s is printed once, on the first line" % (
                lk["from"], lk["to"], len(pairs), "/* mark" if lk.get("assumed") else ""))
    return out


def apply_redundancy(spec, members, links):
    """Primary / Secondary controller pair: labels, adjacency and two parallel redundancy links between them."""
    pairs = []
    for r in spec.get("redundancy", []):
        p, q = members[r["primary"]][0], members[r["secondary"]][0]
        p.partner, q.partner, q.is_secondary = q, p, True
        for n, name in ((p, "Primary Controller"), (q, "Secondary Controller")):
            model = _s(n.item.get("model"))
            n.label = name + ("\n" + model if model else "")
        base = _s(r.get("label")) or "Redundancy"
        count = r.get("links", 2)
        assumed = bool(r.get("assumed"))
        for k in range(count):
            links.append(Link(p, q, r.get("cable", "ethernet"), "%s link %d" % (base, k + 1) if count > 1 else base + " link", assumed, r))
        pairs.append((p, q))
    return pairs


def _first_line(node):
    return node.label.split("\n")[0]


def apply_rings(spec, comps, nodes, members, links, report):
    """Rings (task 8): for the first node and every member, two ring switches (generated unless the spec names them) joined to their node by
    an assumed ethernet link; the fibre spokes to the ellipse are drawn by the layout. Returns the list of Ring objects."""
    rings, idx = [], len(spec["items"])
    sym = APPROVED["switch"]
    for n, rg in enumerate(spec.get("rings", []), 1):
        first = members[rg["first"]][0]
        mods = [members[m][0] for m in rg["members"]]
        given = rg.get("switches") or {}
        rid = _s(rg.get("id")) or "ring%d" % n
        sw, added = {}, []
        for node in [first] + mods:
            if node.src in given:
                pair = [members[x][0] for x in given[node.src]]
            else:
                pair = []
                for k in (1, 2):
                    nid = "%s_%s_sw%d" % (rid, node.src, k)
                    s_node = Node(id=nid, src=nid, idx=idx, label="Ring switch", level=node.level, scope=node.scope, kind="switch", comp=sym,
                                  image=None, image_source=None, image_match=None, pic=True, w0=PICTURE[0], h0=PICTURE[1],
                                  aspect=_aspect(comps.picture_path(sym)), group=None, near=None, assumed=False, generated=True,
                                  is_secondary=False, item={})
                    idx += 1
                    nodes.append(s_node)
                    members[nid] = [s_node]
                    links.append(Link(node, s_node, "ethernet", None, True, None))      # the medium is not stated: assumed
                    pair.append(s_node)
                added.append(_first_line(node))
            sw[node] = pair
        ring = Ring(rid, _s(rg.get("label")) or "Fiber Optic Ring", first, mods, sw, rg)
        for node in [first] + mods:
            node.ring, node.ring_role = ring, "main" if node is first else "member"
            for s_node in sw[node]:
                s_node.ring, s_node.ring_role = ring, "switch"
        rings.append(ring)
        order = [first] + mods + [first]
        report["added_by_rule"].append("ring %s (%s): %s" % (rid, ring.label, " -> ".join(_first_line(x) for x in order)))
        if added:
            report["added_by_rule"].append("ring %s: 2 ring switches added at each of %s (required by the standard)" % (rid, ", ".join(added)))
    return rings


def adopt_patch_panel_bands(nodes, report):
    """A patch panel is drawn in the band (and scope) of the item it serves, beside it (task 9)."""
    for n in nodes:
        if n.kind == "patch_panel" and n.near_node is not None and (n.level, n.scope) != (n.near_node.level, n.near_node.scope):
            report["added_by_rule"].append("patch panel %s moved to %s (%s scope), the band of %s which it serves" % (
                _first_line(n), n.near_node.level, n.near_node.scope, _first_line(n.near_node)))
            n.level, n.scope = n.near_node.level, n.near_node.scope


# ================================================================================================================================
# The free-form spec
# ================================================================================================================================
def emit(spec, lay, cables, report, warnings):
    shapes, lines = [], []
    colours = levels.header_colours(spec, warnings)
    for b in lay.bands:
        lv = b.level
        shapes.append(dict(id="band_" + lv, kind="zone", x=0.0, y=b.y, w=lay.area_w, h=b.h, fill=levels.BAND_FILL, line=levels.BAND_LINE))
        shapes.append(dict(id="hdr_" + lv, kind="zone", x=0.0, y=b.y, w=levels.STRIP_W, h=b.h, fill=colours[lv], vertical=True,
                           line=colours[lv], label=levels.level_title(lv), size=levels.HEADER_SIZE))
        top = b.y + levels.HEADER_H + TOP_PAD
        for sc in b.cols:
            x0, x1 = b.col_x[sc]
            shapes.append(dict(id="scope_%s_%s" % (lv, sc), kind="zone", x=x0, y=top, w=x1 - x0, h=b.y + b.h - SCOPE_BOTTOM_MARGIN - top,
                               fill=levels.SCOPE_FILL[sc], line=levels.SCOPE_LINE, lw=0.5, label=levels.SCOPE_CAPTION[sc], size=6.5, italic=True))
    for n in lay.nodes:
        sh = dict(id=n.id, kind="box", label=n.label, x=n.cx - n.w / 2, y=n.y, w=n.w, h=n.h, level=n.level)
        if n.comp:
            sh["component"] = n.comp
        elif n.image:
            sh["image"] = n.image
            if n.image_source:
                sh["image_source"] = n.image_source
            if n.image_match:
                sh["image_match"] = n.image_match
        shapes.append(sh)
    for ring in lay.rings:
        shapes.append(dict(id=ring.shape_id, kind="ellipse", label=ring.label, x=ring.cx - ring.a, y=ring.cy - ring.b, w=2 * ring.a, h=2 * ring.b,
                           cable="fibre"))
        for sw in ring.switches():
            lines.append({"from": sw.id, "to": ring.shape_id, "cable": "fibre",
                          "points": [[round(x, 4), round(y, 4)] for x, y in lay.spoke(ring, sw)]})
    for lk in lay.links:
        label = None if getattr(lk, "quiet", False) else lk.label
        if lk.assumed and not getattr(lk, "quiet", False):
            label = (label or "") + "*"
        d = {"from": lk.a.id, "to": lk.b.id, "cable": lk.cable, "points": [[round(x, 4), round(y, 4)] for x, y in lay.route(lk)]}
        if label:
            d["label"] = label
        lines.append(d)
    return shapes, lines


def compile_v2(spec, comps=None, cables=None, spec_dir=".", area=None):
    """Free-form spec for build_diagram.prepare(). Raises SpecError for errors and for questions that must be asked first."""
    comps, cables = comps or Components(), cables or Cables()
    errors, questions, warnings = validate(spec, comps, cables)
    if errors or questions:
        raise SpecError(errors, questions)
    area_w, area_h = area or (15.9354, 9.8729)
    nodes, members = expand_items(spec, comps, spec_dir)
    report = {"added_by_rule": [], "assumed": [], "warnings": warnings}
    links = make_links(spec, members, report)
    pairs = apply_redundancy(spec, members, links)
    rings = apply_rings(spec, comps, nodes, members, links, report)
    adopt_patch_panel_bands(nodes, report)
    lay = None
    for s in SCALES:
        try:
            lay = Layout(nodes, links, s, area_w, area_h, members, rings).run()
            break
        except TooLarge:
            for lk in links:
                lk.lane, lk.xf = {}, None
            continue
    if lay is None:
        raise TooLarge()
    for it in spec["items"]:
        if it.get("assumed"):
            report["assumed"].append("item %s (%s, %s)" % (_s(it.get("label")) or it["id"], it["level"], levels.check_scope(it)))
    for lk in spec.get("links", []):
        if lk.get("assumed"):
            report["assumed"].append("link %s -> %s (%s%s)" % (lk["from"], lk["to"], lk["cable"], ", " + lk["label"] if _s(lk.get("label")) else ""))
    for r in spec.get("redundancy", []):
        if r.get("assumed"):
            report["assumed"].append("redundancy %s / %s: %d x %s link%s (medium not stated)" % (
                r["primary"], r["secondary"], r.get("links", 2), r.get("cable", "ethernet"), "s" if r.get("links", 2) != 1 else ""))
    report["assumed"] += [a for a in spec.get("assumptions", []) if isinstance(a, str) and a.strip()]
    shapes, lines = emit(spec, lay, cables, report, warnings)
    notes = [str(n) for n in spec.get("notes", []) if isinstance(n, str)]
    if any(lk.assumed for lk in links):
        notes.append("* = assumed link, to be confirmed.")
    out = {"project": spec.get("project", {}), "notes": notes, "shapes": shapes, "lines": lines, "_report": report}
    return out
