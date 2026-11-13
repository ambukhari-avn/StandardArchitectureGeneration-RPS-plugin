"""Three rounded footer cards matching the supplied November reference."""
import os
import footer as F
from reference_layout import NAVY, BORDER, BODY, CLIENT, ORANGE
from vsdx_writer import A3_H, A3_W, png_size


def build(page, fields, legend, notes, allow_tbc, logo_path, logo_text, parent):
    if abs(page.w - A3_W) > .01 or abs(page.h - A3_H) > .01:
        raise F.FooterError("page must be A3 landscape")
    f = F._check_fields(fields, allow_tbc)
    F._check_legend(legend)
    x, y, h, gap = F.X0, F.Y0, F.HEIGHT, .18
    widths = (6.7, 4.35, F.X1 - F.X0 - 6.7 - 4.35 - 2 * gap)
    cards = []
    for name, w in zip(("title", "notes", "legend"), widths):
        cards.append(page.rect("block", x, y, w, h, parent, fill="#FFFFFF", line=BORDER, lw=1.5, rounding=.13, key="footer-card:" + name))
        x += w + gap
    title, notes_id, legend_id = cards
    sizes = {}
    logo_w, text_x = 1.55, F.X0 + 1.68
    if logo_path:
        if not os.path.exists(logo_path):
            raise F.FooterError("logo file not found: %s" % logo_path)
        iw, ih = png_size(logo_path)
        pw = logo_w - .12
        ph = pw * ih / iw
        if ph > h - .2:
            ph, pw = h - .2, (h - .2) * iw / ih
        page.image(F.X0 + (logo_w - pw) / 2 + .04, y + (h - ph) / 2, pw, ph, logo_path, title, key="logo")
    else:
        page.text(F.X0 + .06, y + .3, logo_w - .1, .45, logo_text, title, size=12, bold=True, color=NAVY)
    page.line([(F.X0 + logo_w, y + .04), (F.X0 + logo_w, y + h - .04)], "#BDD8ED", lw=.5, parent=title, key="footer-logo-divider")
    text_w = widths[0] - 1.78
    # Metadata remains complete even though the reference omits End User.
    metadata = [("client", "Client", f["client"], .29),
                ("project", "Project Name", f["project"], .34)]
    if f["end_user"] != "TBC":
        metadata[0] = ("client", "Client / End User", f["client"] + " / " + f["end_user"], .29)
    cy = y + h - .045
    for key, label, value, cell_h in metadata:
        label_h = .115
        page.text(text_x, cy - label_h, text_w, label_h, label, title, size=6.3, bold=True, halign=0, valign=1, key="footer-label:" + key)
        value_h = cell_h - label_h
        size = F._fit(value, text_w, value_h, (7.5, 7, 6.5, 6), what="footer field '%s'" % key)
        page.text(text_x, cy - cell_h, text_w, value_h, value, title, size=size, halign=0, valign=2, key="footer-value:" + key)
        sizes[key] = size
        cy -= cell_h
    # Document name and approval fields share the bottom strip, with light dividers.
    fields_row = [("doc_name", "Document Name", f["doc_name"], 1.60),
                  ("prepared_by", "Prepared by", f["prepared_by"], .69),
                  ("checked_by", "Checked by", f["checked_by"], .69),
                  ("approved_by", "Approved by", f["approved_by"], .69),
                  ("revision", "Size / Rev / Sheet", "A3 - %s / %s" % (f["revision"], f["sheet"]), text_w - 3.67)]
    cell_y, cell_h, cx = y + .04, .30, text_x
    for index, (key, label, value, w) in enumerate(fields_row):
        if index:
            page.line([(cx - .025, cell_y), (cx - .025, cell_y + cell_h)], "#BDD8ED", lw=.5, parent=title)
        label_size = F._fit(label, w - .04, .13, (6.5, 6), True, "footer label")
        size = F._fit(value, w - .04, cell_h - .13, (7, 6.5, 6), what="footer field '%s'" % key)
        page.text(cx, cell_y + cell_h - .13, w - .04, .13, label, title, size=label_size, bold=True, halign=0)
        page.text(cx, cell_y, w - .04, cell_h - .13, value, title, size=size, halign=0, valign=2, key="footer-value:" + key)
        sizes[key] = size
        cx += w
    nx = F.X0 + widths[0] + gap
    page.text(nx + .12, y + h - .23, widths[1] - .24, .18, "Notes", notes_id, size=8, bold=True, halign=0)
    body = "\n".join("%d) %s" % (i, F._clean(n)) for i, n in enumerate(notes, 1))
    if body:
        size = F._fit(body, widths[1] - .24, h - .32, (7.5, 7, 6.5, 6), what="notes")
        page.text(nx + .12, y + .06, widths[1] - .24, h - .32, body, notes_id, size=size, halign=0, valign=2)
        sizes["notes"] = size
    lx, lw = nx + widths[1] + gap, widths[2]
    page.text(lx + .12, y + h - .23, lw - .24, .18, "Legend", legend_id, size=8, bold=True, halign=0)
    # Scopes are part of the legend card rather than a fourth footer block.
    scope_w = min(1.7, lw * .44)
    for i, (key, (label, fill)) in enumerate(F.SCOPE.items()):
        sy = y + h - .47 - i * .25
        page.rect("icon", lx + .13, sy, .31, .18, legend_id, fill=fill,
                  line=ORANGE if key == "other" else BORDER, lw=1.2, rounding=.04, key="scope:" + key)
        page.text(lx + .50, sy, scope_w - .4, .18, label, legend_id, size=6.5, halign=0, valign=1)
    cable_x = lx + scope_w + .15
    cable_w = lw - scope_w - .27
    # Five standard cables fit in one column; larger custom legends use two.
    cols = 1 if len(legend) <= 5 else 2
    col_w = cable_w / cols
    row_h = min(.18, (h - .31) / max(1, min(5, len(legend))))
    for i, entry in enumerate(legend):
        col, row = divmod(i, 5)
        ex, ey = cable_x + col * col_w, y + h - .43 - row * row_h
        if entry.get("kind", "line") == "line":
            page.line([(ex, ey + .075), (ex + .32, ey + .075)], entry["color"], entry.get("pattern", 1), 1.75, legend_id, key="legend:" + entry["label"])
        else:
            page.rect("icon", ex, ey, .30, .15, legend_id, fill=entry["color"], line=BORDER, lw=1.)
        size = F._fit(entry["label"], col_w - .42, .17, (7, 6.5, 6), what="legend entry")
        page.text(ex + .4, ey, col_w - .42, .17, entry["label"], legend_id, size=size, halign=0)
    return {"top": F.TOP, "block": title, "sizes": sizes}
