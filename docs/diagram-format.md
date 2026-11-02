# Diagram file format (diagram.json)

One JSON file describes one A3 page. `scripts/build_diagram.py` draws it. Nothing is enforced except the footer and the cable colours.
All positions and sizes are inches, measured from the **top-left corner of the drawing area** (x to the right, y downwards).
The drawing area is 15.9 in wide and 9.9 in high; the footer sits below it.

```json
{
  "project": {"end_user": "...", "contractor": "...", "project": "...", "doc_name": "...",
              "prepared_by": "...", "checked_by": "...", "approved_by": "...", "rev": "..."},
  "notes": ["optional footer note", "another"],
  "shapes": [ ... ],
  "lines":  [ ... ]
}
```

## project (footer)
Only values the user or the RFQ gave. A missing value prints `TBC` (`doc_name` and `rev` default to `Architecture` and `R0/1`).
Size is always A3. A value too long for its footer cell stops the build.

## shapes
| field | meaning |
|---|---|
| `id` | required, unique |
| `kind` | `box` (default), `zone` (background rectangle with a title, drawn behind everything), `text` (no border) |
| `label` | text shown in the box / under the picture / as the zone title |
| `x`, `y` | required, top-left corner |
| `w`, `h` | size; defaults: box 1.35 x 0.55, picture 1.0 x 0.95, text 1.5 x 0.3; zones must give them |
| `component` | id from `data/components.json`: the library picture (a box if it has none) |
| `image`, `image_source` | path to a picture (PNG; WebP, JPEG or GIF are converted if Pillow is installed) and where it came from; the footer notes it |
| `dashed`, `fill`, `bold`, `size` | optional look: dashed outline, `#RRGGBB` fill, bold text, font size in pt (never below 6) |

## lines
`{"from": "a", "to": "b", "cable": "ethernet"}` - plain lines, no arrows or labels. `cable` is one of `ethernet`, `fibre`, `modbus`,
`bacnet`, `hardwired`; the colour comes from `data/cable_types.json` and cannot be set here, so every diagram uses the same colours.
The line is straight or has square corners. Optional `"via": [[x, y], ...]` forces it through points (same coordinates as shapes) to
route round something. The legend lists the cable types used.

## What the program does when something is off
- Stops (`NOT BUILT`): a line names an unknown shape or cable; a shape has no id, x or y; unknown component; unreadable file.
- Repairs and warns: a shape outside the drawing area is moved in; a picture that is missing or not a PNG becomes a box; a label too
  long for its box is printed at 6 pt; two shapes overlapping; a line passing through a shape.
