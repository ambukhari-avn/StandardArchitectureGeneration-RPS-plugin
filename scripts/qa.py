"""Automatic drawing checks run on every build (Phases 8, 9 and 11-E). Standard library only.

Each check returns defects as plain sentences. build_diagram.py prints them as `defect:` lines and returns them in result["qa"];
a drawing with defects must be corrected before delivery (the AI still inspects the preview: these checks do not replace that).

    python scripts/qa.py --lock      (maintainers only) record the approved header/footer geometry in data/template_lock.json
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
LOCK = os.path.join(ROOT, "data", "template_lock.json")
TOL = 0.03            # inches: an end point this close to an equipment/box border counts as attached
HOP = 0.13            # crossing hops are short non-orthogonal pieces; longer diagonal segments are defects
A3 = (16.54, 11.69)


def _r(v):
    return round(float(v), 3)


def template_signature(page):
    """Geometry and style of the master-template elements (Phase 9): sheet frame, title block position, footer frame, section
    cards and dividers, and the logo picture (position, size and file contents). Text values are not part of it."""
    sig = {}
    for s in page.shapes:
        k = s.get("key") or ""
        if k in ("frame", "title", "footer-frame", "logo") or k.startswith(("footer-divider:", "footer-card:")):
            entry = {"box": [_r(s["x"]), _r(s["y"]), _r(s["w"]), _r(s["h"])], "fill": s.get("fill"), "line": s.get("line"),
                     "lw": s.get("lw"), "pattern": s.get("pattern")}
            if k == "title":
                entry = {"box": entry["box"], "color": s.get("color"), "bold": s.get("bold")}
            if s.get("image"):
                with open(s["image"], "rb") as fh:
                    entry["sha256"] = hashlib.sha256(fh.read()).hexdigest()
            sig[k] = entry
    return sig


def check_template(page):
    if not os.path.exists(LOCK):
        return ["template lock file data/template_lock.json is missing"]
    with open(LOCK, encoding="utf-8") as fh:
        locked = json.load(fh)["elements"]
    now = template_signature(page)
    out = []
    for k, v in locked.items():
        if k not in now:
            out.append("approved template element %r is missing" % k)
        elif now[k] != v:
            out.append("approved template element %r changed (%s -> %s); the header/footer/logo are locked" % (k, v, now[k]))
    for k in now:
        if k not in locked:
            out.append("unexpected template element %r" % k)
    return out


def _on_border(pt, r):
    x, y, w, h = r
    px, py = pt
    inside = x - TOL <= px <= x + w + TOL and y - TOL <= py <= y + h + TOL
    return inside and min(abs(px - x), abs(px - x - w), abs(py - y), abs(py - y - h)) <= TOL


def _inside(pt, r):
    x, y, w, h = r
    return x - TOL <= pt[0] <= x + w + TOL and y - TOL <= pt[1] <= y + h + TOL


def check_cables(lines, paths, rect_of_id, label_of_id=None):
    """8.1 / 8.2: every cable has both endpoints, is one continuous orthogonal polyline, and ends on its own equipment or box."""
    out = []
    for c, pts in zip(lines, paths):
        name = "%s (%s to %s)" % (c.get("where", "cable"), c["a"], c["b"])
        if not pts or len(pts) < 2:
            out.append("%s has no drawn path" % name)
            continue
        ra, rb = rect_of_id(c["a"]), rect_of_id(c["b"])
        ends = [pts[0], pts[-1]]
        ok = (_on_border(ends[0], ra) and _on_border(ends[1], rb)) or (_on_border(ends[0], rb) and _on_border(ends[1], ra))
        if not ok and not ((_inside(ends[0], ra) and _inside(ends[1], rb)) or (_inside(ends[0], rb) and _inside(ends[1], ra))):
            out.append("%s does not terminate on its equipment or box (broken or floating end)" % name)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x0 - x1) > 1e-3 and abs(y0 - y1) > 1e-3 and ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5 > HOP:
                out.append("%s has a diagonal segment" % name)
                break
    return out


def check_cable_spacing(lines, paths, gap=0.075, run=0.2):
    """8.3 / 8.6: two different cables must not run along (almost) the same track: that reads as one cable or an accidental junction."""
    segs = []
    for n, pts in enumerate(paths):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(y0 - y1) < 1e-3 and abs(x1 - x0) > run:
                segs.append((n, "h", y0, min(x0, x1), max(x0, x1)))
            elif abs(x0 - x1) < 1e-3 and abs(y1 - y0) > run:
                segs.append((n, "v", x0, min(y0, y1), max(y0, y1)))
    out, seen = [], set()
    for i, a in enumerate(segs):
        for b in segs[i + 1:]:
            if a[0] == b[0] or a[1] != b[1] or abs(a[2] - b[2]) >= gap:
                continue
            shared = min(a[4], b[4]) - max(a[3], b[3])
            ca, cb = lines[a[0]], lines[b[0]]
            bus = ca.get("cable") == cb.get("cable") == "hardwired"          # the approved hardwired bus into an I/O is shared on purpose
            on_trunk = {ca["a"], ca["b"]} & {cb["a"], cb["b"]} and (ca["a"] == ca["b"] or cb["a"] == cb["b"])   # a bus's own uplink
            if shared > run and not bus and not on_trunk and (a[0], b[0]) not in seen:
                seen.add((a[0], b[0]))
                out.append("cables %s and %s run along the same track for %.2f in (reads as one cable or a junction)" %
                           ("%s-%s" % (ca["a"], ca["b"]), "%s-%s" % (cb["a"], cb["b"]), shared))
    return out


def check_attachments(lines, paths, tol=0.05):
    """8.6: two different cables must not end on the same point of a device (that reads as a junction)."""
    ends, out = [], []
    for n, pts in enumerate(paths):
        if pts:
            ends += [(n, pts[0]), (n, pts[-1])]
    for i, (n, p) in enumerate(ends):
        for m, q in ends[i + 1:]:
            if n != m and abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol:
                a, b = lines[n], lines[m]
                if a.get("cable") == b.get("cable") == "hardwired":
                    continue
                out.append("cables %s-%s and %s-%s end at the same point (reads as a junction)" % (a["a"], a["b"], b["a"], b["b"]))
    return out


def _overlap(a, b, margin=0.0):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return dx > margin and dy > margin, max(dx, 0) * max(dy, 0)


def _text_extent(s):
    """Approximate inked box of a text shape (its box is often wider than its words)."""
    if s.get("text_angle"):
        return (s["x"], s["y"], s["w"], s["h"])
    lines = str(s.get("text") or "").split("\n")
    size = (s.get("size") or 8) / 72
    tw = min(s["w"], max(len(l) for l in lines) * size * .55 + .04)
    th = min(s["h"], len(lines) * size * 1.2 + .02)
    x = s["x"] + (s["w"] - tw) / 2 if s.get("halign", 1) == 1 else s["x"] if s.get("halign") == 0 else s["x"] + s["w"] - tw
    v = s.get("valign", 1)
    y = s["y"] + (s["h"] - th) / 2 if v == 1 else s["y"] + s["h"] - th if v == 0 else s["y"]
    return (x, y, tw, th)


def check_text(page, footer_top):
    """No label/caption text overlaps another text block in the drawing area (the footer is checked by its own fitting)."""
    texts = [s for s in page.shapes if s.get("text") and s["kind"] == "rect" and s["y"] >= footer_top - 1e-6
             and not (s.get("key") or "").startswith(("layer-desc:",))]
    out = []
    boxes = [(s, _text_extent(s)) for s in texts]
    for i, (a, ra) in enumerate(boxes):
        for b, rb in boxes[i + 1:]:
            hit, area = _overlap(ra, rb, 0.02)
            if hit and area > 0.004:
                out.append("text %r overlaps text %r" % (str(a["text"])[:30], str(b["text"])[:30]))
    return out


def check_headings(page, panels):
    heads = [s for s in page.shapes if (s.get("key") or "").startswith("layer-heading:")]
    names = {s["key"].split(":", 1)[1]: s for s in page.shapes if (s.get("key") or "").startswith("layer-name:")}
    out = []
    if not panels:
        return out
    if {p["id"] for p in panels} != {h["key"].split(":", 1)[1] for h in heads}:
        out.append("layer headings do not match the selected layers")
    if len({_r(h["w"]) for h in heads}) > 1:
        out.append("layer heading strips have different widths")
    for p in panels:
        n = names.get(p["id"])
        if not n or n.get("text_angle") != 90:
            out.append("layer %r heading is not vertical" % p["id"])
    return out


def check_containers(shapes):
    """7.4: a visible box around a single piece of Avanceon equipment, with no title, panel, scope or I/O-frame reason, is unnecessary."""
    out = []
    for g in shapes:
        if g["kind"] != "group" or g.get("frame") is False or g.get("scope") == "other" or g.get("solid") or g.get("label"):
            continue
        kids = [s for s in shapes if s.get("parent") == g["id"]]
        if len(kids) == 1 and kids[0]["kind"] == "box" and g.get("layer") != "field":
            out.append("box %r only wraps %r: remove it (no panel, scope or system reason)" % (g["id"], kids[0]["id"]))
    return out


_SIZES = None


def sizes():
    global _SIZES
    if _SIZES is None:
        import re
        with open(os.path.join(ROOT, "data", "equipment_sizes.json"), encoding="utf-8") as fh:
            raw = json.load(fh)["categories"]
        _SIZES = {k: dict(v, rx=re.compile(v["words"], re.I) if v.get("words") else None) for k, v in raw.items()}
    return _SIZES


def category_of(s):
    """Equipment category for sizing: declared, else recognised from the caption (first match in equipment_sizes.json order)."""
    table = sizes()
    if s.get("category") in table:
        return s["category"]
    if s.get("category") in ("eng_workstation", "laptop"):
        return "workstation"
    if s.get("category") in ("historian",):
        return "server"
    text = " ".join(str(s.get(k) or "") for k in ("label", "sub", "component"))
    for name, v in table.items():
        if v.get("rx") is not None and v["rx"].search(text):
            return name
    return "default"


def displayed_long_side(d):
    """Longest visible side of a device picture as laid out (inches)."""
    import draw
    sub_h = draw.SUB_ZONE if d.get("sub") else 0
    area_h = d["h"] - draw.LABEL_ZONE - sub_h
    if area_h <= 0 or not d.get("pic"):
        return 0.0
    try:
        vw, vh = draw.visible_size(d["pic"], d["w"], area_h, 0.90)
    except Exception:
        return 0.0
    return max(vw, vh)


def check_sizes(shapes):
    """Item 7: every equipment picture meets its category's minimum displayed size (PLC and remote I/O have the largest minimums)."""
    out = []
    table = sizes()
    for d in shapes:
        if d["kind"] != "box" or not d.get("reference") or not d.get("pic"):
            continue
        cat = category_of(d)
        need = table.get(cat, table["default"])["min"]
        got = displayed_long_side(d)
        if 0 < got < need - 0.005:
            out.append("%s picture %r is %.2f in, below the %.2f in minimum for %s equipment" % (cat, d["id"], got, need, cat))
    return out


def check_clearance(lines, paths, shapes, rect_of_id, clear=0.04):
    """Item 6: a cable keeps a minimum clearance from equipment it does not connect to (no running along or through a picture)."""
    out = []
    devices = [d for d in shapes if d["kind"] == "box" and d.get("reference")]
    for c, pts in zip(lines, paths):
        ends = {c["a"], c["b"]}
        for d in devices:
            if d["id"] in ends or any(d["id"] == e for e in ends):
                continue
            x, y, w, h = rect_of_id(d["id"])
            x0, y0, x1, y1 = x - clear, y - clear, x + w + clear, y + h + clear
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                lo_x, hi_x, lo_y, hi_y = min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)
                if hi_x > x0 and lo_x < x1 and hi_y > y0 and lo_y < y1:
                    out.append("cable %s-%s passes within %.2f in of %r" % (c["a"], c["b"], clear, d["id"]))
                    break
            else:
                continue
            break
    return out


def check_corridors(lines, paths, corridors, shapes, rect_of_id, tol=0.06):
    """Item 6: a cable stays in the band of layers it connects, and never runs inside a visible box that holds neither of its ends."""
    out = []
    by_id = {s["id"]: s for s in shapes}

    def ancestors(i):
        res, s = set(), by_id.get(i)
        while s is not None and s.get("parent"):
            res.add(s["parent"])
            s = by_id.get(s["parent"])
        return res
    boxes = [g for g in shapes if g["kind"] == "group" and g.get("frame") is not False]
    for c, pts, band in zip(lines, paths, corridors):
        name = "cable %s-%s" % (c["a"], c["b"])
        if band:
            lo, hi = band[1] - tol, band[1] + band[3] + tol
            if any(not (lo <= y <= hi) for x, y in pts):
                out.append("%s leaves the layers it connects (routing corridor)" % name)
                continue
        own = ancestors(c["a"]) | ancestors(c["b"]) | {c["a"], c["b"]}
        for g in boxes:
            if g["id"] in own:
                continue
            x, y, w, h = rect_of_id(g["id"])
            inside = [(px, py) for px, py in pts if x + tol < px < x + w - tol and y + tol < py < y + h - tol]
            if len(inside) >= 2:
                out.append("%s runs inside the box %r that holds neither of its ends" % (name, g["id"]))
                break
    return out


def layout_signature(page):
    """Hash of the complete drawn geometry (every shape's kind, key, box, points, text): identical for identical layouts."""
    rows = []
    for s in page.shapes:
        rows.append([s.get("kind"), s.get("key"), _r(s["x"]), _r(s["y"]), _r(s["w"]), _r(s["h"]), str(s.get("text") or ""),
                     [[_r(x), _r(y)] for x, y in (s.get("pts") or [])], s.get("line"), s.get("fill")])
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def check_picture_ends(lines, paths, by_id, picture_rect, on, margin=.02):
    """8.1: a cable ending on a device meets its visible picture (top/bottom within the picture's width, sides beside the picture),
    never empty space around a wide caption, which reads as a dangling stub."""
    out = []
    for c, pts in zip(lines, paths):
        if len(pts) < 2:
            continue
        for end, nxt in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            for e in (c["a"], c["b"]):
                d = by_id.get(e)
                if d is None or d["kind"] != "box" or not d.get("pic") or not on(end, d):
                    continue
                px, py, pw, ph = picture_rect(d)
                vertical = abs(end[0] - nxt[0]) < 1e-6
                if vertical and not (px - margin <= end[0] <= px + pw + margin):
                    out.append("cable %s-%s ends beside the picture of %r (dangling end)" % (c["a"], c["b"], e))
                elif not vertical and not (py - margin <= end[1] <= py + ph + margin):
                    out.append("cable %s-%s ends above or below the picture of %r (dangling end)" % (c["a"], c["b"], e))
                elif not vertical and min(abs(end[0] - px), abs(end[0] - px - pw)) > .06:
                    out.append("cable %s-%s stops short of the picture of %r (floating end)" % (c["a"], c["b"], e))
    return out


def check_inside(paths, bottom, top, left, right):
    """8.1: every cable stays inside the drawing area (above the footer)."""
    for pts in paths:
        if any(not (left - .02 <= x <= right + .02 and bottom - .02 <= y <= top + .02) for x, y in pts):
            return ["a cable leaves the drawing area (runs into the footer or off the page)"]
    return []


def check_page(page):
    w, h = page.w, page.h
    return [] if abs(w - A3[0]) < .02 and abs(h - A3[1]) < .02 else ["page is %.2f x %.2f in, not A3 landscape" % (w, h)]


def lock():
    """Record the current header/footer geometry as the approved template (run only when the template is deliberately changed)."""
    sys.path.insert(0, HERE)
    import build_diagram as B
    import tempfile
    spec = B.load_json(os.path.join(ROOT, "samples", "reference_quality.json"))
    out = os.path.join(tempfile.mkdtemp(), "lock.vsdx")
    r = B.build(spec, os.path.join(ROOT, "base", "base.vsdx"), out, spec_dir=os.path.join(ROOT, "samples"), check_template=False)
    with open(LOCK, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"_note": "Approved Avanceon header/footer/logo geometry (Phase 9). Builds stop if these change. Regenerate only for an "
                            "approved template change: python scripts/qa.py --lock", "elements": template_signature(r["page"])},
                  fh, indent=1)
        fh.write("\n")
    print("locked %d template elements in %s" % (len(template_signature(r["page"])), LOCK))


if __name__ == "__main__":
    if sys.argv[1:] == ["--lock"]:
        lock()
    else:
        print(__doc__)
