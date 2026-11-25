# Boxed reference layout (1.7.0)

The current default follows `reference-style.png`. Bold white layer names, turned 90 degrees, sit in a vertical navy heading strip (#001477) on the left of each full-width pale layer frame (#F5FAFF, blue border #27369B); every strip has the same width and stays inside its frame (7.2). Other equipment headings remain navy (#073878). Client/existing-system groups use pale orange (#FFE5B5) and orange borders (#FF8800). Cable colours and their solid/dashed classifications remain unchanged in `data/cable_types.json`.

## Layout and hierarchy

Start from `samples/reference_boxed.json`. Set `layers` to required standard ids in any order; the builder uses standard top-to-bottom order. Each layer has one full-width frame with its vertical heading strip on the left; an optional description is a second, smaller rotated line inside the strip (all strips then widen equally). Equipment blocks span the layer to the right of the strip and use its full height. Heights follow the rows of equipment and captions each layer must hold plus routing room for its cables (7.3). Long names are fitted on one line or split at a word; a name that cannot fit stops the build. Control has a larger default allowance; `layer_weights` can tune it, for example `{"scada": 2, "control": 5, "field": 2}`. No layer is forced to equal another.

Use `layer_headers` to override display text, e.g. `{"control": {"name": "Control System", "description": "Redundant PLC"}}`. Default headings omit Purdue level numbers; include one in the name if requested.

Create a `kind: "group"` shape with a `layer`, then give its device shapes `parent: "group-id"`. Child shapes inherit the parent's layer. Groups may themselves have parents. The program fits children in a grid: `columns` (1–24) sets a group column count; zero-based `row` on children makes explicit rows. Children in the same explicit row share that row. Device pictures are enlarged to fill their share of the container (equal shares per row, aspect ratio preserved, about 90 % occupancy); see `equipment-sizing-rules.md`. Crowded layouts warn instead of silently hiding content. Parent cycles, missing parents, invalid options and conflicting layers stop the build.

Root groups are arranged left-to-right. `width_weight` allocates relative width. A requested separate panel uses `placement: "beside"` on a root group in the control layer; it is placed to the right of main PLC equipment. This works for any separately requested panel. The builder never invents one. `solid: true` makes a group border solid, suitable for an I/O rack box. **One common I/O box per PLC system:** put all racks of a system in one group (solid, e.g. `columns: 4`) and give no rack a box of its own; if a group holds only racks that receive field wiring, it becomes that common box automatically. Keep the PLC in a row above the I/O group. Fewer boxes (7.4): Avanceon equipment sits directly in its layer (`"frame": false` groups arrange it invisibly); visible boxes only for panels/cabinets, several independent PLC systems, client scope, sites or process areas, security zones, the field-instrument group and a common solid I/O box when several racks are drawn. The build reports an unnecessary box as a defect. `max_width` and `max_height` (inches) limit root block dimensions only when a compact box is explicitly requested; otherwise root blocks fill the layer space.

Loose layer devices are placed in a generated invisible arrangement (no box); field instruments and client-scope devices keep a visible group. Existing/external system summaries may be empty labelled groups: their labels are centred. Actual devices still require pictures. No component model, wiring or footer value is inferred from the style reference.

Positions inside this layout are computed by the group system; do not mix absolute x/y assumptions with parent-relative grid placement. For old exact-position drawings, `layout_style: "legacy"` preserves the previous layer placement and footer.

## Box-to-box cables

Specify the actual logical lines as usual. Explicit group endpoints are kept exactly as given. Device links crossing between containers attach to the outside boxes; internal connections remain within a shared box. Parallel non-hardwired connections remain separate.

`cable_detail: "grouped"` is the default. For hardwired instrument lines from the field layer to the same control-layer I/O rack, the program draws one visible line per source field container and target rack. It frames the rack automatically if needed. All original instrument-to-rack endpoint pairs remain in the JSON and in the visible line's `User.SourceKey` metadata after `|logical=`. Distinct source groups and distinct racks are not combined.

To show every individual device line, set `cable_detail: "individual"`. Per-line `individual: true` preserves just that line. Manual `via`, `from_side`, `to_side` or `straight` instructions also preserve that connection individually. The router ignores an endpoint container's own children when finding its outside attachment, while keeping other devices clear. Cable colours come only from the cable standard; the reference image's cable colours do not override it.

## Footer

Three joined rectangular sections with shared blue borders and no gaps: logo/project/document metadata; Notes; Legend. The legend includes both scope swatches and the cable samples. Labels/headings are bold and metadata values regular. Client and a supplied End User share one entry; the bottom strip holds Document Name, Prepared by, Checked by, Approved by, and Size / Rev / Sheet. Missing supplied values use TBC; normal document/revision/sheet defaults remain supported. Text fitting enforces the 6 pt floor. The page remains A3 landscape.

Picture transparency, the 2400 px cap, compact dashes and black-frame prevention from earlier versions are retained. `--preview` remains required for visual inspection. Automated checks exercise both this default and legacy layout compatibility. Native Visio display has not been verified for this release.


## Cable clearance (1.6.0)
- Between rows or side-by-side boxes that a cable runs between, the layout leaves a band wide enough for about 7 mm clearance from both borders (0.50 in rows, 0.45 in columns). A container whose devices are linked past a neighbour gets a clear band above and below its row. Layer gaps leave room for labels.
- The router prefers 8 mm from devices (falling back to 4 mm, then the minimum), avoids running along box and layer borders, keeps a cable between two devices of one container inside that container, keeps clear of group titles, and separates parallel runs by about 4 mm where the band allows. Unavoidable crossings are drawn as hops.
- Cable labels are placed away from crossings, devices, other labels and box/layer borders.
- Devices are measured at their picture and caption (not the empty cell around them), so cables attach to the equipment.


## Control-layer order, representative I/O and checks (Phases 7-8)
`scripts/arch_spec.py to-diagram` places control equipment top to bottom as FO patch panels, switches, PLCs (primary and secondary side by side), I/O; absent equipment leaves no empty row. A representative rack (equivalent racks in a star or on a backplane, or when the user chose the simplified display) is one picture captioned with the total quantity and has no box. Lines accept `"arrows": "none" | "end" | "both"`; hardwired signals default to an arrow at the I/O. After routing, cables sharing a track or an attachment point are moved onto their own parallel track, and `qa.py` checks every build (see `defect:` lines). The header/footer geometry and logo are locked in `data/template_lock.json`.

## Engine layout (1.7.2)

- **Functional rows in every layer**: control (I/O racks, PLCs, switches with FO panels at the ends), SCADA (servers, clients, network); relative `place` constraints (`left_of`, `right_of`) reorder a row.
- **Heights by requirement**: each layer first receives what its minimum picture sizes, captions, cable channels (at least 0.45 in), buses and hardwired labels need; spare space is then shared by content. If the page cannot fit, the compact arrangement merges rows.
- **Corridors and attachment**: a cable stays inside the layers of its two ends (its corridor), starts and ends on the equipment picture (not on the empty cell), and the facing sides of a direct pair (redundancy sync) are reserved for that link.
- **Buses**: a switch serving three or more devices in one row is drawn as a common network bus (trunk, drops, one uplink); the per-device logical links stay in `logical_links`.
- **Blocking checks with automatic correction**: picture size, clearance, corridors, dangling/floating ends, cables inside the drawing area, cable spacing, attachment points, text, headings, boxes, page and template. Up to six correction passes, otherwise NOT BUILT and nothing written.
