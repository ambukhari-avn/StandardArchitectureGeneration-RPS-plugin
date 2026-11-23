"""Draw one dataset component into a cell of the page. Standard library only.

  * with a picture in the dataset -> the picture (true aspect ratio, centred) with its label underneath;
  * without                       -> a rectangle with the label inside (decisions D8).
The label is always the dataset label, plus an optional suffix such as "-01" for numbered copies; callers
cannot pass free text. If the label does not fit at or above the font floor, TextFitError is raised.
"""
import os
from textfit import TextFitError, fit_size
from vsdx_writer import FONT_FLOOR, png_size

LABEL_SIZES = (7, 6.5, 6)
BOX_SIZES = (8, 7, 6.5, 6)
LABEL_ZONE = 0.30                 # inches reserved under a picture for its label (three lines at 6 pt)
BOX_FILL, BOX_LINE = "#F2F2F2", "#404040"


SUB_ZONE, SUB_COLOR = 0.14, "#1F4E9E"      # optional second caption line, in blue (e.g. "(Primary)")


_VISIBLE = {}


def visible_box(pic):
    """(left, top, right, bottom) of the visible equipment as fractions of the image, ignoring
    transparent margins (alpha <= 16). The file itself is never modified. Full image when the
    picture is opaque or cannot be analysed."""
    try:
        st = os.stat(pic)
        key = (os.path.abspath(pic), st.st_mtime_ns, st.st_size)
        if key in _VISIBLE:
            return _VISIBLE[key]
        box = (0., 0., 1., 1.)
        try:
            from PIL import Image
            with Image.open(pic) as im:
                alpha = im.convert("RGBA").getchannel("A")
            w, h = alpha.size
            if alpha.getextrema()[0] < 255:
                b = alpha.point(lambda v: 255 if v > 16 else 0).getbbox()
                if b:
                    box = (b[0] / w, b[1] / h, b[2] / w, b[3] / h)
        except ImportError:
            import pictures
            w, h, px = pictures._read_png(pic)
            xs = [i for row in px for i, p in enumerate(row) if p[3] > 16]
            ys = [j for j, row in enumerate(px) if any(p[3] > 16 for p in row)]
            if xs and ys and (min(xs), min(ys), max(xs) + 1, max(ys) + 1) != (0, 0, w, h):
                box = (min(xs) / w, min(ys) / h, (max(xs) + 1) / w, (max(ys) + 1) / h)
        if box[2] - box[0] < .02 or box[3] - box[1] < .02:
            box = (0., 0., 1., 1.)
        _VISIBLE[key] = box
        return box
    except Exception:
        return (0., 0., 1., 1.)


def draw_picture(page, pic, label, x, y, w, h, key, parent=None, soft=False, sub=None, bold=False, fill=1.0, visible=False):
    """A picture (PNG path) in the cell, true aspect ratio, centred, with `label` underneath.
    sub: an optional second caption line printed under the label in blue. bold: the label in bold.
    soft: a label that does not fit is printed at the font floor instead of raising TextFitError."""
    try:
        size = fit_size(label, w, LABEL_ZONE, LABEL_SIZES, bold)
    except TextFitError:
        if not soft:
            raise
        size = FONT_FLOOR
    sub_h = SUB_ZONE if sub else 0
    area_h = h - LABEL_ZONE - sub_h
    if area_h <= 0:
        raise ValueError("cell too short for a picture and its label: %.2f in" % h)
    iw, ih = png_size(pic)
    ax, ay = x + w / 2, y + LABEL_ZONE + sub_h + area_h / 2          # centre of the image area
    if visible:
        # Size by the visible equipment (transparent margins ignored) so that it fills `fill`
        # of the area in the limiting dimension; the image file is placed unchanged.
        l, t, r, b = visible_box(pic)
        vw, vh = (r - l) * iw, (b - t) * ih
        shown_w = min(w * fill, area_h * fill * vw / vh)
        pw, ph = shown_w / (r - l), shown_w * vh / vw / (b - t)
        img = page.image(ax - (l + r) / 2 * pw, ay - (1 - (t + b) / 2) * ph, pw, ph, pic, parent, key=key)
    else:
        pw = min(w, area_h * iw / ih)
        ph = pw * ih / iw
        img = page.image(x + (w - pw) / 2, y + LABEL_ZONE + sub_h + (area_h - ph) / 2, pw, ph, pic, parent, key=key)
    txt = page.text(x, y + sub_h, w, LABEL_ZONE, label, parent, size=size, valign=0, bold=bold)
    out = [img, txt]
    if sub:
        try:
            ssize = fit_size(sub, w, SUB_ZONE + 0.04, LABEL_SIZES)
        except TextFitError:
            ssize = FONT_FLOOR
        out.append(page.text(x, y, w, SUB_ZONE + 0.04, sub, parent, size=ssize, valign=0, color=SUB_COLOR))
    return out


def draw_component(page, comps, cid, x, y, w, h, suffix="", qty=1, parent=None):
    """Draw component `cid` in the cell (x, y, w, h) (inches, bottom-left origin). Returns the ids of the shapes added."""
    comp = comps.get(cid)
    label = comp["label"] + suffix
    key = "%s|qty=%d" % (comp["id"], qty)
    pic = comps.picture_path(cid)
    if pic is None:
        size = fit_size(label, w, h, BOX_SIZES)
        return [page.rect("icon", x, y, w, h, parent, fill=BOX_FILL, line=BOX_LINE, lw=0.75, text=label, size=size, key=key)]
    return draw_picture(page, pic, label, x, y, w, h, key, parent)
