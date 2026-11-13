# Boxed reference layout (1.1.0)

The current default follows `reference-style.png`. It uses navy headings (`#073878`), blue rounded borders (`#27369B`), light-blue heading cards (`#E4F3FF`) and pale equipment panels (`#F5FAFF`). Client/existing-system groups use pale orange (`#FFE5B5`) and orange borders (`#FF8800`). Cable colours and their solid/dashed classifications remain unchanged in `data/cable_types.json`.

## Layout and hierarchy

Start from `samples/reference_boxed.json`. Set `layers` to required standard ids in any order; the builder uses standard top-to-bottom order. Each layer has a separate heading card and equipment panel, with a small clear gap between layers. Heights follow actual group rows and picture sizes. Control has a larger default allowance; `layer_weights` can tune it, for example `{"scada": 2, "control": 5, "field": 2}`. No layer is forced to equal another.

Use `layer_headers` to override display text, e.g. `{"control": {"name": "Control System", "description": "Redundant PLC"}}`. Default headings omit Purdue level numbers; include one in the name if requested.

Create a `kind: "group"` shape with a `layer`, then give its device shapes `parent: "group-id"`. Child shapes inherit the parent's layer. Groups may themselves have parents. The program fits children in a grid: `columns` (1–24) sets a group column count; zero-based `row` on children makes explicit rows. Children in the same explicit row share that row. Their sizes and proportions are retained where space allows; crowded layouts warn instead of silently hiding content. Parent cycles, missing parents, invalid options and conflicting layers stop the build.

Root groups are arranged left-to-right. `width_weight` allocates relative width. A requested separate panel uses `placement: "beside"` on a root group in the control layer; it is placed to the right of main PLC equipment. This works for any separately requested panel. The builder never invents one. `solid: true` makes a group border solid, suitable for an I/O rack. `max_width` and `max_height` (inches) keep a root summary group compact within its allocated panel.

Loose layer devices are automatically placed in a generated equipment group. Existing/external system summaries may be empty labelled groups: their labels are centred. Actual devices still require pictures. No component model, wiring or footer value is inferred from the style reference.

Positions inside this layout are computed by the group system; do not mix absolute x/y assumptions with parent-relative grid placement. For old exact-position drawings, `layout_style: "legacy"` preserves the previous layer placement and footer.

## Box-to-box cables

Specify the actual logical lines as usual. Explicit group endpoints are kept exactly as given. Device links crossing between containers attach to the outside boxes; internal connections remain within a shared box. Parallel non-hardwired connections remain separate.

`cable_detail: "grouped"` is the default. For hardwired instrument lines from the field layer to the same control-layer I/O rack, the program draws one visible line per source field container and target rack. It frames the rack automatically if needed. All original instrument-to-rack endpoint pairs remain in the JSON and in the visible line's `User.SourceKey` metadata after `|logical=`. Distinct source groups and distinct racks are not combined.

To show every individual device line, set `cable_detail: "individual"`. Per-line `individual: true` preserves just that line. Manual `via`, `from_side`, `to_side` or `straight` instructions also preserve that connection individually. The router ignores an endpoint container's own children when finding its outside attachment, while keeping other devices clear. Cable colours come only from the cable standard; the reference image's cable colours do not override it.

## Footer

Three separate rounded cards: logo/project/document metadata; Notes; Legend. The legend includes both scope swatches and the cable samples. Labels/headings are bold and metadata values regular. Client and a supplied End User share one entry; the bottom strip holds Document Name, Prepared by, Checked by, Approved by, and Size / Rev / Sheet. Missing supplied values use TBC; normal document/revision/sheet defaults remain supported. Text fitting enforces the 6 pt floor. The page remains A3 landscape.

Picture transparency, the 2400 px cap, compact dashes and black-frame prevention from earlier versions are retained. `--preview` remains required for visual inspection. Automated checks exercise both this default and legacy layout compatibility. Native Visio display has not been verified for this release.
