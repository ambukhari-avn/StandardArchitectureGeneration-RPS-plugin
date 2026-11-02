"""Minimal .xlsx reader. Standard library only (an .xlsx is a zip of XML).

    sheets(path)               -> [(name, state)]            state is 'visible' or 'hidden'
    read_sheet(path, name, max_row=None) -> {(row, col): value}   1-based; numbers as float, text as str; cached values only
    sheet_geometry(path, name) -> (default_row_height_pt, {row: height_pt})
    drawing_pictures(path, name) -> pictures anchored on the sheet (see below)
"""
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
EMU_PER_PT = 12700


def _rels(z, part):
    d, f = posixpath.split(part)
    rel = posixpath.join(d, "_rels", f + ".rels")
    if rel not in z.namelist():
        return {}
    return {r.get("Id"): posixpath.normpath(posixpath.join(d, r.get("Target"))) if not r.get("Target").startswith("/")
            else r.get("Target").lstrip("/") for r in ET.fromstring(z.read(rel))}


def _sheet_part(z, name):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    for s in wb.find(_M + "sheets"):
        if s.get("name") == name:
            return _rels(z, "xl/workbook.xml")[s.get(_R + "id")]
    raise KeyError("no sheet named %r" % name)


def sheets(path):
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        return [(s.get("name"), s.get("state", "visible")) for s in wb.find(_M + "sheets")]


def _col(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def read_sheet(path, name, max_row=None):
    """Cell values of a sheet. With max_row, reading stops after that row (cheap header discovery on huge sheets)."""
    with zipfile.ZipFile(path) as z:
        part = _sheet_part(z, name)
        sst = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_M + "si"):
                sst.append("".join(t.text or "" for t in si.iter(_M + "t")))
        cells = {}
        with z.open(part) as fh:
            for _, el in ET.iterparse(fh, events=("end",)):
                if el.tag != _M + "row":
                    continue
                for c in el.findall(_M + "c"):
                    v, t = c.find(_M + "v"), c.get("t")
                    if t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(_M + "t"))
                    elif v is None or v.text is None:
                        continue
                    elif t == "s":
                        val = sst[int(v.text)]
                    elif t in ("str", "e", "b"):
                        val = v.text
                    else:
                        val = float(v.text)
                    m = re.match(r"([A-Z]+)(\d+)", c.get("r"))
                    cells[(int(m.group(2)), _col(m.group(1)))] = val
                rnum = int(el.get("r", 0))
                el.clear()
                if max_row is not None and rnum >= max_row:
                    break
        return cells


def sheet_geometry(path, name):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read(_sheet_part(z, name)))
    fmt = root.find(_M + "sheetFormatPr")
    default = float(fmt.get("defaultRowHeight", 15)) if fmt is not None else 15.0
    heights = {int(r.get("r")): float(r.get("ht", default)) for r in root.iter(_M + "row")}
    return default, heights


def drawing_pictures(path, name):
    """Pictures anchored on the sheet, in drawing order (later = drawn on top).

    Each is {'media': 'xl/media/imageN.png', 'order': i, 'top_pt': float, 'bottom_pt': float, 'col': int}
    with positions measured from the top of the sheet using the real row heights, so a picture can be
    assigned to the row it visually sits in (its anchor row alone is not reliable for tall pictures).
    """
    with zipfile.ZipFile(path) as z:
        part = _sheet_part(z, name)
        root = ET.fromstring(z.read(part))
        drawing, legacy = root.find(_M + "drawing"), root.find(_M + "legacyDrawing")
        default, heights = sheet_geometry(path, name)
        top_of, y = {}, 0.0
        for r in range(1, max(heights) + 3):
            top_of[r] = y
            y += heights.get(r, default)
        out = []
        if legacy is not None:                       # old-style (VML) pictures, e.g. vector .emf symbols pasted into Excel
            vpart = _rels(z, part)[legacy.get(_R + "id")]
            vrels = _rels(z, vpart)
            vml = z.read(vpart).decode("utf-8", "replace")
            for i, m in enumerate(re.finditer(r"<v:shape\s.*?</v:shape>", vml, re.S)):
                rid, anchor = re.search(r'o:relid="([^"]+)"', m.group(0)), re.search(r"<x:Anchor>([^<]+)</x:Anchor>", m.group(0))
                if not (rid and anchor and rid.group(1) in vrels):
                    continue
                lc, _, tr, to, _, _, br, bo = [int(v) for v in anchor.group(1).split(",")]
                out.append({"media": vrels[rid.group(1)], "order": 1000 + i, "top_pt": top_of[tr + 1] + to * 0.75,
                            "bottom_pt": top_of[br + 1] + bo * 0.75, "col": lc})
        if drawing is None:
            return out
        dpart = _rels(z, part)[drawing.get(_R + "id")]
        drels = _rels(z, dpart)
        for i, anc in enumerate(ET.fromstring(z.read(dpart))):
            pic = anc.find(_XDR + "pic")
            if pic is None:
                continue
            blip = pic.find(".//" + _A + "blip")
            f, t = anc.find(_XDR + "from"), anc.find(_XDR + "to")
            gi = lambda e, k: int(e.find(_XDR + k).text)
            top = top_of[gi(f, "row") + 1] + gi(f, "rowOff") / EMU_PER_PT
            if t is not None:
                bottom = top_of[gi(t, "row") + 1] + gi(t, "rowOff") / EMU_PER_PT
            else:
                bottom = top + int(anc.find(_XDR + "ext").get("cy")) / EMU_PER_PT
            out.append({"media": drels[blip.get(_R + "embed")], "order": i, "top_pt": top, "bottom_pt": bottom,
                        "col": gi(f, "col")})
        return out


def row_at(pt, path, name):
    """Row (1-based) containing vertical position `pt` points from the top of the sheet."""
    default, heights = sheet_geometry(path, name)
    y = 0.0
    for r in range(1, max(heights) + 3):
        h = heights.get(r, default)
        if y <= pt < y + h:
            return r
        y += h
    return None
