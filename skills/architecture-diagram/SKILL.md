---
name: architecture-diagram
description: Make an editable one-page A3 Visio (.vsdx) system-architecture diagram (for example a Purdue-model diagram) from the user's request, with the team's fixed footer and cable colours. Use whenever the user asks for an architecture diagram or a Visio file of a system.
---

**Avanceon Architecture Diagram plugin — version 1.7.2** (Claude plugin; the ChatGPT package carries the same version).

You make one editable A3 Visio (.vsdx) architecture diagram per request, in Avanceon's approved template, with the supplied program. The program enforces the rules below; your job is to collect a correct specification, choose pictures, and deliver only what the program built.

## Order of authority (highest first; a lower level never overrides a higher one)

1. **Locked template.** Footer (logo, project/document metadata, Prepared/Checked/Approved, Revision, Notes, cable and scope legends), title, vertical layer-heading strips, scope colours, cable colours and line weights (`data/cable_types.json`), the fixed library pictures, A3 landscape and editable Visio output never change; only their text values do. Missing values print TBC. The builder stops if the template geometry or a fixed picture changes.
2. **User-confirmed specification** (`architecture_spec.json`): selected layers, every equipment record and quantity, topology, connections, redundancy, scope and placement constraints. The build is refused if the drawing does not show exactly this (`--check-spec`).
3. **Mandatory engineering rules** (`docs/mandatory-drawing-rules.md`): never invent equipment, models, OEMs, rings, cables, dual interfaces, redundant I/O or synchronisation links; hardwired signals end at the actual I/O; protocol, medium, topology and redundancy are separate answers. Use IEC 61131, IEC 62443, IEC 61082-1, ISA-5.1 and OEM recommendations as guidance only; never claim formal compliance.
4. **Engine layout** (automatic): functional rows, layer heights, minimum picture sizes, routing corridors, attachment points, clearances, crossings and labels. Do not hand-position shapes in a diagram generated from a specification.
5. **Presentation choices**: pictures, cable waypoints, layer/width weights. Kept across revisions.

## Questionnaire (new drawings and revisions)

Keep every architecture in `architecture_spec.json`, managed only with `python "${CLAUDE_PLUGIN_ROOT}/scripts/arch_spec.py" <command> <spec> ...` (commands and choice values: `docs/questionnaire-workflow.md`). It holds project metadata, layers, equipment with permanent ids (EQ-001...), confirmed connections (CN-001...), answers, placement, notes and revision history. Never draw from memory of the chat.

Ask one step at a time. Use the host's multiple-choice tool when it has one (at most four options; free text always accepted), else numbered choices in chat. Never ask again for information already given in the chat or in attached RFQ/BOQ text: record it first and ask only what is open.

1. **Project details.** Client / Contractor, End User, Project, Document Title, Prepared By, Checked By, Approved By, Drawing Revision in one message; record with `project`.
2. **Purdue layers.** Offer Level 0 Field Instruments, Level 1 Control, Level 2 SCADA / Supervisory, Level 3 Site Operations, Level 3.5 DMZ, Level 4 Enterprise, Level 5 External / Cloud, renaming and custom layers (`layers --select ... --rename KEY="Name" --custom "LEVEL|Name|Description"`). Select only what the user selects. Level 3.5 never adds equipment by itself.
3. **Equipment per layer.** One multiline question per selected layer, lowest first; record with `add-equipment --layer KEY --text ...` and show the parsed summary for correction (`edit-equipment`). A redundant CPU pair is one redundant system.
4. **Connectivity.** Record connections the user already described (`connect --from EQ --to EQ --protocol --medium --topology --redundancy ...`), then run `questions` and ask only the open questions it lists, in its order; record replies with `answer KEY VALUE` (`other --text`, `na`). Show any incompatibility `connect`, `answer` or `validate` reports; never replace it silently. How a connection is drawn is separate from what it is: `edit-connection CN --display auto|point-to-point|bus|cross|chain|ring|consolidated` changes only the drawing; `layout --buses off` draws every network link as its own cable; `layout --io-display representative|individual` chooses the remote I/O display.
5. **Placement (optional).** Record any relative placement the user asks for with `place EQ --left-of EQ` / `--right-of EQ` (`--clear` removes it). Contradictory constraints stop the build; ask the user which one wins.
6. **Review.** Show `review`; let the user change anything or go back. Offer the editable request (`request --out request.md`); after user edits run `parse-request`, show the differences, then `parse-request --apply`.
7. **Generate, preview, approve, export.**
   - `validate` (no errors), then `to-diagram --out diagram.json` (for a revision add `--previous <old diagram.json>`).
   - You may add pictures (below) and cable `waypoints` to diagram.json; never change shapes, quantities, connections, rows or cable types there. `verify-diagram <spec> diagram.json` must print no problems.
   - Build the preview with `--check-spec <spec> --preview`. The preview PNG is rendered from the same page as the Visio file, and `<out>.layout.json` locks that layout. Show the preview for approval.
   - After approval, export with `--check-spec <spec> --locked-layout <out>.layout.json`; the Visio file is written only if its layout is identical to the approved preview. Any change after approval needs a new preview.
8. **Revisions** ("remove the engineering workstation", "simplex to redundant PLC", "add two SCADA servers", "move the firewall to DMZ", "daisy-chain the remote I/O"): load the existing specification (ask for it if missing), `revise --revision <next>`, change only the affected records (`remove-equipment`, `edit-equipment`, `add-equipment`, `answer`, `edit-connection`), answer new questions, show `changes`, then regenerate with `to-diagram --previous` so unaffected equipment keeps its pictures, waypoints and weights. Never redraw an unrelated architecture.

When the user gives a complete written request, follow the same steps silently and ask only what is unresolved.

## What the engine draws (do not re-create by hand)

- **Layers and boxes.** Full-width layer frames with vertical navy heading strips; heights follow content and are never forced equal. Minimal boxes: a visible boundary only for client/existing scope, several PLC systems, panels, sites or security zones, the single field-instrument group and a common solid I/O box for two or more drawn racks. Scope `avanceon` is pale/white, `other` is pale orange with orange borders.
- **Functional rows.** Control layer bottom to top: I/O racks, PLC controllers (redundant pair side by side, sync link labelled), Ethernet switches with FO patch panels at the ends. SCADA: servers, clients, network. This is a placement order, never a reason to add equipment. Dense diagrams may use the compact arrangement (fewer rows) automatically.
- **Remote I/O.** Equivalent racks show one representative rack captioned "Qty: N · <topology>" with no box around it; the specification keeps every rack and its topology.
- **Field layer** holds instruments and field devices only. One instrument group; representative hardwired lines run from it to each actual I/O system, labelled "Typical Hardwired Signals — AI/DI/AO/DO".
- **Cables.** Logical connections are kept per device (`logical_links`) while the drawing may use a common network bus, point-to-point links, redundant cross-connections, daisy chains, FO rings (`rings`; the approved dashed light-green ellipse) or one consolidated hardwired line. Cables are orthogonal and continuous, start and end on the equipment picture, stay in their routing corridor, keep clearances from equipment, labels and other cables, use hops at crossings, and carry small arrowheads only for hardwired signals (to the I/O) and bidirectional links (`"arrows": "both"`).
- **Picture sizes.** Each equipment category has a minimum displayed size (`data/equipment_sizes.json`; PLCs and remote I/O first). The engine enlarges layers to meet them.
- **Blocking quality checks with automatic correction.** Missing or floating cable ends, diagonals, cables through unrelated layers or equipment, crowded or shared tracks, overlapping text, undersized pictures, headings that do not match the layers, unnecessary boxes, a non-A3 page or a changed template are defects. The builder corrects the layout automatically (up to six passes); if any defect remains it prints NOT BUILT and writes no Visio file (`--draft` renders the failing layout for diagnosis). Change the specification or simplify the display (for example `--display bus`) and rebuild; never deliver a draft.

## Pictures

Read `docs/web-first-images.md` and `docs/fixed-library.md`. The FIXED pictures are only: laptop / engineering laptop, video wall, Ethernet switch (alternate switch only when requested) and fibre optic patch panel. Always set their `component`; never search for, replace, clean, recolour or regenerate them unless the current prompt explicitly asks (then `image`, `image_source` and `image_override: true`). A requested model changes the caption, not the fixed picture.

Every other device (PLCs, remote I/O, servers, RTUs, firewalls, instruments, gateways, ...) is sourced WEB FIRST: with an OEM and model use exactly that; prefer official manufacturer sources, high-resolution transparent PNG or a clean product photo, front-facing, undistorted, no watermark, at least 300 source pixels per displayed inch. Cache it with `python scripts/image_cache.py add <file> --url <source URL> --oem <maker> --model <model>` (reuse with `find`) and give the shape `image`, `image_source`, `oem` and `model`. Never invent a manufacturer or model; an unspecified model gets a representative picture described as illustrative. If the web is unavailable or nothing suitable exists, the offline library is used (including drawn illustrations of common instruments); an instrument with no picture at all gets an ISA-5.1 tag balloon (PT, TT, FT, LT, ...), never an unrelated generic picture. Relay every `notice:` the builder prints and report each fallback.

## Producing the file

New drawings come only from the specification (`to-diagram`), following docs/diagram-format.md in this plugin's folder; a hand-written layout (samples/diagram_example.json) is only for editing an older drawing that has no specification. Write diagram.json, save it in a temporary folder (not the user's output folder) and run

    python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py" <temporary folder>/diagram.json --out Architecture.vsdx --check-spec architecture_spec.json --preview

Inspect the whole preview and close views of device edges, labels and the footer; a successful build alone is not acceptance. Export the approved preview with the same command using `--locked-layout` in place of `--preview`.

If it prints NOT BUILT, every defect listed is blocking: fix the cause and run again. Warnings and notices must be reported to the user. Keep diagram.json, helper scripts and downloaded pictures in a temporary folder, not in the user's output folder, and delete them once the file is built. Tell the user where Architecture.vsdx is (in the working folder) and keep architecture_spec.json next to it for later revisions. Say "built" only if the program did.

(The plugin folder is ${CLAUDE_PLUGIN_ROOT}: it holds scripts/, data/, base/, samples/ and docs/. If that variable is empty, it is two folders above this file.)
