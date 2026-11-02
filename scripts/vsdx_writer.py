"""Shape model + .vsdx emitter. Standard library only.

A .vsdx is an OPC zip of XML. To stay inside what Visio accepts, the package skeleton (styles, theme, windows,
content types) is taken from an existing Visio-made file passed as `base`; only the page contents, page size and
core properties are replaced. The page is always A3 landscape - anything else is refused.
"""
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

A3_W, A3_H = 16.5354, 11.6929      # inches, A3 landscape (420 x 297 mm)
FONT_FLOOR = 6.0                    # pt, legibility floor (configurable by callers that check against it)


class Page:
    """Flat list of shapes in inches, origin bottom-left, y up. Later shapes draw on top."""

    def __init__(self, w=A3_W, h=A3_H):
        self.w, self.h, self.shapes = w, h, []

    def add(self, kind, role, x, y, w, h, parent=None, **kw):
        s = dict(id=len(self.shapes) + 1, kind=kind, role=role, x=x, y=y, w=w, h=h, parent=parent, fill=None,
                 line="#000000", lw=0.75, pattern=1, text="", size=6.5, bold=False, halign=1, valign=1, key=None,
                 pts=None)
        s.update(kw)
        self.shapes.append(s)
        return s["id"]

    def rect(self, role, x, y, w, h, parent=None, **kw):
        return self.add("rect", role, x, y, w, h, parent, **kw)

    def text(self, x, y, w, h, text, parent=None, **kw):
        return self.add("rect", "text", x, y, w, h, parent, fill=None, line=None, text=text, **kw)

    def image(self, x, y, w, h, path, parent=None, **kw):
        """Place a PNG picture (stored once in the package, referenced by relationship)."""
        png_size(path)                              # fail now if it is not a PNG
        return self.add("image", "icon", x, y, w, h, parent, image=path, **kw)

    def line(self, pts, color, pattern=1, lw=1.0, parent=None, key=None):
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return self.add("line", "line", min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), parent,
                        pts=pts, line=color, lw=lw, pattern=pattern, key=key)


def _f(v):
    return repr(round(v, 6))


def png_size(path):
    """(width_px, height_px) of a PNG; raises ValueError for anything else."""
    with open(path, "rb") as fh:
        head = fh.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        raise ValueError("%s is not a PNG file" % path)
    return struct.unpack(">II", head[16:24])


def _image_shape_xml(s, rid):
    x, y, w, h = s["x"], s["y"], s["w"], s["h"]
    c = ["<Cell N='PinX' V='%s'/>" % _f(x + w / 2), "<Cell N='PinY' V='%s'/>" % _f(y + h / 2),
         "<Cell N='Width' V='%s'/>" % _f(w), "<Cell N='Height' V='%s'/>" % _f(h),
         "<Cell N='LocPinX' V='%s' F='Width*0.5'/>" % _f(w / 2), "<Cell N='LocPinY' V='%s' F='Height*0.5'/>" % _f(h / 2),
         "<Cell N='ImgOffsetX' V='0' F='ImgWidth*0'/>", "<Cell N='ImgOffsetY' V='0' F='ImgHeight*0'/>",
         "<Cell N='ImgWidth' V='%s' F='Width*1'/>" % _f(w), "<Cell N='ImgHeight' V='%s' F='Height*1'/>" % _f(h)]
    sec = ""
    if s["key"]:
        sec = "<Section N='User'><Row N='SourceKey'><Cell N='Value' V='%s' U='STR'/></Row></Section>" % escape(str(s["key"]), {"'": "&apos;"})
    g = ("<Section N='Geometry' IX='0'><Cell N='NoFill' V='0'/><Cell N='NoLine' V='0'/><Cell N='NoShow' V='0'/><Cell N='NoSnap' V='0'/>"
         "<Row T='MoveTo' IX='1'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row>"
         "<Row T='LineTo' IX='2'><Cell N='X' V='%s' F='Width*1'/><Cell N='Y' V='0'/></Row>"
         "<Row T='LineTo' IX='3'><Cell N='X' V='%s' F='Width*1'/><Cell N='Y' V='%s' F='Height*1'/></Row>"
         "<Row T='LineTo' IX='4'><Cell N='X' V='0'/><Cell N='Y' V='%s' F='Height*1'/></Row>"
         "<Row T='LineTo' IX='5'><Cell N='X' V='0'/><Cell N='Y' V='0'/></Row></Section>") % (_f(w), _f(w), _f(h), _f(h))
    fd = "<ForeignData ForeignType='Bitmap' CompressionType='PNG'><Rel r:id='%s'/></ForeignData>" % rid
    return "<Shape ID='%d' Type='Foreign' LineStyle='0' FillStyle='0' TextStyle='0'>%s%s%s%s</Shape>" % (
        s["id"], "".join(c), sec, g, fd)


def shape_xml(s, rid=None):
    if s["kind"] == "image":
        return _image_shape_xml(s, rid)
    x, y, w, h = s["x"], s["y"], s["w"], s["h"]
    c = ["<Cell N='PinX' V='%s'/>" % _f(x + w / 2), "<Cell N='PinY' V='%s'/>" % _f(y + h / 2),
         "<Cell N='Width' V='%s'/>" % _f(w), "<Cell N='Height' V='%s'/>" % _f(h),
         "<Cell N='LocPinX' V='%s' F='Width*0.5'/>" % _f(w / 2), "<Cell N='LocPinY' V='%s' F='Height*0.5'/>" % _f(h / 2)]
    line = s["line"]
    filled = s["fill"] is not None and s["kind"] != "line"
    c += ["<Cell N='LinePattern' V='%d'/>" % (0 if line is None else s["pattern"]),
          "<Cell N='LineColor' V='%s'/>" % (line or "#000000"), "<Cell N='LineWeight' V='%s'/>" % _f(s["lw"] / 72),
          "<Cell N='FillPattern' V='%d'/>" % (1 if filled else 0), "<Cell N='FillForegnd' V='%s'/>" % (s["fill"] or "#FFFFFF")]
    c += ["<Cell N='%s' V='0.02'/>" % n for n in ("LeftMargin", "RightMargin", "TopMargin", "BottomMargin")]
    c.append("<Cell N='VerticalAlign' V='%d'/>" % s["valign"])
    sec = ""                                    # section order matches Visio's own files: Character, Paragraph, User, Geometry
    if s["text"]:
        sec += ("<Section N='Character'><Row IX='0'><Cell N='Color' V='#000000'/><Cell N='Style' V='%d'/>"
                "<Cell N='Size' V='%s'/></Row></Section>" % (1 if s["bold"] else 0, _f(s["size"] / 72)))
        sec += "<Section N='Paragraph'><Row IX='0'><Cell N='HorzAlign' V='%d'/></Row></Section>" % s["halign"]
    if s["key"]:
        rows = "<Row N='SourceKey'><Cell N='Value' V='%s' U='STR'/></Row>" % escape(str(s["key"]), {"'": "&apos;"})
        sec += "<Section N='User'>%s</Section>" % rows
    g = ("<Section N='Geometry' IX='0'><Cell N='NoFill' V='%d'/><Cell N='NoLine' V='%d'/><Cell N='NoShow' V='0'/>"
         "<Cell N='NoSnap' V='0'/>" % (0 if filled else 1, 1 if line is None else 0))
    if s["kind"] == "rect":
        rows = [("MoveTo", 0, 0, "", ""), ("LineTo", 1, 0, "Width*1", ""), ("LineTo", 1, 1, "Width*1", "Height*1"),
                ("LineTo", 0, 1, "", "Height*1"), ("LineTo", 0, 0, "", "")]
        for i, (t, ax, ay, fx, fy) in enumerate(rows, 1):
            g += "<Row T='%s' IX='%d'><Cell N='X' V='%s'%s/><Cell N='Y' V='%s'%s/></Row>" % (
                t, i, _f(ax * w), " F='%s'" % fx if fx else "", _f(ay * h), " F='%s'" % fy if fy else "")
    else:                                       # polyline
        for i, (px, py) in enumerate(s["pts"], 1):
            g += "<Row T='%s' IX='%d'><Cell N='X' V='%s'/><Cell N='Y' V='%s'/></Row>" % (
                "MoveTo" if i == 1 else "LineTo", i, _f(px - x), _f(py - y))
    g += "</Section>"
    txt = "<Text><pp IX='0'/><cp IX='0'/>%s</Text>" % escape(s["text"]) if s["text"] else ""
    return "<Shape ID='%d' Type='Shape' LineStyle='0' FillStyle='0' TextStyle='0'>%s%s%s%s</Shape>" % (
        s["id"], "".join(c), sec, g, txt)


def write_vsdx(page, out, base, title="Architecture"):
    if abs(page.w - A3_W) > 0.01 or abs(page.h - A3_H) > 0.01:
        raise ValueError("page is %.3f x %.3f in; output must be A3 landscape (%.4f x %.4f)" % (page.w, page.h, A3_W, A3_H))
    images = {}                                 # source path -> (relationship id, media part name); each file stored once
    for s in page.shapes:
        if s["kind"] == "image" and s["image"] not in images:
            n = len(images) + 1
            images[s["image"]] = ("rId%d" % n, "image%d.png" % n)
    xml = ("<?xml version='1.0' encoding='utf-8' ?>\n<PageContents xmlns='http://schemas.microsoft.com/office/visio/2012/main' "
           "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' xml:space='preserve'><Shapes>"
           + "".join(shape_xml(s, images[s["image"]][0] if s["kind"] == "image" else None) for s in page.shapes)
           + "</Shapes></PageContents>")
    ET.fromstring(xml.encode("utf-8"))          # fail here, not in Visio, if the XML is malformed
    page_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/'
                 'package/2006/relationships">' + "".join(
                     '<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                     'Target="../media/%s"/>' % v for v in images.values()) + "</Relationships>")
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>%s</dc:title>'
            '</cp:coreProperties>' % escape(title))
    cx, cy = page.w / 2, page.h / 2
    view = lambda t: re.sub(r"ViewCenterY='[^']*'", "ViewCenterY='%s'" % cy, re.sub(r"ViewCenterX='[^']*'", "ViewCenterX='%s'" % cx, t))
    with zipfile.ZipFile(base) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in zin.infolist():
            n, data = i.filename, zin.read(i.filename)
            if n.startswith(("visio/media/", "visio/embeddings/")) or n == "docProps/thumbnail.emf":
                continue                        # nothing from the base file's drawing is carried over
            if n == "visio/pages/page1.xml":
                data = xml.encode("utf-8")
            elif n == "visio/pages/_rels/page1.xml.rels":
                data = page_rels.encode()
            elif n == "[Content_Types].xml" and images and not re.search(r"Extension=[\"']png[\"']", data.decode()):
                data = data.decode().replace("</Types>", '<Default Extension="png" ContentType="image/png"/></Types>').encode()
            elif n == "docProps/core.xml":
                data = core.encode()
            elif n == "_rels/.rels":
                data = re.sub(r"<Relationship [^>]*thumbnail[^>]*/>", "", data.decode()).encode()
            elif n == "visio/pages/pages.xml":
                t = data.decode()
                t = re.sub(r"(N='PageWidth' V=')[^']*", r"\g<1>%s" % page.w, t)
                t = re.sub(r"(N='PageHeight' V=')[^']*", r"\g<1>%s" % page.h, t)
                data = view(t).encode()
            elif n == "visio/windows.xml":
                data = view(data.decode()).encode()
            zo.writestr(n, data)
        for path, (_, part) in images.items():
            with open(path, "rb") as fh:
                zo.writestr("visio/media/" + part, fh.read())
