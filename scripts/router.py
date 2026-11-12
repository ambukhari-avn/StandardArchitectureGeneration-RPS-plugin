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
BEND, CROSS, TOUCH, OVERLAP, NEAR, ROW = 1.3, 1.8, 2.5, 5.0, 0.4, 2.2   # penalties (inches of extra length they are worth); NEAR = running right beside another cable, ROW = factor for a horizontal run level with a row of devices (cables belong in the channels between rows)
SIDEPEN = 3.0            # extra cost for leaving / entering a device by a side that does not face the other device
TRACK = 0.12              # spacing of the always-available tracks (so parallel cables can be kept apart)
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
    def __init__(self, rects, bounds, extra_x=(), extra_y=()):
        x0, y0, x1, y1 = bounds
        xs, ys = [x0, x1] + list(extra_x), [y0, y1] + list(extra_y)
        xs += [x0 + k * TRACK for k in range(1, int((x1 - x0) / TRACK))]
        ys += [y0 + k * TRACK for k in range(1, int((y1 - y0) / TRACK))]
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
        self.row = [any(y + 0.02 < yy < y + h - 0.02 for (x, y, w, h) in rects) for yy in self.ys]   # this height is level with a device
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
        self.edges, self.nodes, self.near = set(), {}, set()

    def add(self, grid, nodes):
        for (i, j), (k, l) in zip(nodes, nodes[1:]):
            self.edges.add((min(i, k), min(j, l), 0 if j == l else 1))
            if j == l:                                                # the tracks either side of a horizontal run, and of a vertical one
                self.near.update({(min(i, k), j - 1, 0), (min(i, k), j + 1, 0)})
            else:
                self.near.update({(i - 1, min(j, l), 1), (i + 1, min(j, l), 1)})
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
    """A* from the start stubs to any target stub. starts: [(node, dir, port, cost)], targets: {node: [(inward_dir_index, port)]}.
    Returns (cost, nodes, start_port, end_port) or None."""
    xs, ys = grid.xs, grid.ys
    tl = list(targets)

    def h(i, j):
        return min(abs(xs[i] - xs[a]) + abs(ys[j] - ys[b]) for a, b in tl)
    heap, best, prev = [], {}, {}
    for node, d, prt, c0 in starts:
        st = (node[0], node[1], d)
        if c0 < best.get(st, 1e18):
            best[st] = c0
            prev[st] = (None, prt)
            heapq.heappush(heap, (c0 + h(node[0], node[1]), c0, st))
    found, limit = None, 1e18
    while heap:
        f, cost, st = heapq.heappop(heap)
        if cost > best.get(st, 1e18) or f > limit:
            continue
        i, j, d = st
        if (i, j) in targets:
            for inward, prt, pen in targets[(i, j)]:
                total = cost + pen + (0 if inward == d else bend_cost)
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
            ek = (min(i, ni), min(j, nj), 0 if nd < 2 else 1)
            if nd < 2 and grid.row[j]:
                c += (ROW - 1) * length
            if ek in occ.edges:
                c += OVERLAP * length
            elif ek in occ.near:
                c += NEAR * length
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
                heapq.heappush(heap, (c + h(ni, nj), c, ns))
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
            starts.append(((i, j), d, (p, sd), STUB + (0 if sd == facing_side(ra, rb) else SIDEPEN)))
    for p, sd in _endpoints(grid, rb, sides_b, ra, fixed_b):
        i, j = _stub_node(grid, p, sd)
        if i is not None and j is not None:
            inward = DIRS.index((-SIDES[sd][0], -SIDES[sd][1]))
            targets.setdefault((i, j), []).append((inward, (p, sd), 0 if sd == facing_side(rb, ra) else SIDEPEN))
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
# ---- channel routing (rows of devices, tracks in the free bands between them) ------------------------------------------------------
def _rows(rects):
    """Cluster rectangles into horizontal rows, top first: [(lo, hi, [rect, ...])]."""
    rows = []
    for r in sorted(set(rects), key=lambda r: -(r[1] + r[3] / 2)):
        cy = r[1] + r[3] / 2
        for row in rows:
            lo, hi, mem = row
            if lo - 0.3 * (hi - lo) <= cy <= hi + 0.3 * (hi - lo) and abs(cy - sum(m[1] + m[3] / 2 for m in mem) / len(mem)) < 0.45 * max(m[3] for m in mem):
                row[0], row[1] = min(lo, r[1]), max(hi, r[1] + r[3])
                mem.append(r)
                break
        else:
            rows.append([r[1], r[1] + r[3], [r]])
    return rows


def _hits(pts, rects, skip, e=0.03):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        for r in rects:
            if r in skip:
                continue
            x, y, w, h = r
            if min(x1, x2) < x + w + e and max(x1, x2) > x - e and min(y1, y2) < y + h + e and max(y1, y2) > y - e:
                return True
    return False


def _crossings(upper, lower):
    """Crossings if cable `upper` runs on a track above cable `lower` in the same band."""
    c = sum(1 for x in lower["tops"] if upper["l"] <= x <= upper["r"])      # lower's drop from the row above passes upper's track
    c += sum(1 for x in upper["bots"] if lower["l"] <= x <= lower["r"])     # upper's rise from the row below passes lower's track
    return c


def _order_tracks(items):
    """Order the cables of one band from the top track down so that the fewest cables cross (nested spans: the outer one is further out)."""
    def total(seq):
        return sum(_crossings(seq[i], seq[j]) for i in range(len(seq)) for j in range(i + 1, len(seq)))
    best = None
    for key in (lambda i: i["r"] - i["l"], lambda i: i["l"], lambda i: -(i["r"] - i["l"])):
        seq = sorted(items, key=key)
        cost = total(seq)
        for _ in range(200):
            improved = False
            for i in range(len(seq) - 1):
                if _crossings(seq[i + 1], seq[i]) < _crossings(seq[i], seq[i + 1]):
                    seq[i], seq[i + 1] = seq[i + 1], seq[i]
                    improved = True
            if not improved:
                break
        cost = total(seq)
        if best is None or cost < best[0]:
            best = (cost, list(seq))
    return best[1]


def channel_routes(requests, rects, bounds):
    """Tidy routes for cables between devices that sit in rows (layered drawings): leave by the top or bottom, run along a track in the free
    band between the rows, enter by the top or bottom. Returns a list with a point list per request, None where this style does not apply."""
    out = [None] * len(requests)
    rows = _rows(rects)
    if len(rows) < 1:
        return out
    x0, y0, x1, y1 = bounds
    row_of = {r: n for n, (lo, hi, mem) in enumerate(rows) for r in mem}
    chan = {}                                                           # channel k: free band above row k (k = len(rows): below the last row)
    for k in range(len(rows) + 1):
        top = rows[k - 1][0] if k > 0 else y1                           # (rows[k-1] is the row above channel k, when k > 0) ...
        hi_edge = rows[k][1] if k < len(rows) else y0
        chan[k] = (hi_edge, rows[k - 1][0] if k > 0 else y1)            # (bottom, top) of the free band
    # chan[k] = band between row k-1 (above) and row k (below); chan[0] above all rows; chan[n] below all rows
    plans, load, buses = {}, {}, {}
    side_groups = {}
    straight, uses = {}, {}                                              # neighbours in a row with nothing between them: a straight horizontal cable
    for n, q in enumerate(requests):
        if q.get("via") or q.get("from_side") or q.get("to_side") or q["a"] not in row_of or q["b"] not in row_of:
            continue
        a, b = q["a"], q["b"]
        if row_of[a] != row_of[b]:
            continue
        left, right = (a, b) if a[0] < b[0] else (b, a)
        ylo, yhi = max(a[1], b[1]), min(a[1] + a[3], b[1] + b[3])
        gx0, gx1 = left[0] + left[2], right[0]
        if yhi - ylo < 0.3 or gx1 - gx0 < 0.2:
            continue
        if any(r not in (a, b) and r[0] < gx1 and r[0] + r[2] > gx0 and r[1] < yhi and r[1] + r[3] > ylo for r in rects):
            continue
        straight[n] = (left, right, (ylo + yhi) / 2, a is left)
        for key in ((left, "right"), (right, "left")):
            uses[key] = uses.get(key, 0) + 1
    for n, (left, right, ymid, a_left) in list(straight.items()):
        if uses[(left, "right")] == 1 and uses[(right, "left")] == 1:
            out[n] = [(left[0] + left[2], ymid), (right[0], ymid)] if a_left else [(right[0], ymid), (left[0] + left[2], ymid)]
        else:
            del straight[n]
    for n, q in enumerate(requests):
        if n in straight:
            continue
        if q.get("via") or q.get("from_side") or q.get("to_side") or q["a"] not in row_of or q["b"] not in row_of:
            continue
        a, b = q["a"], q["b"]
        ra, rb = row_of[a], row_of[b]
        if ra == rb:                                                    # same row: round the top or the bottom, whichever band is less used
            k = ra if load.get(ra, 0) <= load.get(ra + 1, 0) else ra + 1
            side = "top" if k == ra else "bottom"
            ends = [(a, side, b), (b, side, a)]
        else:
            k = min(ra, rb) + 1
            ends = [(a, "bottom" if ra < rb else "top", b), (b, "top" if ra < rb else "bottom", a)]
        load[k] = load.get(k, 0) + 1
        plans[n] = (k, ends)
        if q.get("bus"):
            buses.setdefault((k, q["bus"]), []).append(n)
        for idx, (dev, side, other) in enumerate(ends):
            side_groups.setdefault((dev, side), []).append((n, idx, other))
    port_x = {}
    for (dev, side), members in side_groups.items():
        members.sort(key=lambda m: m[2][0] + m[2][2] / 2)
        x, y, w, h = dev
        m = len(members)
        gap = min(SPREAD, (w - 0.2) / m) if m > 1 else 0
        for i, (n, idx, other) in enumerate(members):
            port_x[(n, idx)] = x + w / 2 + (i - (m - 1) / 2) * gap
    on_bus = {n for members in buses.values() if len(members) > 1 for n in members}     # cables that share a bus line (hardwired fan-in)
    for n, (k, ends) in plans.items():                                  # one cable on each end and the devices overlap: make it straight
        (da, sa, oa), (db, sb, ob) = ends
        if n not in on_bus and sa != sb and len(side_groups[(da, sa)]) == 1 and len(side_groups[(db, sb)]) == 1:
            lo_x, hi_x = max(da[0], db[0]), min(da[0] + da[2], db[0] + db[2])
            if hi_x - lo_x > 0.2:
                port_x[(n, 0)] = port_x[(n, 1)] = (lo_x + hi_x) / 2
    # tracks in each channel: one track per cable, ordered so that as few cables as possible cross; shared (left-edge) only if the band is too narrow
    per_chan, bus_items = {}, {}
    for n, (k, ends) in plans.items():
        px0, px1 = port_x[(n, 0)], port_x[(n, 1)]
        if n not in on_bus and ends[0][1] != ends[1][1] and abs(px0 - px1) < 1e-6:
            continue                                                    # straight vertical: no track
        tops = [x for x, (d, s, o) in zip((px0, px1), ends) if s == "bottom"]      # ends that come down from the row above the band
        bots = [x for x, (d, s, o) in zip((px0, px1), ends) if s == "top"]         # ends that come up from the row below it
        if n in on_bus:                                                 # one shared track (the bus) for all cables of this hub
            key = (k, requests[n]["bus"])
            mine = bus_items.get(key)
            if mine is None:
                mine = bus_items[key] = dict(n=n, l=min(px0, px1), r=max(px0, px1), tops=[], bots=[], members=[])
                per_chan.setdefault(k, []).append(mine)
            mine["l"], mine["r"] = min(mine["l"], px0, px1), max(mine["r"], px0, px1)
            mine["tops"] += tops
            mine["bots"] += bots
            mine["members"].append(n)
            continue
        per_chan.setdefault(k, []).append(dict(n=n, l=min(px0, px1), r=max(px0, px1), tops=tops, bots=bots))
    ytrack = {}
    for k, items in per_chan.items():
        lo_y, hi_y = chan[k]
        avail = hi_y - lo_y - 0.2
        if avail < 0:
            continue
        order = _order_tracks(items)                                    # top track first
        if len(order) > 1 and avail / (len(order) - 1) >= 0.09:
            step = min(0.2, avail / (len(order) - 1))
            top_y = (lo_y + hi_y) / 2 + step * (len(order) - 1) / 2
            for ti, it in enumerate(order):
                ytrack[it["n"]] = top_y - ti * step
        elif len(order) == 1:
            ytrack[order[0]["n"]] = (lo_y + hi_y) / 2
        else:                                                           # too many for the band: share tracks where the spans do not overlap
            tracks, assign = [], {}
            for it in sorted(items, key=lambda i: i["l"]):
                for ti, end in enumerate(tracks):
                    if end + 0.12 < it["l"]:
                        tracks[ti] = it["r"]
                        assign[it["n"]] = ti
                        break
                else:
                    tracks.append(it["r"])
                    assign[it["n"]] = len(tracks) - 1
            cnt = len(tracks)
            if avail < 0.08 * max(cnt - 1, 0):
                continue
            step = min(0.2, avail / max(cnt - 1, 1)) if cnt > 1 else 0
            top_y = (lo_y + hi_y) / 2 + step * (cnt - 1) / 2
            for n_, ti in assign.items():
                ytrack[n_] = top_y - ti * step
    for items in per_chan.values():                                     # every cable on a bus gets the bus's track
        for it in items:
            if it["n"] in ytrack:
                for m in it.get("members", ()):
                    ytrack[m] = ytrack[it["n"]]
    for n, (k, ends) in plans.items():
        px0, px1 = port_x[(n, 0)], port_x[(n, 1)]
        (da, sa, oa), (db, sb, ob) = ends
        ya = da[1] + da[3] if sa == "top" else da[1]
        yb = db[1] + db[3] if sb == "top" else db[1]
        if n in ytrack:
            pts = [(px0, ya), (px0, ytrack[n]), (px1, ytrack[n]), (px1, yb)]
        elif abs(px0 - px1) < 1e-6:
            pts = [(px0, ya), (px1, yb)]
        else:
            continue
        if not (x0 - 1e-6 <= min(p[0] for p in pts) and max(p[0] for p in pts) <= x1 + 1e-6 and y0 - 1e-6 <= min(p[1] for p in pts) and max(p[1] for p in pts) <= y1 + 1e-6):
            continue
        if _hits(pts, rects, (da, db)):
            continue
        out[n] = pts
    return out


def _manhattan(q):
    (ax, ay, aw, ah), (bx, by, bw, bh) = q["a"], q["b"]
    return abs(ax + aw / 2 - bx - bw / 2) + abs(ay + ah / 2 - by - bh / 2)


def route_all(requests, rects, bounds):
    """requests: [{a, b (rectangles), a_id, b_id, via, from_side, to_side, straight}]. rects: every device rectangle (obstacles).
    Returns a list of point lists (None where no clear route exists: the caller falls back to a plain route).
    Pass 1 routes the cables (short ones first, so they stay direct) and finds which cables share a side of a device; pass 2 spreads
    those along the side and routes everything again."""
    results = [None] * len(requests)
    auto = sorted((n for n, q in enumerate(requests) if not q.get("via")), key=lambda n: _manhattan(requests[n]))
    for n, q in enumerate(requests):
        if q.get("via"):
            results[n] = manual(q["a"], q["b"], q["via"], q.get("from_side"), q.get("to_side"))
    tidy = channel_routes(requests, rects, bounds)
    for n in list(auto):
        if tidy[n] is not None:
            results[n] = tidy[n]
    auto = [n for n in auto if tidy[n] is None]
    if not auto:
        return results
    grid, fixed, first = Grid(rects, bounds), {}, None
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
        if attempt == 2:
            break
        first = list(results)
        groups = {}
        for n, (ap, bp) in chosen.items():
            groups.setdefault((requests[n]["a_id"], ap[1]), []).append((n, "a", ap, results[n]))
            groups.setdefault((requests[n]["b_id"], bp[1]), []).append((n, "b", bp, results[n]))
        extra_x, extra_y = [], []
        for (sid, sd), members in groups.items():
            if len(members) < 2:
                continue
            n0, end0 = members[0][0], members[0][1]
            r = requests[n0]["a" if end0 == "a" else "b"]
            horizontal_side = sd in ("left", "right")

            def key(m):                                                # order along the side by where the cable heads next (no crossing near the device)
                pts = m[3] if m[1] == "a" else m[3][::-1]
                far = pts[2] if len(pts) > 2 else pts[-1]
                return far[1] if horizontal_side else far[0]
            members.sort(key=key)
            e, lo, hi = side_extent(r, sd)
            gap = min(SPREAD, (hi - lo - 0.2) / len(members))
            if gap < 0.12:
                continue                                               # too many for this side: they stay on the middle
            for k, (n, end, prt, _) in enumerate(members):
                c = (lo + hi) / 2 + (k - (len(members) - 1) / 2) * gap
                pt = with_t(r, sd, c)
                fixed[(n, end)] = (pt, sd)
                (extra_y if horizontal_side else extra_x).append(pt[1] if horizontal_side else pt[0])
        if not fixed:
            break
        grid = Grid(rects, bounds, extra_x, extra_y)                   # the grid now has a track for every spread position
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
