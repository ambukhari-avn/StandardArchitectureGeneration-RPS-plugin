"""Draw one dataset component into a cell of the page. Standard library only.

  * with a picture in the dataset -> the picture (true aspect ratio, centred) with its label underneath;
  * without                       -> a rectangle with the label inside (decisions D8).
The label is always the dataset label, plus an optional suffix such as "-01" for numbered copies; callers
cannot pass free text. If the label does not fit at or above the font floor, TextFitError is raised.
"""
from textfit import TextFitError, fit_size
from vsdx_writer import FONT_FLOOR, png_size

LABEL_SIZES = (7, 6.5, 6)
BOX_SIZES = (8, 7, 6.5, 6)
LABEL_ZONE = 0.30                 # inches reserved under a picture for its label (three lines at 6 pt)
BOX_FILL, BOX_LINE = "#F2F2F2", "#404040"


def draw_picture(page, pic, label, x, y, w, h, key, parent=None, soft=False):
    """A picture (PNG path) in the cell, true aspect ratio, centred, with `label` underneath.
    soft: a label that does not fit is printed at the font floor instead of raising TextFitError."""
    try:
        size = fit_size(label, w, LABEL_ZONE, LABEL_SIZES)
    except TextFitError:
        if not soft:
            raise
        size = FONT_FLOOR
    area_h = h - LABEL_ZONE
    if area_h <= 0:
        raise ValueError("cell too short for a picture and its label: %.2f in" % h)
    iw, ih = png_size(pic)
    pw = min(w, area_h * iw / ih)
    ph = pw * ih / iw
    img = page.image(x + (w - pw) / 2, y + LABEL_ZONE + (area_h - ph) / 2, pw, ph, pic, parent, key=key)
    txt = page.text(x, y, w, LABEL_ZONE, label, parent, size=size, valign=0)
    return [img, txt]


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
