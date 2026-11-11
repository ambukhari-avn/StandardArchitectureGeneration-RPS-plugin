# Diagram file format (diagram.json)

One JSON file describes one A3 page. `scripts/build_diagram.py` draws it. Nothing is enforced except the footer and the cable styles.
All positions and sizes are inches, measured from the **top-left corner of the drawing area** (x to the right, y downwards).
The drawing area is 15.9 in wide and 9.9 in high; the footer sits below it.

This is the **free-form format**. New diagrams are normally written in the meaning-based **v2 format** ([diagram-format-v2.md](diagram-format-v2.md),
`"spec_version": 2`): the AI lists items, levels, scopes and links, and `scripts/compile_v2.py` turns that into a file of exactly this kind
(`build_diagram.py --emit-v1 out.json` saves it). A free-form file builds on its own, unchanged, and has no question gate (it only warns).

```json
{
  "project": {"client": "...", "project": "...", "doc_name": "...",
              "prepared_by": "...", "checked_by": "...", "approved_by": "...", "rev": "..."},
  "notes": ["optional footer note", "another"],
  "shapes": [ ... ],
  "lines":  [ ... ]
}
```

## project (footer)
Only values the user or the RFQ gave. A missing value prints `TBC` (`doc_name` and `rev` default to `Architecture` and `R0/1`).
Size is always A3. A value too long for its footer cell stops the build.

The footer follows the approved Avanceon template: **Client**, Project, Documentation Name, Prepared by, Checked by, Approved by, Size, Rev/Sheet,
Notes, then a fixed scope legend (grey "Avanceon Scope", pink "Client Scope") and the cable legend. `client` is the key for the Client cell;
the older key `end_user` still works. `contractor` is still accepted (older files carry it) but is **not printed**: the approved footer
has no Contractor cell.

## shapes
| field | meaning |
|---|---|
| `id` | required, unique |
| `kind` | `box` (default), `zone` (background rectangle with a title, drawn behind everything), `text` (no border), `ellipse` (the fibre-ring outline, see below) |
| `label` | text shown in the box / under the picture / as the zone title |
| `x`, `y` | required, top-left corner |
| `w`, `h` | size; defaults: box 1.35 x 0.55, picture 1.0 x 0.95, text 1.5 x 0.3; zones and ellipses must give them |
| `component` | id from `data/components.json`: the library picture (a box if it has none) |
| `image`, `image_source`, `image_match` | path to a picture (PNG; WebP, JPEG or GIF are converted if Pillow is installed), where it came from (needed: its absence warns), and `exact` or `generic`. A plain white background is removed when Pillow is installed (library pictures are never changed). The footer notes how many pictures came from outside the library |
| `dashed`, `fill`, `bold`, `italic`, `size` | optional look: dashed outline, `#RRGGBB` fill, bold or italic text, font size in pt (never below 6) |
| `line`, `lw` | optional outline colour `#RRGGBB` and weight in pt (0.25 to 3) |
| `level` | optional `L0` ... `L5`; only used for the report: a level 0 shape left without a picture prints `BOX: no picture found for <label>` |

### kind `ellipse` (fibre ring)
`{"id": "ring", "kind": "ellipse", "label": "Fiber Optic Ring", "x": 2, "y": 3, "w": 6, "h": 1.2}`. One closed outline, drawn as a polygon of
72 points (the first point is repeated at the end), in the style of the `fibre` cable (green, dashed), filled `#E5F7E8` unless `fill` is given,
with the label in bold 8 pt in the middle. `cable` may name another cable id. Lines may end on it: give them a `points` route that finishes on
the outline (a line to the ellipse is not reported as passing through it). It is the only ring graphic; a ring is never drawn unless asked for.


## lines
`{"from": "a", "to": "b", "cable": "ethernet"}`. `cable` is one of the five ids below; its colour, dash and arrowhead come from
`data/cable_types.json` (the Avanceon drawing-instructions document) and cannot be set per line, so every diagram uses the same look
and the footer legend always agrees with the drawn lines.

| `cable` | drawn as | legend text |
|---|---|---|
| `hardwired` | black, solid, **arrowhead at the `to` end** (so `from` = signal source, `to` = destination) | Hardwired (Inst Cable) |
| `ethernet` | blue, dashed | Ethernet Cable |
| `modbus` | red, solid | Modbus Cable |
| `fibre` | green, dashed (a closed loop only for a ring) | Fibre Optic Cable |
| `bacnet` | purple, solid | BACnet Cable |

Optional fields:
- `"label": "Modbus RTU"` - a small text (6.5 pt, white backing) at the middle of the longest segment. Use it for the protocol or
  signal where it matters (`Modbus RTU` / `Modbus TCP`, `OPC UA`, `4-20 mA`). A `modbus` line without a label gives a warning.
- `"via": [[x, y], ...]` - forces the square-cornered route through points (same coordinates as shapes) to go round something.
- `"points": [[x, y], ...]` - a fully explicit route (at least two points, same coordinates as shapes); the program does not route it.
  Use it for parallel lines or lines that must end on a curve.
The legend lists only the cable types used, in table order.

## What the program does when something is off
- Stops (`NOT BUILT`): a line names an unknown shape or cable; a shape has no id, x or y; unknown component; unreadable file.
- Repairs and warns: a shape outside the drawing area is moved in; a picture that is missing or not a PNG becomes a box; a label too
  long for its box is printed at 6 pt; two shapes overlapping; a line passing through a shape; a picture without `image_source`, under 120 px,
  or whose background could not be removed; a `modbus` line without a label.

Every drawing carries a small grey stamp under the footer, `RPS Architecture plugin v<version> | spec v<1|2>`, and the same text in the file's
properties.
