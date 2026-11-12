"""Development aid: draw a Page as a PNG so a layout can be looked at without Visio. Needs Pillow (not used by the plugin itself)."""
from PIL import Image, ImageDraw, ImageFont
import math
import os
from vsdx_writer import DASH_PT, GAP_PT

DPI = 200


def _font(pt, bold=False):
    try:
        face = "arialbd.ttf" if bold else "arial.ttf"
        font_path = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", face)
        return ImageFont.truetype(font_path if os.path.exists(font_path) else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), max(6, int(pt * DPI / 72)))
    except OSError:
        return ImageFont.load_default()


def _wrap(d, text, font, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            t = (line + " " + word).strip()
            if line and d.textlength(t, font=font) > width:
                out.append(line)
                line = word
            else:
                line = t
        out.append(line)
    return out


def _dashed_outline(draw, box, shape, color, stroke, rounding=0):
    left, top, right, bottom = box
    if shape == "ellipse":
        cx, cy = (left + right) / 2, (top + bottom) / 2
        rx, ry = (right - left) / 2, (bottom - top) / 2
        pts = [(cx + rx * math.cos(i * math.pi / 180), cy + ry * math.sin(i * math.pi / 180)) for i in range(361)]
    elif rounding:
        radius = min(rounding, (right - left) / 2, (bottom - top) / 2)
        pts = []
        for cx, cy, start in ((right - radius, top + radius, -90), (right - radius, bottom - radius, 0),
                              (left + radius, bottom - radius, 90), (left + radius, top + radius, 180)):
            pts.extend((cx + radius * math.cos(math.radians(start + i)), cy + radius * math.sin(math.radians(start + i))) for i in range(0, 91, 5))
        pts.append(pts[0])
    else:
        pts = [(left, top), (right, top), (right, bottom), (left, bottom), (left, top)]
    _dashed_path(draw, pts, color, stroke)


def _dashed_path(draw, pts, color, stroke):
    dash, gap, distance = DASH_PT * DPI / 72, GAP_PT * DPI / 72, 0.0
    period = dash + gap
    for p, q in zip(pts, pts[1:]):
        length = math.dist(p, q)
        at = 0.0
        while at < length - 1e-8:
            phase = (distance + at) % period
            step = min(length - at, (dash if phase < dash else period) - phase)
            if step < 1e-8:
                step = min(length - at, 1e-6)
            if phase < dash:
                draw.line([(p[0] + (q[0] - p[0]) * at / length, p[1] + (q[1] - p[1]) * at / length),
                           (p[0] + (q[0] - p[0]) * (at + step) / length, p[1] + (q[1] - p[1]) * (at + step) / length)], fill=color, width=stroke)
            at += step
        distance += length


def render(page, path):
    W, H = int(page.w * DPI), int(page.h * DPI)
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    X = lambda v: v * DPI
    Y = lambda v: H - v * DPI
    for s in page.shapes:
        if s["kind"] == "image":
            pic = Image.open(s["image"]).convert("RGBA").resize((max(1, int(s["w"] * DPI)), max(1, int(s["h"] * DPI))), Image.Resampling.LANCZOS)
            im.paste(pic, (int(X(s["x"])), int(Y(s["y"] + s["h"]))), pic)
        elif s["kind"] == "line":
            pts = [(X(x), Y(y)) for x, y in s["pts"]]
            stroke = max(1, round(s["lw"] * DPI / 72))
            if s["pattern"] == 2:
                _dashed_path(d, pts, s["line"], stroke)
            else:
                d.line(pts, fill=s["line"], width=stroke)
            if s.get("arrow") and len(pts) > 1:                                 # filled arrowhead on the last point
                (px_, py_), (qx, qy) = pts[-2], pts[-1]
                L = max(1e-6, ((qx - px_) ** 2 + (qy - py_) ** 2) ** 0.5)
                ux, uy = (qx - px_) / L, (qy - py_) / L
                a, b = DPI * 0.09, DPI * 0.04
                d.polygon([(qx, qy), (qx - a * ux + b * uy, qy - a * uy - b * ux), (qx - a * ux - b * uy, qy - a * uy + b * ux)], fill=s["line"])
        else:
            box = [X(s["x"]), Y(s["y"] + s["h"]), X(s["x"] + s["w"]), Y(s["y"])]
            stroke = max(1, round(s["lw"] * DPI / 72))
            outline = None if s["pattern"] == 2 else s["line"]
            if s["kind"] == "poly":
                d.polygon([(X(px), Y(py)) for px, py in s["pts"]], fill=s["fill"], outline=s["line"])
                continue
            if s["kind"] == "rect" and s.get("rounding") and (s["fill"] or s["line"]):
                d.rounded_rectangle(box, radius=s["rounding"] * DPI, fill=s["fill"], outline=outline, width=stroke)
            elif s["kind"] == "ellipse":
                d.ellipse(box, fill=s["fill"], outline=outline, width=stroke)
            elif s["fill"] or s["line"]:
                d.rectangle(box, fill=s["fill"], outline=outline, width=stroke)
            if s["line"] and s["pattern"] == 2:
                _dashed_outline(d, box, s["kind"], s["line"], stroke, s["rounding"] * DPI)
            if s["text"] and s.get("text_angle"):                       # rotated text (layer names)
                f = _font(s["size"], s["bold"])
                w_ = int(d.textlength(s["text"], font=f)) + 4
                tile = Image.new("RGBA", (w_, int(f.size * 1.6)), (0, 0, 0, 0))
                ImageDraw.Draw(tile).text((2, 1), s["text"], fill="white", font=f)
                tile = tile.rotate(s["text_angle"], expand=True)
                im.paste(tile, (int((box[0] + box[2] - tile.width) / 2), int((box[1] + box[3] - tile.height) / 2)), tile)
            elif s["text"]:
                f = _font(s["size"], s["bold"])
                lines = _wrap(d, s["text"], f, box[2] - box[0] - 4)
                lh = f.size * 1.15
                y = box[1] + (box[3] - box[1] - lh * len(lines)) / 2 if s["valign"] == 1 else (box[3] - lh * len(lines) if s["valign"] == 0 else box[1])
                for ln in lines:
                    w = d.textlength(ln, font=f)
                    x = box[0] + 2 if s["halign"] == 0 else (box[2] - w - 2 if s["halign"] == 2 else (box[0] + box[2] - w) / 2)
                    d.text((x, y), ln, fill=s.get("color", "#000000"), font=f)
                    y += lh
    im.save(path, dpi=(DPI, DPI))
