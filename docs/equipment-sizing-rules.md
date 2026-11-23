# Equipment sizing and picture-fit rules (1.5.0)

These rules apply to every device picture in the default reference layout: SCADA components, PLCs, I/O racks and field instruments. They supplement `mandatory-drawing-rules.md` and never override the approved topology, quantities, fixed artwork, cable colours, line weights, layer order, footer or editable Visio output. Read and apply them before planning the layout and again when inspecting the preview.

## A. Size and allocation

1. **Fill the available space.** Size equipment to fill the space it is given. Do not leave tiny pictures inside large, mostly empty containers.
2. **Equal image areas per row.** Devices in the same row each receive an equal share of the usable row width and the same image-area height. A nested group is weighted by the devices it holds, so a four-rack block gets four equal shares.
3. **Proportional enlargement.** Each picture is fitted to the largest size that fits its allocated area with its aspect ratio preserved. Never stretch or distort a device to fill both dimensions.
4. **Visible bounds.** Size by the visible equipment. Ignore transparent margins and blank background when calculating the displayed size. The approved fixed image files stay unchanged (they are placed byte-for-byte; only the placement is calculated from the visible bounds).
5. **80–90 % occupancy.** Target 90 % of the image area in the limiting dimension: a tall transmitter nearly fills the available height, a wide rack nearly fills the available width.
6. **No default maximum.** Default device width and height are only relative weights. The final size comes from the space actually left after layout. `max_width` / `max_height` still apply only to a root block that was explicitly requested compact.

## B. Consistency

7. **Comparable devices look alike.** Devices with the same component or picture share one displayed cell size (both PLCs equal, all eight I/O racks equal). Field instruments share one cell height. Different equipment types stay naturally proportioned because every picture is fitted by its own aspect ratio.
8. **Captions and cables first.** The caption zone (and the blue second line) is reserved beneath every picture, separate and readable. Rows keep a clear cable channel (0.16 in) between them and a small edge clearance, with no further empty space.

## C. Containers and layers

9. **Expand nested groups.** Nested groups use the full width and height inside their container. A four-rack block spans its PLC-system container with four evenly spaced, clearly visible rack images.
10. **Balance layer heights around equipment.** A layer's height follows what it must hold (picture rows, captions, titles). A system-summary box with no devices (for example Existing SCADA) is kept shallow. Reduce unnecessary blank space rather than shrinking equipment to satisfy an arbitrary layer proportion. `layer_weights` can still override.

## D. Image quality and verification

11. **Sharp sources.** Prefer high-resolution originals. Enlarging a low-resolution picture adds no detail. The builder warns with the pixels per displayed inch of every picture below 200 (web pictures below 150) and names approved fixed images it leaves unchanged. Report every remaining limitation to the user.
12. **Verify the A3 preview before delivery.** Check that all equipment is clearly recognisable at normal page-view size, comparable devices match, and no pictures, captions or cables overlap. The builder warns when equipment is displayed under 0.80 in across ("equipment is only ... in across"): treat it as too small and rebuild with fewer items per row, a higher `layer_weights` value for that layer, or a different `columns` / `row` split.
13. **Preserve the existing requirements.** Enlargement keeps the approved topology, equipment quantities, fixed artwork, cable colours, line weights, layer order, footer and editable Visio output unchanged.

## Where the rules live in the code

| Rules | Code |
|---|---|
| 1, 2, 6, 9 | `place()` in `scripts/reference_layout.py` (row heights by weight, equal width shares, no scale cap) |
| 3, 4, 5 | `draw_picture(..., fill, visible)` and `visible_box()` in `scripts/draw.py`; `FILL` in `reference_layout.py` |
| 7 | `equalise()` in `scripts/reference_layout.py` |
| 8 | `CHANNEL`, `EDGE`, `LABEL_ZONE` |
| 10 | layer weights in `apply_layers()` |
| 11, 12 | quality and size warnings in `draw_shape()` in `scripts/build_diagram.py` (`SMALL_EQUIPMENT`) |
