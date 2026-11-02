"""Development aid: draw a Page as a PNG so a layout can be looked at without Visio. Needs Pillow (not used by the plugin itself)."""
from PIL import Image, ImageDraw, ImageFont

DPI = 100


def _font(pt):
    try:
        return ImageFont.truetype("arial.ttf", max(6, int(pt * DPI / 72)))
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


def render(page, path):
    W, H = int(page.w * DPI), int(page.h * DPI)
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    X = lambda v: v * DPI
    Y = lambda v: H - v * DPI
    for s in page.shapes:
        if s["kind"] == "image":
            pic = Image.open(s["image"]).convert("RGBA").resize((max(1, int(s["w"] * DPI)), max(1, int(s["h"] * DPI))))
            im.paste(pic, (int(X(s["x"])), int(Y(s["y"] + s["h"]))), pic)
        elif s["kind"] == "line":
            pts = [(X(x), Y(y)) for x, y in s["pts"]]
            for p, q in zip(pts, pts[1:]):
                if s["pattern"] == 2:                                   # dashed
                    n = max(1, int(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 / 8))
                    for i in range(0, n, 2):
                        d.line([(p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n),
                                (p[0] + (q[0] - p[0]) * min(i + 1, n) / n, p[1] + (q[1] - p[1]) * min(i + 1, n) / n)], fill=s["line"], width=max(1, int(s["lw"] * 1.3)))
                else:
                    d.line([p, q], fill=s["line"], width=max(1, int(s["lw"] * 1.3)))
        else:
            box = [X(s["x"]), Y(s["y"] + s["h"]), X(s["x"] + s["w"]), Y(s["y"])]
            if s["fill"] or s["line"]:
                d.rectangle(box, fill=s["fill"], outline=s["line"], width=1)
            if s["text"]:
                f = _font(s["size"])
                lines = _wrap(d, s["text"], f, box[2] - box[0] - 4)
                lh = f.size * 1.15
                y = box[1] + (box[3] - box[1] - lh * len(lines)) / 2 if s["valign"] == 1 else (box[3] - lh * len(lines) if s["valign"] == 0 else box[1])
                for ln in lines:
                    w = d.textlength(ln, font=f)
                    x = box[0] + 2 if s["halign"] == 0 else (box[2] - w - 2 if s["halign"] == 2 else (box[0] + box[2] - w) / 2)
                    d.text((x, y), ln, fill="black", font=f)
                    y += lh
    im.save(path)
