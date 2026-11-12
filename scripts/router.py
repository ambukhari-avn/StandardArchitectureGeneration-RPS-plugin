"""Standard cable routing: square-cornered, end-to-end, round devices, few bends, little overlap, hops where cables must cross.

Rules applied to every cable that has no manual instruction (page coordinates, inches, y up; a rectangle is (x, y, w, h)):
  1. only horizontal and vertical segments (never a diagonal);
  2. a cable starts and ends ON the edge of the two devices it joins and leaves / enters it at a right angle, facing the other device
     whenever that is the shortest way;
  3. it never runs through a device (devices are kept clear by CLEAR inches);
  4. fewest bends: straight if the two devices line up, else an L, else a Z; extra bends cost more than extra length;
  5. cables do not share a track: running along an earlier cable is penalised hard, so parallel cables take separate tracks;
  6. several cables on one side of a device are spread along that side (SPREAD apart) instead of piling up on one point;
  7. crossings are penalised, so they are few; the ones left are drawn as a small hop (`add_hops`).
Manual instructions always win: "via" points are followed exactly (made square), "from_side" / "to_side" fix the side a cable uses.
"""
import heapq
import math
from bisect import bisect_left, bisect_right

CLEAR = 0.06              # clearance kept round every device
STUB = 0.15               # first / last piece of a cable, at a right angle to the device edge
BEND, CROSS, TOUCH, OVERLAP = 0.9, 0.7, 2.0, 8.0     # penalties (inches of extra length they are worth)
SPREAD = 0.28             # spacing between cables that attach to the same side of a device
HOP_R = 0.07              # radius of a hop
SIDES = {"left": (-1, 0), "right": (1, 0), "top": (0, 1), "bottom": (0, -1)}
OPP = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]            # grid directions (x+, x-, y+, y-)


class RouteError(Exception):
    pass


# ---- ports --------------------------------------------------------------------------------------------------------------------
def port(r, side, t=0.5):
    x, y, w, h = r
    if side == "left":
        return (x, y + h * t)
    if side == "right":
        return (x + w, y + h * t)
    if side == "top":
        return (x + w * t, y + h)
    return (x + w * t, y)


def side_extent(r, side):
    """(fixed edge coordinate, lo, hi): the side's line and the range along it."""
    x, y, w, h = r
    return {"left": (x, y, y + h), "right": (x + w, y, y + h), "top": (y + h, x, x + w), "bottom": (y, x, x + w)}[side]


def with_t(r, side, c):
    """The point on `side` whose coordinate along the side is c."""
    e, lo, hi = side_extent(r, side)
    c = min(max(c, lo + 0.08), hi - 0.08) if hi - lo > 0.2 else (lo + hi) / 2
    return (e, c) if side in ("left", "right") else (c, e)


def facing_side(a, b):
    """The side of a that faces rectangle b."""
    acx, acy, bcx, bcy = a[0] + a[2] / 2, a[1] + a[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    dx, dy = bcx - acx, bcy - acy
    if abs(dx) * a[3] > abs(dy) * a[2]:
        return "right" if dx > 0 else "left"
    return "top" if dy > 0 else "bottom"


def candidate_ports(r, side, other):
    """Attachment points on one side: its middle, and (when the other device overlaps it in that direction) the point that makes a straight cable."""
    pts = [port(r, side)]
    e, lo, hi = side_extent(r, side)
    olo, ohi = (other[1], other[1] + other[3]) if side in ("left", "right") else (other[0], other[0] + other[2])
    a, b = max(lo, olo), min(hi, ohi)
    if b - a > 0.15:
        pts.append(with_t(r, side, (a + b) / 2))
    return pts


# ---- grid ---------------------------------------------------------------------------------------------------------------------
def _uniq(vals, lo, hi, tol=0.012):
    vals = sorted(v for v in vals if lo - 1e-9 <= v <= hi + 1e-9)
    out = []
    for v in vals:
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


class Grid:
    def __init__(self, rects, bounds):
        x0, y0, x1, y1 = bounds
        xs, ys = [x0, x1], [y0, y1]
        for (x, y, w, h) in rects:
            xs += [x - STUB, x + w + STUB, x, x + w, x + w / 2]
            ys += [y - STUB, y + h + STUB, y, y + h, y + h / 2]
            for k in (0.5, 1, 1.5, 2, 2.5):                           # spread positions on every side
                xs += [x + w / 2 - k * SPREAD, x + w / 2 + k * SPREAD]
                ys += [y + h / 2 - k * SPREAD, y + h / 2 + k * SPREAD]
        for vals in (xs, ys):                                         # tracks half way across every gap, and either side of it
            base = sorted(vals)
            for a, b in zip(base, base[1:]):
                if b - a > 0.3:
                    vals.append((a + b) / 2)
                    if b - a > 0.8:
                        vals += [(a + b) / 2 - 0.12, (a + b) / 2 + 0.12]
        self.xs, self.ys = _uniq(xs, x0, x1), _uniq(ys, y0, y1)
        self.bounds = bounds
        nx, ny = len(self.xs), len(self.ys)
        self.hb = [bytearray(ny) for _ in range(max(nx - 1, 0))]      # hb[i][j]: edge (i,j)-(i+1,j) blocked
        self.vb = [bytearray(max(ny - 1, 0)) for _ in range(nx)]      # vb[i][j]: edge (i,j)-(i,j+1) blocked
        for (x, y, w, h) in rects:
            rx0, rx1, ry0, ry1 = x - CLEAR, x + w + CLEAR, y - CLEAR, y + h + CLEAR
            jlo, jhi = bisect_right(self.ys, ry0 + 1e-9), bisect_left(self.ys, ry1 - 1e-9)
            for j in range(jlo, jhi):                                 # horizontal edges at rows strictly inside the rectangle
                for i in range(max(bisect_right(self.xs, rx0 + 1e-9) - 1, 0), min(bisect_left(self.xs, rx1 - 1e-9), nx - 1)):
                    self.hb[i][j] = 1
            ilo, ihi = bisect_right(self.xs, rx0 + 1e-9), bisect_left(self.xs, rx1 - 1e-9)
            for i in range(ilo, ihi):
                for j in range(max(bisect_right(self.ys, ry0 + 1e-9) - 1, 0), min(bisect_left(self.ys, ry1 - 1e-9), ny - 1)):
                    self.vb[i][j] = 1

    def ix(self, x):
        i = bisect_left(self.xs, x - 0.013)
        return i if i < len(self.xs) and abs(self.xs[i] - x) <= 0.013 else None

    def iy(self, y):
        j = bisect_left(self.ys, y - 0.013)
        return j if j < len(self.ys) and abs(self.ys[j] - y) <= 0.013 else None

    def blocked(self, i, j, d):
        di, dj = DIRS[d]
        if di:
            return self.hb[min(i, i + di)][j]
        return self.vb[i][min(j, j + dj)]


class Occupancy:
    """What earlier cables already use: grid edges (collinear overlap) and nodes (crossings / touching)."""
    def __init__(self):
        self.edges, self.nodes = set(), {}

    def add(self, grid, nodes):
        for (i, j), (k, l) in zip(nodes, nodes[1:]):
            self.edges.add((min(i, k), min(j, l), 0 if j == l else 1))
        for n, (i, j) in enumerate(nodes):
            mid = 0 < n < len(nodes) - 1
            if not mid:
                self.nodes.setdefault((i, j), set()).add("end")
                continue
            pi, pj = nodes[n - 1]
            ni, nj = nodes[n + 1]
            if pj == j and nj == j:
                self.nodes.setdefault((i, j), set()).add("H")
            elif pi == i and ni == i:
                self.nodes.setdefault((i, j), set()).add("V")
            else:
                self.nodes.setdefault((i, j), set()).add("B")


# ---- the search ---------------------------------------------------------------------------------------------------------------
def _search(grid, occ, starts, targets, bend_cost):
    """starts: [(node, dir, port, cost)], targets: {node: [(inward_dir_index, port)]}. Returns (cost, nodes, start_port, end_port) or None."""
    xs, ys = grid.xs, grid.ys
    heap, best, prev = [], {}, {}
    for node, d, prt, c0 in starts:
        st = (node[0], node[1], d)
        if c0 < best.get(st, 1e18):
            best[st] = c0
            prev[st] = (None, prt)
            heapq.heappush(heap, (c0, st))
    found, limit = None, 1e18
    while heap:
        cost, st = heapq.heappop(heap)
        if cost > best.get(st, 1e18) or cost > limit:
            continue
        i, j, d = st
        if (i, j) in targets:
            for inward, prt in targets[(i, j)]:
                total = cost + (0 if inward == d else bend_cost)
                if total < limit:
                    limit, found = total, (st, prt)
        for nd in range(4):
            if nd == (d ^ 1):                                         # no U-turns
                continue
            ni, nj = i + DIRS[nd][0], j + DIRS[nd][1]
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)) or grid.blocked(i, j, nd):
                continue
            length = abs(xs[ni] - xs[i]) + abs(ys[nj] - ys[j])
            c = cost + length + (bend_cost if nd != d else 0)
            if (min(i, ni), min(j, nj), 0 if nd < 2 else 1) in occ.edges:
                c += OVERLAP * length
            use = occ.nodes.get((ni, nj))
            if use:
                if "B" in use or "end" in use:
                    c += TOUCH
                elif ("V" in use and nd < 2) or ("H" in use and nd >= 2):
                    c += CROSS
            ns = (ni, nj, nd)
            if c < best.get(ns, 1e18):
                best[ns] = c
                prev[ns] = (st, None)
                heapq.heappush(heap, (c, ns))
    if not found:
        return None
    st, end_port = found
    nodes = []
    while st is not None:
        nodes.append((st[0], st[1]))
        st, start_port = prev[st]
    nodes.reverse()
    return limit, nodes, start_port, end_port


def _stub_node(grid, p, side):
    dx, dy = SIDES[side]
    return grid.ix(p[0] + dx * STUB), grid.iy(p[1] + dy * STUB)


def _endpoints(grid, r, side_names, other, fixed):
    """[(point, side)] attachment candidates of rectangle r."""
    out = []
    for sd in side_names:
        for p in ([fixed[sd]] if fixed and sd in fixed else candidate_ports(r, sd, other)):
            out.append((p, sd))
    return out


def _one(grid, occ, ra, rb, sides_a, sides_b, fixed_a, fixed_b, bend_cost):
    starts, targets = [], {}
    for p, sd in _endpoints(grid, ra, sides_a, rb, fixed_a):
        i, j = _stub_node(grid, p, sd)
        if i is not None and j is not None:
            d = DIRS.index(SIDES[sd]) if SIDES[sd] in DIRS else 0
            starts.append(((i, j), d, (p, sd), STUB))
    for p, sd in _endpoints(grid, rb, sides_b, ra, fixed_b):
        i, j = _stub_node(grid, p, sd)
        if i is not None and j is not None:
            inward = DIRS.index((-SIDES[sd][0], -SIDES[sd][1]))
            targets.setdefault((i, j), []).append((inward, (p, sd)))
    if not starts or not targets:
        return None
    return _search(grid, occ, starts, targets, bend_cost)


def _pts(grid, nodes, a_port, b_port):
    pts = [a_port[0]] + [(grid.xs[i], grid.ys[j]) for i, j in nodes] + [b_port[0]]
    out = [pts[0]]
    for p in pts[1:]:                                                 # drop repeated and collinear points
        if abs(p[0] - out[-1][0]) < 1e-6 and abs(p[1] - out[-1][1]) < 1e-6:
            continue
        if len(out) >= 2 and ((abs(out[-2][0] - out[-1][0]) < 1e-6 and abs(out[-1][0] - p[0]) < 1e-6) or
                              (abs(out[-2][1] - out[-1][1]) < 1e-6 and abs(out[-1][1] - p[1]) < 1e-6)):
            out[-1] = p
        else:
            out.append(p)
    return out


# ---- manual routes ------------------------------------------------------------------------------------------------------------
def square(pts, first_horizontal):
    """Make a point list square-cornered: where two consecutive points are not aligned a corner is added so every segment is horizontal or vertical."""
    out, horiz = [pts[0]], first_horizontal
    for q in pts[1:]:
        p = out[-1]
        if abs(p[0] - q[0]) > 1e-6 and abs(p[1] - q[1]) > 1e-6:
            out.append((q[0], p[1]) if horiz else (p[0], q[1]))
            horiz = not horiz
        elif abs(p[0] - q[0]) > 1e-6:
            horiz = False                                             # a horizontal segment: the next one turns vertical
        elif abs(p[1] - q[1]) > 1e-6:
            horiz = True
        if abs(q[0] - out[-1][0]) > 1e-6 or abs(q[1] - out[-1][1]) > 1e-6:
            out.append(q)
    return out


def manual(ra, rb, via, side_a=None, side_b=None):
    """The cable the file spelled out: from the side of a facing the first via point, through the points, to the side of b facing the last."""
    sa = side_a or facing_side(ra, (via[0][0], via[0][1], 0, 0))
    sb = side_b or facing_side(rb, (via[-1][0], via[-1][1], 0, 0))
    pa, pb = port(ra, sa), port(rb, sb)
    pts = square([pa] + list(via) + [pb], sa in ("left", "right"))
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-6 or abs(p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    return out


# ---- all cables ---------------------------------------------------------------------------------------------------------------
def route_all(requests, rects, bounds):
    """requests: [{a, b (rectangles), via, from_side, to_side, straight}]. rects: every device rectangle (obstacles).
    Returns a list of point lists (None where no clear route exists: the caller falls back to a plain route)."""
    grid = Grid(rects, bounds)
    results = [None] * len(requests)
    auto = [n for n, q in enumerate(requests) if not q.get("via")]
    for n, q in enumerate(requests):
        if q.get("via"):
            results[n] = manual(q["a"], q["b"], q["via"], q.get("from_side"), q.get("to_side"))
    fixed, first = {}, None                                            # pass 2: spread cables that share a side of a device
    for attempt in (1, 2):
        occ = Occupancy()
        chosen = {}
        for n in auto:
            q = requests[n]
            bend = 40.0 if q.get("straight") else BEND
            sa = [q["from_side"]] if q.get("from_side") else list(SIDES)
            sb = [q["to_side"]] if q.get("to_side") else list(SIDES)
            fa, fb = fixed.get((n, "a")), fixed.get((n, "b"))
            res = _one(grid, occ, q["a"], q["b"], sa, sb, {fa[1]: fa[0]} if fa else None, {fb[1]: fb[0]} if fb else None, bend)
            if res is None:
                results[n] = first[n] if first and first[n] else None
                continue
            cost, nodes, ap, bp = res
            occ.add(grid, nodes)
            results[n] = _pts(grid, nodes, ap, bp)
            chosen[n] = (ap, bp)
        if attempt == 1:
            first = list(results)
            groups = {}
            for n, (ap, bp) in chosen.items():
                groups.setdefault((requests[n]["a_id"], ap[1]), []).append((n, "a", ap, results[n]))
                groups.setdefault((requests[n]["b_id"], bp[1]), []).append((n, "b", bp, results[n]))
            moved = False
            for (sid, sd), members in groups.items():
                if len(members) < 2:
                    continue
                n0, end0 = members[0][0], members[0][1]
                r = requests[n0]["a" if end0 == "a" else "b"]
                horizontal_side = sd in ("left", "right")
                def key(m):                                            # order along the side by where the cable heads next (no crossing near the device)
                    pts = m[3] if m[1] == "a" else m[3][::-1]
                    nxt = pts[1] if len(pts) > 1 else pts[0]
                    far = pts[2] if len(pts) > 2 else nxt
                    return (far[1] if horizontal_side else far[0])
                members.sort(key=key)
                e, lo, hi = side_extent(r, sd)
                if len(members) > 5 or (hi - lo) < SPREAD * len(members) + 0.2:
                    continue                                           # too many for this side: they stay on the middle
                gap = SPREAD
                mid = (lo + hi) / 2
                for k, (n, end, prt, _) in enumerate(members):
                    c = mid + (k - (len(members) - 1) / 2) * gap
                    fixed[(n, end)] = (with_t(r, sd, c), sd)
                    moved = True
            if not moved:
                break
    return results


# ---- hops ---------------------------------------------------------------------------------------------------------------------
def add_hops(paths):
    """Where a horizontal run crosses another cable's vertical run, replace the crossing by a small semicircular hop (the horizontal one hops).
    Returns new point lists; T-junctions, touching ends and crossings too close to a corner or to another hop stay plain crossings."""
    verticals = []
    for n, pts in enumerate(paths):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(x1 - x2) < 1e-6 and abs(y1 - y2) > 1e-6:
                verticals.append((n, x1, min(y1, y2), max(y1, y2)))
    out = []
    for n, pts in enumerate(paths):
        new = [pts[0]]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(y1 - y2) < 1e-6 and abs(x1 - x2) > 2 * HOP_R + 0.06:
                lo, hi = min(x1, x2), max(x1, x2)
                xs = sorted({round(v[1], 4) for v in verticals if v[0] != n and v[2] + 0.03 < y1 < v[3] - 0.03
                             and lo + HOP_R + 0.03 < v[1] < hi - HOP_R - 0.03})
                kept = []
                for x in xs:
                    if not kept or x - kept[-1] >= 2 * HOP_R + 0.03:
                        kept.append(x)
                if x1 > x2:
                    kept.reverse()
                for cx in kept:
                    sgn = 1 if x2 > x1 else -1
                    new.append((cx - sgn * HOP_R, y1))
                    for k in range(1, 8):
                        ang = math.pi * k / 8
                        new.append((cx - sgn * HOP_R * math.cos(ang), y1 + HOP_R * math.sin(ang)))
                    new.append((cx + sgn * HOP_R, y1))
            new.append((x2, y2))
        out.append(new)
    return out
