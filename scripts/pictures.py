"""Make a picture sit cleanly on the page: transparent background, trimmed, not oversized. Pillow if present, standard library otherwise.

    path, note = prepare(path)      # path of the cleaned PNG (cached in a temp folder); note is None or a short problem text

What it does to a picture without its own transparent background (typical web photo of a device on white):
  * the background is the colour the picture's border is made of (white, light grey, ...), removed by flood fill from the edges inward, so white
    that is *inside* the device is kept;
  * a one-pixel halo of near-background colour left along the cut is removed as well;
  * the picture is cropped to what is left and shrunk to at most MAX_SIDE pixels (keeps the .vsdx small).
A picture that already has transparent corners is only cropped and shrunk. If almost nothing would be left (a white device on white), or the file
cannot be read, the original is used and `note` says so.
"""
import hashlib
import os
import struct
import tempfile
import zlib
from collections import deque

MAX_SIDE = 2400           # retain detail for A3 printing; never upscale a small source
CACHE_VERSION = "reference-quality-v2"
TOL = 30                  # per-channel distance from the border colour that still counts as background
HALO = 70                 # looser distance for the pixels touching the cut
PAD = 2
_CACHE_DIR = os.path.join(tempfile.gettempdir(), "arch_pictures")
_PNG = b"\x89PNG\r\n\x1a\n"


# ---- Pillow-free PNG reading / writing (8-bit, non-interlaced: gray, RGB, RGBA, palette) -------------------------------------
def _read_png(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != _PNG:
        raise ValueError("not a PNG")
    pos, idat, plte, trns, hdr = 8, [], None, None, None
    while pos < len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat.append(body)
        elif typ == b"PLTE":
            plte = body
        elif typ == b"tRNS":
            trns = body
        pos += 12 + n
    w, h, depth, ctype, _, _, interlace = hdr
    if depth != 8 or interlace or ctype not in (0, 2, 3, 4, 6):
        raise ValueError("unsupported PNG variant (needs 8-bit, not interlaced)")
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b"".join(idat))
    stride, rows, prev = w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f = raw[y * (stride + 1)]
        cur = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = cur[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if f == 1:
                cur[i] = (cur[i] + a) & 255
            elif f == 2:
                cur[i] = (cur[i] + b) & 255
            elif f == 3:
                cur[i] = (cur[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(cur)
        prev = cur
    px = []
    for cur in rows:
        line = []
        for x in range(w):
            if ctype == 6:
                line.append(tuple(cur[x * 4:x * 4 + 4]))
            elif ctype == 2:
                line.append((cur[x * 3], cur[x * 3 + 1], cur[x * 3 + 2], 255))
            elif ctype == 0:
                line.append((cur[x], cur[x], cur[x], 255))
            elif ctype == 4:
                line.append((cur[x * 2], cur[x * 2], cur[x * 2], cur[x * 2 + 1]))
            else:                                                   # palette
                i = cur[x]
                line.append((plte[i * 3], plte[i * 3 + 1], plte[i * 3 + 2], trns[i] if trns and i < len(trns) else 255))
        px.append(line)
    return w, h, px


def _write_png(path, w, h, px):
    raw = bytearray()
    for line in px:
        raw.append(0)
        for r, g, b, a in line:
            raw += bytes((r, g, b, a))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(_PNG + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


# ---- the cleaning itself, on a list-of-rows RGBA model so the same code serves both routes ---------------------------------------
def _near(p, bg, tol):
    return abs(p[0] - bg[0]) <= tol and abs(p[1] - bg[1]) <= tol and abs(p[2] - bg[2]) <= tol


def _clean(w, h, px):
    """(w, h, px) cleaned, or None if nothing sensible would be left."""
    corners = [px[0][0], px[0][w - 1], px[h - 1][0], px[h - 1][w - 1]]
    if any(p[3] < 255 for row in px for p in row):                # preserve supplied alpha, including antialiased edges
        out = px
    else:
        inset = min(2, (w - 1) // 2, (h - 1) // 2)
        inner = [px[inset][inset], px[inset][w - 1 - inset], px[h - 1 - inset][inset], px[h - 1 - inset][w - 1 - inset]]
        # Ignore a thin grey product-photo frame when the inset is consistently
        # lighter. Only edge seeds use the looser tolerance; interiors do not.
        if all(min(c[:3]) >= 230 for c in inner) and all(_near(c, inner[0], TOL) for c in inner):
            corners = inner
        opaque = [c for c in corners if c[3] >= 16]
        bg = tuple(sorted(c[i] for c in opaque)[len(opaque) // 2] for i in range(3))
        out = [list(r) for r in px]
        def background_pixel(p):
            # A neutral soft shadow is still backdrop when connected to an edge.
            # Coloured equipment and enclosed white product details stay intact.
            return _near(p, bg, TOL) or (min(bg) >= 230 and max(p[:3]) - min(p[:3]) <= 12 and _near(p, bg, 100))
        seen = [bytearray(w) for _ in range(h)]
        q = deque()
        edge = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
        for x, y in edge:
            if not seen[y][x] and _near(px[y][x], bg, HALO):
                seen[y][x] = 1
                q.append((x, y))
        while q:
            x, y = q.popleft()
            out[y][x] = (px[y][x][0], px[y][x][1], px[y][x][2], 0)
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and background_pixel(px[ny][nx]):
                    seen[ny][nx] = 1
                    q.append((nx, ny))
        halo = []                                                   # one-pixel fringe of near-background colour along the cut
        for y in range(h):
            for x in range(w):
                if out[y][x][3] and _near(out[y][x], bg, HALO) and any(
                        0 <= nx < w and 0 <= ny < h and out[ny][nx][3] == 0 for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
                    halo.append((x, y))
        for x, y in halo:
            out[y][x] = (out[y][x][0], out[y][x][1], out[y][x][2], 0)
    ys = [y for y in range(h) if any(p[3] > 16 for p in out[y])]
    xs = [x for x in range(w) if any(out[y][x][3] > 16 for y in ys)] if ys else []
    if not ys or not xs:
        return None
    x0, x1, y0, y1 = max(min(xs) - PAD, 0), min(max(xs) + PAD + 1, w), max(ys[0] - PAD, 0), min(ys[-1] + PAD + 1, h)
    kept = sum(1 for y in range(y0, y1) for x in range(x0, x1) if out[y][x][3] > 16)
    if kept < 0.03 * w * h:                                         # (almost) nothing left: the cut ate the device
        return None
    return x1 - x0, y1 - y0, [out[y][x0:x1] for y in range(y0, y1)]


def _shrink(w, h, px):
    if max(w, h) <= MAX_SIDE:
        return w, h, px
    f = MAX_SIDE / max(w, h)
    nw, nh = max(1, int(w * f)), max(1, int(h * f))
    return nw, nh, [[px[int(y / f)][int(x / f)] for x in range(nw)] for y in range(nh)]


def prepare(path, background="auto"):
    """(path of the cleaned PNG, note). Never raises: on any problem the original path comes back with a note."""
    try:
        if background not in ("auto", "keep"):
            raise ValueError('background must be "auto" or "keep"')
        st = os.stat(path)
        key = hashlib.sha1(("%s|%s|%s|%s|%s|%s" % (CACHE_VERSION, MAX_SIDE, background, os.path.abspath(path), st.st_mtime_ns, st.st_size)).encode()).hexdigest()[:16]
        out = os.path.join(_CACHE_DIR, key + ".png")
        if os.path.exists(out):
            return out, None
        os.makedirs(_CACHE_DIR, exist_ok=True)
        try:
            from PIL import Image, ImageOps
            with Image.open(path) as source:
                im = ImageOps.exif_transpose(source).convert("RGBA")
            # Transparent originals need no segmentation. Crop at native resolution
            # before applying the cap, so small devices on a large canvas stay sharp.
            if im.getchannel("A").getextrema()[0] < 255 or background == "keep":
                bbox = im.getchannel("A").getbbox()
                if bbox:
                    bbox = (max(0, bbox[0] - PAD), max(0, bbox[1] - PAD), min(im.width, bbox[2] + PAD), min(im.height, bbox[3] + PAD))
                    im = im.crop(bbox)
                im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
                im.save(out, dpi=(300, 300))
                return out, None
            im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            w, h = im.size
            data = list(im.getdata())
            px = [data[y * w:(y + 1) * w] for y in range(h)]
        except ImportError:
            w, h, px = _read_png(path)
        if background == "keep":
            _write_png(out, w, h, px)
            return out, None
        corners = [px[0][0], px[0][-1], px[-1][0], px[-1][-1]]
        if not any(p[3] < 255 for row in px for p in row):
            # Automatic removal is safe only for a consistent light studio backdrop.
            # Complex scenes and dark equipment at the image edges need a better source.
            light = all(min(c[:3]) >= 190 and max(c[:3]) - min(c[:3]) <= 30 for c in corners)
            consistent = all(_near(c, corners[0], TOL) for c in corners)
            if not light or not consistent:
                return path, "background is not a uniform light backdrop; use a transparent product picture or background=keep; the picture is used as it is"
        res = _clean(w, h, px)
        if res is None:
            return path, "background could not be removed (almost nothing is left); the picture is used as it is"
        w, h, px = res
        try:
            from PIL import Image
            cleaned = Image.new("RGBA", (w, h))
            cleaned.putdata([p for row in px for p in row])
            cleaned.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            cleaned.save(out, dpi=(300, 300))
        except ImportError:
            w, h, px = _shrink(w, h, px)
            _write_png(out, w, h, px)
        return out, None
    except Exception as e:                                          # an unreadable picture must not stop the build
        return path, "background not removed (%s); the picture is used as it is" % e
