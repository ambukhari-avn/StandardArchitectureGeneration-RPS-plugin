# Standardized architecture questionnaire (Phases 2–6, revisions 6.4)

The AI holds the conversation; `scripts/arch_spec.py` keeps the record. Everything the user says goes into one structured
specification, `architecture_spec.json`, and the drawing is generated from it. Standard library only.

```
python scripts/arch_spec.py <command> architecture_spec.json [options]
```

## The seven steps

| Step | What the AI asks | Commands |
|---|---|---|
| 1 Project details | Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, Approved By, Drawing Revision (blank = TBC) | `init`, `project --client .. --end-user .. --project .. --doc-name .. --prepared-by .. --checked-by .. --approved-by .. --revision ..` |
| 2 Purdue layers | Which layers (any combination), renames, custom layers | `catalog`, `layers --select L0 L1 L2 L3.5 [--rename L1="Control System"] [--custom "2.5\|Utilities\|Power & water"]` |
| 3 Equipment | One multiline free-text question per selected layer, lowest level first | `add-equipment --layer L0 --text "..."` (or `--file`), `edit-equipment EQ-003 --quantity 4 ...`, `remove-equipment EQ-003` |
| 4 Connectivity | Only the open questions `questions` lists, in its order | `connect ...` for connections already described, `questions [--next] [--json]`, `answer KEY VALUE [--text ...]`, `unanswer KEY` |
| 5 Review & edit | Review, edits, return to any step; editable text request | `review`, `validate`, `request --out request.md`, `parse-request request.md [--apply]`, `note "..."` |
| 6 Generate | Placement and display (optional) | `place EQ --left-of EQ`, `edit-connection CN --display bus\|point-to-point\|cross\|chain\|ring\|consolidated`, `layout --buses off`; `to-diagram --out diagram.json`; `verify-diagram spec diagram.json`; `build_diagram.py diagram.json --out Architecture.vsdx --check-spec spec --preview`; after approval the same with `--locked-layout Architecture.layout.json` |
| 7 Modify | Change requests after delivery | `revise --revision R1 --note ..`, the edit commands above, `changes`, `to-diagram --previous old_diagram.json` (keeps pictures, waypoints and weights of unaffected items) |

`show` prints the whole specification, `history` the change log, `stage NAME` records where the conversation is.

## Layers

| Key | Level | Default name | Drawing id |
|---|---|---|---|
| L0 | 0 | Field Instruments | `field` |
| L1 | 1 | Control | `control` |
| L2 | 2 | SCADA / Supervisory | `scada` |
| L3 | 3 | Site Operations | `operations` |
| L3.5 | 3.5 | DMZ — Demilitarized Zone | `dmz` |
| L4 | 4 | Enterprise / Business Network | `enterprise` |
| L5 | 5 | External / Corporate / Cloud Systems | `external` |
| C1, C2… | any number | user's name | `custom_<name>` (drawn through `custom_layers`) |

Only the selected layers are kept; nothing is added automatically. Names are the user's. The drawing runs from the highest level at the
top to the lowest at the bottom; equipment questions run from the lowest up. Selecting L3.5 adds no equipment. A layer holding
equipment cannot be dropped without `--force` (which deletes its equipment).

## Equipment records

Each line of a layer's text becomes one record with a permanent id (`EQ-001`, never reused): name, category, quantity, layer, OEM,
model, redundancy, location/panel, scope, interfaces, notes and the original text. Accepted forms include `Pressure Transmitters — 12`,
`2 x SCADA Servers`, `SCADA Switches x 2`, `Level switches 4 nos`, `Qty 3 Printers`, and optional fields after `|`:
`Modbus gateway | OEM: Moxa | Model: MGate 5105 | Location: MCC-1 | Interfaces: Modbus RTU, Modbus TCP | Scope: client`.

- Missing quantity or model stays empty (flagged `quantity not stated`); nothing is invented.
- Redundant/hot-standby controllers or servers with quantity 2 are **one** redundant system (`systems: 1`). Another quantity with
  "redundant" is flagged for the user to confirm.
- Scope words (client scope, existing, by others, third party, free issue) mark the record `other` (client / existing scope colour).
- A line already recorded in the same layer is not added twice.

Categories: `instrument, io, plc, rtu, dcs, hmi, switch, fo_panel, firewall, gateway, media_converter, router, wireless, server,
historian, workstation, eng_workstation, laptop, printer, video_wall, ups, kvm, time_server, existing_scada, other`.

## Connectivity questions (generated, never a fixed list)

`questions` looks at the recorded equipment and lists only relationships that exist and are still unresolved, in this order:

| Step | Trigger | Question keys and choice values |
|---|---|---|
| 1 | instruments + I/O / controller | `instrument_to_control`: `hardwired`, `modbus_rtu`, `modbus_tcp`, `fibre_interface`, `mixed` → per instrument `instrument_method:EQ`, `instrument_target:EQ`, `instrument_interface:EQ`, `instrument_local:EQ` |
| 2 | I/O + PLC | `io_protocol`: `profinet`, `ethernet_ip`, `modbus_tcp`, `profibus`, `backplane`; `io_topology`: `star`, `daisy`, `ring`, `dual`, `backplane`; `io_medium`: `copper`, `fibre`, `rs485`; `io_star_hub`; `io_owner:EQ` (several PLC systems) |
| 3 | redundant PLC | `plc_sync:EQ`: `dedicated`, `ethernet`, `fibre`, `oem_tbv`; `plc_sync_paths:EQ`: `1`, `2`, `unknown`; `plc_sync_medium:EQ` |
| 4 | PLC + switches | `plc_switch:EQ`: `each_dedicated`, `both_to_both`, `single_to_one`, `redundant_network`; `plc_switch_medium` |
| 5 | control + SCADA networks | `control_scada`: `copper`, `fibre`, `dual`, `via_firewall`; `control_scada_medium`, `control_scada_firewall` |
| 6 | SCADA switches + servers/workstations | `scada_homing`: `single_first`, `single_split`, `dual` (only with 2+ switches); `scada_lan_medium` |
| 7 | patch panels, fibre interfaces or links | `fibre_topology`: `p2p`, `dual`, `ring`; `fibre_ring_nodes` (only when a ring is chosen); `fo_panel_links:EQ` (which fibre links pass through the panel) |
| 8 | firewall | `firewall_zones:EQ` (exactly two of the project's layers), `firewall_medium:EQ`, `firewall_link:EQ:LAYER` |
| 9 | any other communicating equipment with no connection (gateways, RTUs, DNP3 devices, routers, wireless, DCS, existing SCADA, HMIs, printers...) | `link:EQ:N:target`, `link:EQ:N:protocol`, `link:EQ:N:medium` (gateways, converters and firewalls have two sides) |

Every question accepts `other` (with `--text`) and most accept `na`. Step 9 is asked only after steps 1–8 are settled. A connection
recorded with `connect` resolves the matching question, so connections the user already described are not asked again. Changing an
answer (`answer` again, or `unanswer`) rebuilds only the connections that answer created and keeps their ids; a connection changed with
`edit-connection` becomes the user's and is never overwritten by later answers.

Each connection stores source and destination equipment ids, protocol, medium, topology, redundancy, number of paths, direction, scope,
label, optional `via` (e.g. a patch panel), and how it maps to units (`links`, `chain`, `ring`, `group`, `pair`).

## Validation

`validate` (also run inside `review`, `request` and `to-diagram`) keeps protocol, medium, topology and redundancy apart and flags,
without changing anything:

- a value in the wrong field (`PROFINET` as a medium, `Star` as a protocol);
- Ethernet protocols on RS-485/RS-232/hardwired cable; serial protocols on copper Ethernet; hardwired signals on fibre or in a ring;
- an instrument connected straight to fibre without a communication interface;
- unconfirmed medium, topology or sync link count, open questions, and "Other" answers that still need a `connect`;
- a medium with no colour in the approved cable standard (RS-232, wireless, PROFIBUS cable, OEM sync cable): such links are not drawn
  and are reported, so a cable type is never chosen by assumption.

Cable types: hardwired → `hardwired`, copper Ethernet → `ethernet`, fibre → `fibre`, Modbus RTU on RS-485 → `modbus`, BACnet → `bacnet`.

## Review and the editable request

`review` prints project information, selected layers, equipment per layer, the connectivity summary, unresolved technical questions,
warnings and notes. `request --out request.md` writes the complete request as text; the user may edit any line (ids in brackets
identify records, new lines without an id are added, deleted lines are removed, `-` means not stated). `parse-request request.md`
lists the differences; `--apply` writes them into the specification and rewrites the file. `request` refuses to overwrite a request
file that has edits not yet parsed (`--force` discards them).

## Generating the drawing

`to-diagram --out diagram.json` produces a buildable diagram: footer values, the selected layers with their names (`layer_headers`,
`custom_layers`), one container per PLC system with its common I/O box, one field-instrument group per PLC system (one picture per
instrument type with its quantity), one SCADA container, client/existing scope boxes in the client colour, and lines from the confirmed
connections only. Shape ids are `<equipment id>-<unit>` (e.g. `EQ-004-1`), so they stay stable across revisions. Library pictures are
only offline fallbacks; source pictures web first as usual and record them with `image EQ-004 --image ... --image-source ...`.

## Revisions (6.4)

Each `to-diagram` stores a baseline. After a change request:

```
arch_spec.py revise spec.json --revision R1 --note "client comments"
arch_spec.py remove-equipment spec.json EQ-010                     # remove the engineering workstation
arch_spec.py edit-equipment spec.json EQ-004 --redundancy "Redundant pair" --quantity 2   # simplex -> redundant (then answer the sync questions)
arch_spec.py edit-equipment spec.json EQ-008 --quantity 4          # add two SCADA servers
arch_spec.py edit-equipment spec.json EQ-013 --layer L3.5          # move the firewall to DMZ
arch_spec.py answer spec.json io_topology daisy                    # remote I/O network to daisy-chain
arch_spec.py changes spec.json                                     # affected equipment and connections only
arch_spec.py to-diagram spec.json --out diagram.json               # then rebuild with --preview
```

Unrelated equipment, quantities, connections and ids are untouched; the header and footer are regenerated from the same project
record with the new revision.

## Examples and acceptance tests

`python scripts/examples.py samples/examples` runs four complete questionnaires (Phase 11 tests A-D: simple PLC, redundant PLC,
architecture with a DMZ, and a revision) and writes for each the questionnaire transcript with the review, the editable request, the
specification, diagram.json, the Visio file and its preview. `tests/test_acceptance.py` checks them automatically (test E adds the
visual checks every build runs); the previews are still inspected by eye.
