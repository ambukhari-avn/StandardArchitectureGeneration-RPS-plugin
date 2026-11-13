# Diagram file format (diagram.json)

One JSON file describes one A3 page. `scripts/build_diagram.py` draws it. The default is the boxed reference layout described in [reference-layout.md](reference-layout.md); `layout_style: "legacy"` retains exact-position compatibility.
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
The footer has three rounded cards: logo/metadata, Notes, and Legend. **Avanceon Scope** (pale/white) and **Client Scope** (pale orange with an orange border) appear as swatches inside Legend. Client and a known End User share an entry; Size / Rev / Sheet share the bottom entry.
Size is always A3. A value too long for its footer cell stops the build.

## shapes
| field | meaning |
|---|---|
| `id` | required, unique |
| `kind` | `box` (default: device picture with caption), `zone` (legacy positioned background), `group` (rounded equipment container; title at top, or centred when empty), `pill` (legacy, not drawn), `text` (no border) |
| `label` | caption under the picture (bold) / the zone or group title / the pill text. A second line (`\n`) or `sublabel` is printed under it in blue, e.g. "SCADA Server" + "(Primary)" |
| `sublabel` | optional blue second caption line |
| `x`, `y` | required for unlayered positioned shapes; omitted for automatic reference groups/devices; reference positions inside layers are computed |
| `w`, `h` | natural device size, default 1.35 x 1.25; groups in the reference layout are sized to their contents and allocated layer space |
| `parent` | id of a containing group; inherits its layer, supports nested groups |
| `columns`, `row` | group grid columns (1–24); optional zero-based explicit row on a child |
| `placement`, `width_weight` | a requested separate control panel uses `placement: "beside"`; width_weight sets relative root-group width |
| `solid`, `max_width`, `max_height` | solid group outline for an I/O frame; maximum root summary dimensions in inches |
| `component` | id from `data/components.json`: the library picture; missing pictures warn and get a generic icon |
| `image`, `image_source` | picture path and provenance (PNG; WebP/JPEG/GIF are converted with Pillow); source is recorded on the picture shape |
| `background` | `auto` (default): remove a uniform light backdrop, preserve existing alpha and trim. `keep`: preserve the source background. Complex/dark backgrounds in auto mode are retained with a warning; obtain a transparent product original instead. |
| `dashed`, `fill`, `bold`, `size` | optional look: dashed outline, `#RRGGBB` fill, bold text, font size in pt (never below 6) |
| `layer` | optional standard layer id (see layers); `x` becomes optional and `y` is ignored |
| `scope` | optional `avanceon` or `other`: fills a box or zone with the matching footer scope colour (an explicit `fill` wins; pictures are not coloured) |

## lines
`{"from": "a", "to": "b", "cable": "ethernet"}` names devices or groups. `cable` is one of `ethernet`, `fibre`, `modbus`,
`bacnet`, `hardwired`; the colour comes from `data/cable_types.json` and cannot be set here, so every diagram uses the same colours.
The line is straight or has square corners. Optional `"via": [[x, y], ...]` forces it through points (same coordinates as shapes) to
route round something. The legend lists the cable types used.
In the default reference style, links across boxes attach to container borders. Field-to-I/O hardwired connections share one visible trunk per source group and target rack. Original logical endpoints remain recorded. Set top-level `cable_detail: "individual"` or per-line `individual: true` to restore individual wires. Manual route instructions also bypass grouping. Explicit group endpoints remain exactly as specified.

## pictures (every device, instruments and third-party items included)
Every device shows a picture, never a box with text. Give it `component` (a library id) or `image` (a PNG from the web; WebP/JPEG/GIF are converted
if Pillow is installed) with `image_source`. **Instruments and field devices, third-party items and VM boxes are devices too and get pictures.**
Every picture, library or web, is cleaned before it is drawn: a white or light-grey background becomes transparent (white *inside* the device is
kept), it is trimmed and capped at 2400 px. Existing transparency is preserved. A device with no usable picture gets a generic device icon and a warning, never a plain box. Picture wrappers explicitly disable inherited fill, outline and shadow. Scope styling belongs on group containers, never on the device's picture.

## layers (Purdue bands)
`"layers": ["scada", "control", "field"]` - the standard layers the drawing needs (any of 1 to 6 of: `enterprise`, `dmz`, `operations`,
`scada`, `control`, `field`). Layers use standard order. Separate rounded light-blue heading cards and pale equipment panels have navy text and blue borders. Heights follow content; the PLC/control area gets a larger allowance. Small gaps separate layers. `layer_weights` overrides proportions, e.g. `{"scada":2,"control":5,"field":2}`. `layer_headers` overrides names/descriptions, e.g. `{"control":{"name":"Control System","description":"Redundant PLC"}}`.
Put a group in a layer with `"layer": "control"` and its devices in it with `parent`. Nested groups, columns and rows organise complex controls above I/O. Loose devices are boxed automatically. A separately requested panel is a control root group with `placement: "beside"`; it is never inserted automatically. See [reference-layout.md](reference-layout.md) for complete rules and `samples/reference_boxed.json` for a working example. Older equal-height placement is only available through `layout_style: "legacy"`.

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

## Page size is fixed
The page is always A3 landscape. Coordinates, `via` points or ring boxes that fall outside the drawing area are pulled back inside and reported in `warnings`; the page never grows.



## Cabling rules (automatic)
Every cable in `lines` is routed by the program, so a prompt only needs `from`, `to` and `cable`:
- square corners only; leaves and enters each device at a right angle, ON its edge, facing the other device when that is shortest;
- never through a device (it goes round); straight when the devices line up, otherwise as few bends as possible;
- in a layered drawing (devices in rows) cables run as drop - track - drop: leave by the top or bottom, run along their own track in the free band between the rows (tracks ordered to avoid crossings), enter by the top or bottom; neighbours in a row get one straight cable; devices that are not in rows use a grid router;
- parallel cables take separate tracks; several cables on one side of a device are spread along that side;
- unavoidable crossings are drawn as a small hop (the horizontal cable hops over the vertical one); T-junctions are not hopped;
- in a layered drawing cables stay out of the dark-blue band.
Manual instructions always win, per cable: `"from_side"` / `"to_side"` (`left`, `right`, `top`, `bottom`), `"via": [[x, y], ...]` (followed exactly, corners squared), `"straight": true` (prefer a straight cable). FO ring node links keep their own look.


## Look and feel (reference style)
- Version 1.1.0 follows `reference-style.png` for headers, three-card footer, nested boxes and varied layer heights. Palette and hierarchy are detailed in [reference-layout.md](reference-layout.md). Cable colours are unchanged.
- Internal dashed pattern `2` exports as Visio tiny-dash pattern `23` (see `reference-dashes.png`); PNG previews approximate it with 2.5 pt strokes / 1.25 pt gaps. Picture wrappers disable inherited fill, outline and shadow.
- Match `docs/reference-style.png` for visual treatment, using the current project's equipment and topology. Cables and ring links are 1.75 pt, panel/layer boundaries 1.5 pt, outer border 2.25 pt. Preview rendering uses 200 dpi, bold fonts, proportional strokes, dashed containers and Lanczos picture resampling.
- Picture cleanup keeps up to 2400 pixels, preserves existing alpha and device interior whites, and never upscales small pictures. Choose sharp manufacturer originals at 300 source pixels per displayed inch. Background removal is for uniform light product backdrops, not arbitrary scenes. Use `--preview` and inspect the image before delivery.
- A blue frame surrounds the sheet; a bold blue **title** (`"title"` in the file, default the Document Name) sits in a strip above the layers.
- Heading cards use project-relevant names (SCADA, Control System, Field Instruments by default), optionally overridden with layer_headers. Equipment boxes are adjacent to their heading cards.
- Group scope `other` uses the pale-orange client/existing-system treatment. Avanceon groups use pale/white backgrounds. Footer swatches match them.
- A group title is bold navy at the top, or centred for an empty system-summary group. Use solid frames for I/O racks.
- Grouped instrument hardwiring is one black box-to-box trunk into each I/O rack; individual logical device connections are retained in source metadata.
