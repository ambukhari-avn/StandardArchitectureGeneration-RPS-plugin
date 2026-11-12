# Diagram file format (diagram.json)

One JSON file describes one A3 page. `scripts/build_diagram.py` draws it. Nothing is enforced except the footer and the cable colours.
All positions and sizes are inches, measured from the **top-left corner of the drawing area** (x to the right, y downwards).
The drawing area is 15.9 in wide and 9.9 in high; the footer sits below it.

```json
{
  "project": {"end_user": "...", "client": "...", "project": "...", "doc_name": "...",
              "prepared_by": "...", "checked_by": "...", "approved_by": "...", "revision": "...", "sheet": "..."},
  "notes": ["optional footer note", "another"],
  "shapes": [ ... ],
  "lines":  [ ... ]
}
```

## project (footer)
Only values the user or the RFQ gave. A missing value prints `TBC` (`doc_name`, `revision` and `sheet` default to `Architecture`, `R0` and `1`). The older keys `contractor` and `rev` (`R0/1`) are still read as `client` and `revision` + `sheet`.
The footer also always shows two fixed scope boxes between Notes and Legend: **Avanceon Scope** (light blue) and **Other Scope** (light green).
Size is always A3. A value too long for its footer cell stops the build.

## shapes
| field | meaning |
|---|---|
| `id` | required, unique |
| `kind` | `box` (default: a **device**, always drawn as its picture with the caption underneath, never as a box), `zone` (background rectangle with a title, drawn behind everything), `group` (dashed rounded container with a blue title pill, e.g. "Redundant PLC System"; needs `w`, `h`), `pill` (a light-blue label, e.g. "Field Instruments & Devices", that may sit on a line), `text` (no border) |
| `label` | caption under the picture (bold) / the zone or group title / the pill text. A second line (`\n`) or `sublabel` is printed under it in blue, e.g. "SCADA Server" + "(Primary)" |
| `sublabel` | optional blue second caption line |
| `x`, `y` | required, top-left corner |
| `w`, `h` | size; defaults: device 1.35 x 1.25, text 1.5 x 0.3, pill sized to its text; zones and groups must give them |
| `component` | id from `data/components.json`: the library picture (a box if it has none) |
| `image`, `image_source` | path to a picture (PNG; WebP, JPEG or GIF are converted if Pillow is installed) and where it came from; the footer notes it |
| `dashed`, `fill`, `bold`, `size` | optional look: dashed outline, `#RRGGBB` fill, bold text, font size in pt (never below 6) |
| `layer` | optional standard layer id (see layers); `x` becomes optional and `y` is ignored |
| `scope` | optional `avanceon` or `other`: fills a box or zone with the matching footer scope colour (an explicit `fill` wins; pictures are not coloured) |

## lines
`{"from": "a", "to": "b", "cable": "ethernet"}` - plain lines, no arrows or labels. `cable` is one of `ethernet`, `fibre`, `modbus`,
`bacnet`, `hardwired`; the colour comes from `data/cable_types.json` and cannot be set here, so every diagram uses the same colours.
The line is straight or has square corners. Optional `"via": [[x, y], ...]` forces it through points (same coordinates as shapes) to
route round something. The legend lists the cable types used.

## pictures (every device, instruments and third-party items included)
Every device shows a picture, never a box with text. Give it `component` (a library id) or `image` (a PNG from the web; WebP/JPEG/GIF are converted
if Pillow is installed) with `image_source`. **Instruments and field devices, third-party items and VM boxes are devices too and get pictures.**
Every picture, library or web, is cleaned before it is drawn: a white or light-grey background becomes transparent (white *inside* the device is
kept), it is trimmed and shrunk to at most 700 px. A device with no usable picture gets a generic device icon and a warning, never a plain box.
A `scope` colours a rounded tile behind the picture and caption.

## layers (Purdue bands)
`"layers": ["scada", "control", "field"]` - the standard layers the drawing needs (any of 1 to 6 of: `enterprise`, `dmz`, `operations`,
`scada`, `control`, `field`; names, order and style come from `data/layers.json` and the program, not the file). Each is drawn as a pale
rounded panel with a dark-blue band on the left carrying its name in white. **The layers always divide the whole drawing area equally**, top to
bottom in the standard order (Enterprise at the top, Field at the bottom), so 2 layers are tall, 6 are shorter, and no space is left empty
under the last one.
Put a shape in a layer with `"layer": "scada"`. Its `y` is ignored: it is centred in the layer. Shapes of a layer are spread **evenly across
its width in the order listed** (give every shape of the layer an `x` to keep your own positions instead). A shape too tall or too many
shapes too wide for the layer are reduced to fit (never below half size; the font floor still applies) with a warning if very crowded.
Shapes with a `scope` get a thin dark-blue outline so they stand out on the panel. Shapes without `layer` are placed as before.

## rings (fibre ring)
`{"id": "fo1", "label": "Fiber Optic Ring", "cable": "fibre", "nodes": ["plc", "rio1", "rio2", "..."]}`
Draws the approved fibre-ring illustration: one **dashed light-green ellipse** (the ring's cable colour, label inside, default
"Fiber Optic Ring") with a short straight link from every listed element to it, in the same colour and dash as the ring (fibre: green dashed). Elements **above** the ring join its top, elements **below**
join its bottom. List every element the request connects to the ring in `nodes` (2 or more, any number, in connection order: main PLC /
first node, RIO-1, RIO-2, ... last RIO); an element with its own ring switch is listed as that switch.
Place the elements in one or two rows with a clear gap between the rows (at least 1.2 in): the ellipse is sized to the nodes and drawn in that gap.
With one row only, the ellipse is drawn below it (above it if there is no room). Optional `x`, `y`, `w`, `h` (all four, same coordinates as
shapes) fix the ellipse yourself. Do not draw the ring as your own shape: use `rings`.

## What the program does when something is off
- Stops (`NOT BUILT`): a line names an unknown shape or cable; a shape has no id, x or y; unknown component; unreadable file.
- Repairs and warns: a shape outside the drawing area is moved in; a picture that is missing or not a PNG becomes a box; a label too
  long for its box is printed at 6 pt; two shapes overlapping; a line passing through a shape.
