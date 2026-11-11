"""Clean a picture taken from the web so it sits on the drawing without its white background.   Standard library at import time.

Pillow is used only when it is installed (it is in ChatGPT's sandbox; elsewhere it is optional). Without it the picture is placed as it is
and the status says so, so the core build still runs on the standard library alone.

    clean(path) -> (new_path, status)
    status is one of:  'removed'  |  'already-transparent'  |  'skipped: Pillow not installed'  |  'skipped: background not plain'
                       |  'skipped: <reason>'   (a picture that cannot be processed is left as it is)
"""
import os
import tempfile

MAX_SIDE = 800          # the longer side is reduced to this many pixels (before the flood fill, so it is fast)
TOLERANCE = 40          # how far from white a pixel may be and still count as background (0-255 per channel, summed by Pillow's floodfill)
WHITE_MIN = 235         # every channel of a corner must be at least this for the background to count as plain white
PAD = 2                 # pixels kept around the object after cropping

REMOVED, TRANSPARENT = "removed", "already-transparent"
NO_PILLOW, NOT_PLAIN = "skipped: Pillow not installed", "skipped: background not plain"


def _pillow():
    try:
        from PIL import Image, ImageDraw
        return Image, ImageDraw
    except ImportError:
        return None


def clean(path):
    """(path of the picture to use, status). The original file is never changed; a cleaned copy is a PNG in a temporary folder."""
    mods = _pillow()
    if mods is None:
        return path, NO_PILLOW
    Image, ImageDraw = mods
    try:
        img = Image.open(path).convert("RGBA")
    except (OSError, ValueError) as e:
        return path, "skipped: cannot read the picture (%s)" % e
    w, h = img.size
    corners = [img.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    if any(c[3] < 255 for c in corners):
        return path, TRANSPARENT
    if not all(min(c[:3]) >= WHITE_MIN for c in corners):
        return path, NOT_PLAIN
    if max(w, h) > MAX_SIDE:                                    # shrink first: the fill then runs on at most 800 x 800 pixels
        k = MAX_SIDE / max(w, h)
        img = img.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
        w, h = img.size
    img = _fill_outside(img, ImageDraw)
    box = img.getchannel("A").point(lambda a: 255 if a > 0 else 0).getbbox()
    if box is None:                                             # everything was background: nothing sensible to keep
        return path, "skipped: the whole picture is background"
    img = img.crop((max(0, box[0] - PAD), max(0, box[1] - PAD), min(w, box[2] + PAD), min(h, box[3] + PAD)))
    out = os.path.join(tempfile.mkdtemp(), os.path.splitext(os.path.basename(path))[0] + "_clean.png")
    img.save(out)
    return out, REMOVED


def _fill_outside(img, ImageDraw):
    """Make the white that is connected to the picture's border transparent. White inside the object (not reached from the border) stays."""
    w, h = img.size
    seeds = [(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)] + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)]
    clear = (255, 255, 255, 0)
    for seed in seeds:
        px = img.getpixel(seed)
        if px[3] == 0 or min(px[:3]) < WHITE_MIN - TOLERANCE:    # already cleared by an earlier fill, or the object touches the border here
            continue
        ImageDraw.floodfill(img, seed, clear, thresh=TOLERANCE)
    return img
