"""Import the client's component workbook -> data/components.json, data/icons/<id>.png, docs/dataset-import-report.md.

    python scripts/import_dataset.py <system_architecture_dataset.xlsx>

Rules (see docs/decisions.md D8, D9, D17):
  * The client's text is kept as supplied (leading/trailing whitespace trimmed, nothing else changed).
  * A component gets a picture only if a picture sits in its row. Where several pictures are stacked in
    one row, the top-most one (last in drawing order) is the one Excel shows, so it is the one used;
    the others are listed in the report, not exported.
  * Rows that are exact repeats (same layer, title, brand, part number) share one id; the later rows
    point at the first with `duplicate_of`.
Standard library only.
"""
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xlsx_reader

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SHEET = "Components"
HEADERS = {"layer": "layer", "item title": "title", "oem / brand": "brand", "part number / model": "part_number",
           "part-number confidence": "confidence", "image file name": "image_file_name"}


# ---- pure helpers (unit-tested) --------------------------------------------------------------------------------
def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def base_id(title):
    """Id stem from a title; a trailing/embedded '(...)' note is not part of the name."""
    return slug(re.sub(r"\([^)]*\)", " ", title)) or "component"


def _model_token(part_number):
    for tok in re.split(r"[\s/()]+", part_number or ""):
        t = re.sub(r"[^A-Za-z0-9]", "", tok)
        if len(t) >= 4 and any(ch.isdigit() for ch in t):
            return t.lower()
    return ""


def assign_ids(rows):
    """rows: dicts with layer, title, brand, part_number, source_row. Returns [(id, duplicate_of_or_None)] in row order.

    A title that is unique keeps the plain id. Colliding titles all get '_brand', then '_model', then '_row<N>'.
    Ids do not depend on row order, so they stay stable if rows are re-ordered.
    """
    ident = lambda r: (r["layer"], r["title"].lower(), (r["brand"] or "").lower(), re.sub(r"\W", "", (r["part_number"] or "").lower()))
    canon, first = [], {}
    for i, r in enumerate(rows):
        k = ident(r)
        if k not in first:
            first[k] = i
            canon.append(i)
    stem = {i: base_id(rows[i]["title"]) for i in canon}
    ids = {}
    groups = {}
    for i in canon:
        groups.setdefault(stem[i], []).append(i)
    for s, members in groups.items():
        if len(members) == 1:
            ids[members[0]] = s
            continue
        cand = {i: s + ("_" + slug(rows[i]["brand"]) if rows[i]["brand"] else "") for i in members}
        if len(set(cand.values())) < len(members):
            cand = {i: cand[i] + ("_" + _model_token(rows[i]["part_number"]) if _model_token(rows[i]["part_number"]) else "") for i in members}
        if len(set(cand.values())) < len(members):
            cand = {i: cand[i] + "_" + slug(rows[i]["layer"]) for i in members}
        if len(set(cand.values())) < len(members):
            cand = {i: s + "_row%d" % rows[i]["source_row"] for i in members}
        ids.update(cand)
    if len(set(ids.values())) != len(ids):
        raise ValueError("could not make component ids unique")
    out = []
    for i, r in enumerate(rows):
        k = ident(r)
        if first[k] == i:
            out.append((ids[i], None))
        else:
            out.append((ids[first[k]] + "_row%d" % r["source_row"], ids[first[k]]))
    return out


def top_picture_per_row(pictures_with_rows):
    """[(row, picture_dict)] -> {row: (chosen_picture, [hidden_pictures])}; chosen = highest drawing order."""
    by = {}
    for row, p in pictures_with_rows:
        by.setdefault(row, []).append(p)
    return {r: (max(ps, key=lambda p: p["order"]), sorted([p for p in ps], key=lambda p: p["order"])[:-1]) for r, ps in by.items()}


def emf_to_png(data, dpi=600):
    """Render a vector .emf/.wmf symbol to a PNG with a transparent background (Pillow, import time only; Windows renders EMF)."""
    try:
        import io
        from PIL import Image, ImageDraw
    except ImportError:
        raise SystemExit("the workbook has .emf symbols; importing them needs Pillow (pip install pillow) on Windows")
    im = Image.open(io.BytesIO(data))
    im.load(dpi=dpi)
    im = im.convert("RGBA")
    for xy in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
        if im.getpixel(xy)[:3] != (255, 255, 255) and min(im.getpixel(xy)[:3]) < 250:
            continue
        ImageDraw.floodfill(im, xy, (255, 255, 255, 0), thresh=6)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


# ---- import ----------------------------------------------------------------------------------------------------
def run(xlsx, root=ROOT):
    cells = xlsx_reader.read_sheet(xlsx, SHEET)
    maxr = max(r for r, _ in cells)
    hdr = {}
    for (r, c), v in cells.items():
        if r == 1 and isinstance(v, str) and v.strip().lower() in HEADERS:
            hdr[HEADERS[v.strip().lower()]] = c
    missing = [h for h in HEADERS.values() if h not in hdr]
    if missing:
        raise ValueError("workbook header row lacks column(s): %s" % ", ".join(missing))
    def txt(r, k):
        v = cells.get((r, hdr[k]))
        if isinstance(v, float):
            v = str(int(v)) if v == int(v) else repr(v)
        return (v.strip() or None) if isinstance(v, str) else None
    rows = []
    for r in range(2, maxr + 1):
        row = {k: txt(r, k) for k in hdr}
        if not (row["layer"] or row["title"]):
            continue
        if not (row["layer"] and row["title"]):
            raise ValueError("row %d has a layer or a title but not both" % r)
        row["source_row"] = r
        rows.append(row)
    ids = assign_ids(rows)

    pics = xlsx_reader.drawing_pictures(xlsx, SHEET)
    located = []
    for p in pics:
        centre = (p["top_pt"] + p["bottom_pt"]) / 2
        located.append((xlsx_reader.row_at(centre, xlsx, SHEET), p))
    chosen = top_picture_per_row(located)

    icons_dir = os.path.join(root, "data", "icons")
    os.makedirs(icons_dir, exist_ok=True)
    for f in os.listdir(icons_dir):
        if f.lower().endswith(".png"):
            os.remove(os.path.join(icons_dir, f))
    comps, by_row_id = [], {}
    with zipfile.ZipFile(xlsx) as z:
        for row, (cid, dup) in zip(rows, ids):
            c = {"id": cid, "layer": row["layer"], "title": row["title"], "label": row["title"], "brand": row["brand"],
                 "part_number": row["part_number"], "confidence": row["confidence"], "image_file_name": row["image_file_name"],
                 "picture": None, "duplicate_of": dup, "source_row": row["source_row"]}
            comps.append(c)
            by_row_id[row["source_row"]] = c
        # a picture belongs to the canonical component of its row's group
        canon = {c["id"]: c for c in comps if not c["duplicate_of"]}
        hidden_report, orphan_rows = [], []
        for srow, (pic, hidden) in sorted(chosen.items()):
            c = by_row_id.get(srow)
            if c is None:
                orphan_rows.append(srow)
                continue
            target = canon[c["duplicate_of"]] if c["duplicate_of"] else c
            if target["picture"]:
                hidden_report.append((srow, "second picture for an already-pictured component, not used"))
                continue
            dest = os.path.join(icons_dir, target["id"] + ".png")
            with open(dest, "wb") as fh:
                fh.write(emf_to_png(z.read(pic["media"])) if pic["media"].lower().endswith((".emf", ".wmf")) else z.read(pic["media"]))
            target["picture"] = "icons/%s.png" % target["id"]
            if hidden:
                hidden_report.append((srow, "%d stacked picture(s) underneath were not used: %s" % (
                    len(hidden), ", ".join(os.path.basename(h["media"]) for h in hidden))))
        referenced = {p["media"] for p in pics}
        media_all = [n for n in z.namelist() if n.startswith("xl/media/")]
    data = {"source": {"file": os.path.basename(xlsx), "sheet": SHEET}, "components": comps}
    with open(os.path.join(root, "data", "components.json"), "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    write_report(root, xlsx, comps, hidden_report, orphan_rows, len(media_all) - len(referenced))
    return comps


def write_report(root, xlsx, comps, hidden_report, orphan_rows, unused_media):
    layers = {}
    for c in comps:
        layers[c["layer"]] = layers.get(c["layer"], 0) + 1
    pic = [c for c in comps if c["picture"]]
    named_no_pic = [c for c in comps if c["image_file_name"] and not c["picture"] and not c["duplicate_of"]]
    pic_no_name = [c for c in pic if not c["image_file_name"]]
    dups = [c for c in comps if c["duplicate_of"]]
    paren = [c for c in comps if "(" in c["title"] and not c["duplicate_of"]]
    L = ["# Dataset import report", "",
         "Generated by `scripts/import_dataset.py` from `%s` (sheet `%s`). Facts only; nothing here changes the client's data." % (
             os.path.basename(xlsx), SHEET), "",
         "- Rows imported: **%d** (%d distinct components, %d exact repeats)" % (len(comps), len(comps) - len(dups), len(dups)),
         "- Components with a picture: **%d**; drawn as a box (no picture): **%d**" % (len(pic), len(comps) - len(dups) - len(pic)),
         "- Layer labels (%d): %s" % (len(layers), "; ".join("%s (%d)" % kv for kv in sorted(layers.items()))), "",
         "## Pictures",
         "- Rule: the picture whose vertical centre lies in the row; if several are stacked in a row the top-most is used.",
         "- Rows with stacked pictures: %s" % ("; ".join("row %d: %s" % h for h in hidden_report) or "none"),
         "- Pictures whose row has no component: %s" % (", ".join(map(str, orphan_rows)) or "none"),
         "- Image files in the workbook not attached to any picture (not used): %d" % unused_media,
         "- Rows that name an image file but have no picture (drawn as boxes): %d" % len(named_no_pic),
         "- Rows with a picture but no image file name: %s" % (", ".join("%d (%s)" % (c["source_row"], c["title"]) for c in pic_no_name) or "none"), "",
         "## Exact repeats (same layer, title, brand, part number)",
         "\n".join("- row %d repeats `%s`" % (c["source_row"], c["duplicate_of"]) for c in dups) or "- none", "",
         "## Titles containing a bracket (used verbatim as the label)",
         "\n".join("- row %d: %s" % (c["source_row"], c["title"]) for c in paren) or "- none", ""]
    with open(os.path.join(root, "docs", "dataset-import-report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    comps = run(sys.argv[1])
    print("imported %d rows, %d with a picture; see docs/dataset-import-report.md" % (len(comps), sum(1 for c in comps if c["picture"])))
