# Meaning-based diagram file (spec version 2)

The v2 file says **what exists, at which Purdue level, in whose scope and how it connects**. It has **no coordinates**: `scripts/compile_v2.py`
places everything and turns the file into the free-form format of [diagram-format.md](diagram-format.md), which `scripts/build_diagram.py`
then draws. The older free-form file (shapes with x/y/w/h) still builds exactly as before; v2 is what the AI writes for new diagrams.

    python scripts/build_diagram.py diagram.json --out Architecture.vsdx
    python scripts/build_diagram.py diagram.json --out Architecture.vsdx --emit-v1 compiled.json   # also save the free-form file the compiler made

A file is v2 when it has `"spec_version": 2`. [`samples/diagram_example_v2.json`](../samples/diagram_example_v2.json) is the worked example
(pressure transmitters and an analyzer, a redundant S7-1500 pair, two SCADA workstations);
[`samples/diagram_example_ring_v2.json`](../samples/diagram_example_ring_v2.json) has a fibre ring.

## What is fixed and what is free

| Fixed by the program (the same on every drawing) | Free (you decide) |
|---|---|
| the A3 footer and its legends (client, project, rev, notes, scope legend, cable legend) | which items exist, their labels and models |
| the five cable styles (colour, dash, arrowhead) | which cable and which label each link has |
| one sky-blue band per Purdue level that is used, in level order, with a dark-blue vertical title strip | the level and the scope of every item |
| grey scope box = Avanceon, pink = Client / Other | pictures (library, then manufacturer web picture, then box) |
| the version stamp (bottom right) | header colours, only if the client gave them (`band_colors`) |

Only what is listed is drawn. The program never adds a switch, ring, DMZ, server or printer by itself; the one exception is the pair of ring
switches that a ring requires at each of its nodes (listed under ADDED BY RULE in the build report).

## Top level

```json
{
  "spec_version": 2,
  "project": {"client": "...", "project": "...", "doc_name": "...", "prepared_by": "...", "checked_by": "...", "approved_by": "...", "rev": "..."},
  "notes": ["optional footer note"],
  "items": [ ... ],
  "links": [ ... ],
  "redundancy": [ ... ],
  "rings": [ ... ],
  "band_colors": {"L2": "#RRGGBB"},
  "assumptions": ["what you assumed that is not an item or a link"],
  "questions": []
}
```

`project` is the footer (see [diagram-format.md](diagram-format.md)); a value you do not have prints `TBC`. `notes` go into the footer notes cell; the
program adds one more note, `* = assumed link, to be confirmed.`, when any link is assumed. `assumptions` are **not** printed on the drawing; they
appear in the build report. `questions` must be empty when you build (see "Errors, questions, warnings").

## items

| field | meaning |
|---|---|
| `id` | required, unique |
| `label` | required unless `component` (or `kind` switch / patch_panel) supplies one |
| `level` | **required**: `L0`, `L1`, `L2`, `L3`, `L3.5`, `L4` or `L5` (table below). Missing is a question; any other value is an error |
| `scope` | **required**: `avanceon` or `other`. Missing, `unknown`, `dual` or `both` is a question: it is never guessed |
| `kind` | `instrument`, `controller`, `rio`, `workstation`, `server`, `switch`, `patch_panel`, `firewall` or `other` (anything else warns and counts as `other`) |
| `model` | printed under the label (for example `Siemens S7-1500`) |
| `qty` | whole number; default 1. Up to 12 draws that many items numbered `-01`, `-02` ...; **more than 12 draws one item labelled `x N`** |
| `component` | id from `data/components.json` or `data/components_extra.json` (find it with `python scripts/find_component.py "<words>"`). A library picture always wins over `image` |
| `image`, `image_source`, `image_match` | a picture file (PNG; WebP/JPEG/GIF if Pillow is installed), where it came from (URL or manufacturer site; **needed**), and `exact` (the exact model) or `generic` (the type) |
| `group` | id of the item this one hangs under (level 0 items usually go under their controller). Optional: level 0 items also follow their links |
| `near` | id of an item this one is drawn right beside (patch panels use it) |
| `assumed` | `true` when you inferred the item and the prompt did not state it |

### Purdue levels

| `level` | band title | typical content |
|---|---|---|
| `L5` | Level 5 - Enterprise Network | cloud, headquarters |
| `L4` | Level 4 - Site Business Planning | ERP, business systems |
| `L3.5` | Level 3.5 - DMZ | firewalls, jump hosts |
| `L3` | Level 3 - Site Operations | MES, site servers, historian |
| `L2` | Level 2 - Supervisory (SCADA) | SCADA, HMI, workstations, engineering, printer |
| `L1` | Level 1 - Control (PLC / RTU / RIO) | PLC, RTU, RIO, controllers |
| `L0` | Level 0 - Field (Instruments / Actuators) | transmitters, analyzers, valves, motors |

Bands are drawn top to bottom in the order above and **only for levels that have at least one item**. Every band has the same title strip (0.45 in wide, white bold text turned to read upwards) on its left, the body is sky blue and the scope
boxes sit inside it; the strip is dark blue unless the client supplied `band_colors` (a `#RRGGBB` per level; a bad value is ignored with a warning).
Titles of L3, L3.5, L4 and L5 are a judgement (the Avanceon document names only L0-L2); rename them in `scripts/levels.py`.
If an item's label or kind looks like another level (for example a "SCADA workstation" on `L1`), the build warns; it never moves the item.

### Scope boxes

Inside a band, items sit in a scope box: **grey** for `avanceon`, **pink** for `other`. A band with both scopes shows the two boxes side by side.
The box colours are the same as the scope legend in the footer.

## links

`{"from": "pt", "to": "plc1", "cable": "hardwired", "label": "4-20 mA", "assumed": true}`

| field | meaning |
|---|---|
| `from`, `to` | item ids. For `hardwired` the arrowhead is at `to`: `from` = signal source |
| `cable` | `ethernet`, `fibre`, `modbus`, `bacnet` or `hardwired` (styles in [diagram-format.md](diagram-format.md)) |
| `label` | protocol or signal (`Modbus RTU`, `Modbus TCP`, `OPC UA`, `4-20 mA`). A `modbus` link without one warns |
| `assumed` | `true` when you inferred the link; its label gets a `*` (an unlabelled assumed link shows just `*`) |

A link between items with a quantity pairs their copies: equal counts one to one; one copy against many meets every
one; otherwise each copy of the larger side meets the nearest copy of the smaller side. A link that expands to **more than 4 lines** is
labelled on its first line only (listed under ADDED BY RULE). Several lines entering one side of an item are spread over that side, never stacked.

## redundancy (only when asked)

`{"primary": "plc1", "secondary": "plc2", "links": 2, "cable": "ethernet", "label": "Redundancy", "assumed": true}`

The two items are renamed **Primary Controller** and **Secondary Controller** (the `model` stays beneath), drawn side by side in the same
scope box, with two parallel lines labelled `Redundancy link 1` and `Redundancy link 2`. Both must be single items (`qty` 1) on the same level
and in the same scope. `links` other than 2 is allowed but warns ("the document shows two"). If the prompt did not say how the pair
synchronises, use `ethernet` and `"assumed": true`. Links listed for the primary are **not** copied to the secondary: list both.

## rings (only when asked)

`{"id": "r1", "label": "Fiber Optic Ring", "first": "plc1", "members": ["rio1", "rio2", "rio3"]}`

One closed fibre ellipse in the order Main PLC, RIO-1 ... RIO-n, back to the Main PLC. Needs at least 2 members; `first` and the members must be
different, single items on the same level and in the same scope.

* For `first` and each member the program adds **two ring switches** (kind `switch`, label `Ring switch`, the approved symbol), joined to their
  node by an assumed ethernet link, unless you name them: `"switches": {"plc1": ["swA", "swB"]}` uses your own two items for that node.
  The additions are listed under ADDED BY RULE; they are not "assumed", because the standard requires them.
* The Level 1 band holds, from the top: the other items of the band, then the Main PLC with its two switches near the two ends of the ellipse,
  the ellipse (labelled `Fiber Optic Ring`, light green, green dashed), the switch pair of every member, and the members. Level 0 items hang
  under their member. A fibre spoke runs from every ring switch straight to the ellipse outline.
* If the ring is too wide for one page the item size steps down; if it still does not fit the build stops with `too large for one A3 page`.
* A spec without `rings` never contains an ellipse or a ring switch.

## Switches and patch panels (only when asked)

`"kind": "switch"` or `"patch_panel"` always uses the approved symbol (`network_switch_approved`, `fo_patch_panel` from
`data/components_extra.json`); a `component` or `image` given for them is ignored with a warning. Switches sit on a lower row of their band, under
what they serve. A patch panel is drawn in the band of the item named in `near`, right beside it. The program warns when a level has exactly one
switch ("the document default is two") but never adds one. The AI's patterns: "SCADA switches" = two `L2` switches with every SCADA device
linked to both; "local switches" = two per control area at `L1`.

The switch picture in the repository is a **placeholder** until the approved Avanceon symbol is supplied: replace
`data/icons/network_switch_approved.png`, keeping the file name.

## Pictures

Servers, workstations and firewalls with no `component` and no `image` get a generic library picture (`rack_server`, `client_operator_workstation`, `industrial_firewall`); a picture you give always replaces it. Order: 1) a library picture (`component`; check with `find_component.py`), 2) the exact model's picture from the manufacturer (`image`,
`image_source`, `image_match: "exact"`), 3) a generic picture of the type from a manufacturer (`image_match: "generic"`), 4) nothing found: a
labelled box, reported as `BOX: no picture found for <label>`. The build:

* removes a plain white background from web pictures (Pillow needed; without it the picture is placed as it is and the report says so),
* warns when `image_source` is missing, when the shorter side is under 120 px, or when a generic picture was used,
* adds the footer note `N picture(s) from outside the component library (M generic); sources are in the shape data.`

## Errors, questions, warnings

| kind | effect | examples |
|---|---|---|
| **error** | `NOT BUILT`, fix the file | unknown level, cable, component or item id; duplicate id; `qty` not a whole number; a ring with fewer than 2 members; a redundant pair on different levels; an item id that collides with a numbered copy |
| **question** | `NOT BUILT: questions for the user:`, ask the user, then build | missing level; missing, unknown or dual scope; anything in `questions` |
| **warning** | built, listed in the report | an item that looks like another level; a modbus link with no label; `links` other than 2; a single switch; a missing `image_source` |

If nothing fits one page even at the smallest item size (65 %), the build stops with
`too large for one A3 page; ask the user to split it or use "x N" counts`.

## The build report

After `built ...` the program prints four sections; the AI pastes ASSUMED, PICTURES and WARNINGS into its reply.

| section | content |
|---|---|
| `ADDED BY RULE` | what the program added or changed on its own: ring order and ring switches, labels printed once, patch panels moved to their band |
| `ASSUMED` | every item or link marked `assumed`, the redundancy medium when assumed, and the `assumptions` strings |
| `PICTURES` | per item: `library`, `web, exact picture`, `web, generic picture` (with the source) or `box`; numbered copies are one entry with `[xN]` |
| `WARNINGS` | everything the build warns about |

The drawing carries the version of the plugin that made it (bottom right, `RPS Architecture plugin v<version> | spec v2`) and the same text in the
file's properties.
