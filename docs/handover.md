# Handover guide

## What this is (and is not)
This is **not model training**. No AI model is trained, fine-tuned or changed, and nothing the engineers type is used to teach a model.

It is a **toolkit that an existing AI (ChatGPT or Claude) is told to use**:
1. A short **instruction text** tells the AI what to add to its answer: the team's fixed footer, cable styles, level bands and scope boxes, and a Visio file.
2. A small **program** (Python) does the part an AI cannot do reliably: it places everything and draws the editable `.vsdx` file.
3. A **library** of component pictures and the cable/footer rules sits next to the program.

Analogy: the AI is a draughtsman. The instruction is the job brief; the program is the company's drawing template and stamp. The draughtsman decides what the diagram contains, but every drawing leaves with the same title block, cable styles, bands and scope boxes. Replacing the AI with a newer one needs no retraining: the same instruction and program still work.

## What is fixed and what is free
| Fixed (same for everyone) | Free (the AI decides) |
|---|---|
| The A3 footer: Client, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev/Sheet, notes, scope legend, cable legend, Avanceon logo | What is in the diagram (only what the prompt asks for), names, models, protocols |
| Cable types and styles: ethernet blue dashed, fibre green dashed, modbus red solid, bacnet purple solid, hardwired black solid with an arrowhead | Which cable and label each link has (marked `assumed` when inferred); which level and scope each item has (the program asks when scope is unknown or dual) |
| One band per Purdue level in use (L0-L5, L3.5 DMZ) in a sky-blue box with a dark-blue vertical title strip (or the client's colours); grey / pink scope boxes | Pictures: library first, then the manufacturer's picture of the exact model, then a generic one, then a labelled box (reported) |
| The plugin version stamp; output is one editable A3 `.vsdx` made by the program | Switches, a fibre ring, redundant controllers: drawn only when the prompt asks |

The footer values (Client, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev) come from the user's prompt; missing ones print `TBC`. (`end_user` is still accepted for Client; `contractor` is accepted but no longer printed.)

## How a user uses it
1. Write a normal prompt (optionally attach an RFQ or BOQ). Say the project name and any footer details in the prompt.
2. The AI asks its questions once (unknown scope, instrument models, an unclear interface, header colours), writes a small v2 `diagram.json` (no coordinates), runs the program, and returns `Architecture.vsdx` together with the ASSUMED, PICTURES and WARNINGS sections of the build report.
3. The user opens it in Visio and edits it freely.

In Claude, the AI asks once whether it may download pictures from the web; say yes (or write "download real product pictures from the web" in the prompt). Install Pillow once (`pip install pillow`) if the white backgrounds of web pictures should be removed.

## The parts of the repo
```
chatgpt-plugin/instructions.md   THE instruction text. One source for both platforms.
chatgpt-plugin/make_package.py   builds arch_plugin.zip (ChatGPT) and regenerates the Claude skill from instructions.md
.claude-plugin/                  Claude plugin + marketplace manifests (plugin version lives here)
skills/architecture-diagram/     the Claude skill (generated file: edit instructions.md, not this)
scripts/build_diagram.py         the program: diagram.json -> .vsdx, and the build report
scripts/compile_v2.py            v2 spec (meaning) -> free-form spec: validation, questions, placement, redundancy, rings
scripts/levels.py                Purdue levels, header and scope colours (grey / pink)
scripts/vsdx_writer.py           writes the Visio package on top of base/base.vsdx
scripts/footer.py, cables.py     the fixed footer and the cable styles
scripts/draw.py, textfit.py      pictures/boxes and text fitting
scripts/components.py            the component library loader (components.json + components_extra.json)
scripts/find_component.py        library lookup, run before any web picture search
scripts/imaging.py               background removal for web pictures (Pillow, optional)
scripts/import_dataset.py        refreshes the library from the dataset workbook (maintenance only)
data/cable_types.json            cable names, colours, dashes, arrowheads (client's drawing instructions)
data/level_hints.json            keywords used only to warn about a probably wrong level
data/components.json + icons/    library components and pictures (rewritten by import_dataset.py)
data/components_extra.json       hand-added components (approved switch and FO patch panel); survives a re-import
base/base.vsdx                   empty A3 Visio page made by Visio itself (do not edit)
docs/diagram-format-v2.md        the diagram.json format the AI writes (meaning, no coordinates)
docs/diagram-format.md           the free-form format it compiles to (still builds on its own)
docs/setup.md                    ChatGPT and Claude setup steps
docs/decisions.md                every decision and why (D43 = free-form design; D44-D57 = the upgrade to the new Avanceon document)
tests/                           run: python -m unittest discover -s tests
```

## Setting it up
See [setup.md](setup.md). Short version:
- **Claude:** `/plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-plugin`, then `/plugin install architecture-diagram@rps-architecture`. Needs Python 3 on the PC.
- **ChatGPT:** create a custom GPT: paste `instructions.md` as its instructions, upload `arch_plugin.zip` and the client's Word drawing-rules document as knowledge, turn on Code Interpreter and Web search.

## Making a change (release routine)
1. Change the instruction (`instructions.md`) or the code. Never hand-edit `SKILL.md`.
2. `python -m unittest discover -s tests` (expect 221 tests, 2 skipped: the two file-writer tests run only when `ARCH_BASE_VSDX` points at `base/base.vsdx`; Pillow-dependent tests also skip themselves when Pillow is missing).
3. `python chatgpt-plugin/make_package.py` (rebuilds the zip in `Downloads\out` and rewrites `SKILL.md`).
4. Raise `version` in `.claude-plugin/plugin.json` (Claude only notices updates when the version changes).
5. Commit, merge to `main` (Claude reads `main`), push.
6. Claude users: refresh the marketplace, update the plugin, start a new session. ChatGPT users: replace the custom GPT's instruction and knowledge file by hand.

Typical changes: a new cable colour or type (`data/cable_types.json`), a new library component (update the workbook and run `import_dataset.py`, or add it to `data/components_extra.json`), the approved switch picture (replace `data/icons/network_switch_approved.png`), band or scope colours (`scripts/levels.py`), a footer change (`scripts/footer.py`, then every user must update), wording of the instruction. After changing `instructions.md` run `make_package.py` and the tests: `tests/test_instructions.py` fails when `SKILL.md` was edited by hand or a swap sentence was lost.

## Things people get wrong
- **"It is trained on our data."** No. See the first section.
- **Editing files on a PC and expecting Claude to change.** Claude uses its own cached copy; only a pushed, version-raised update reaches it.
- **Hand-written Visio files.** The AI must never write the `.vsdx` itself: Visio rejects it (wrong XML namespace, missing shape geometry, missing package parts). Only `build_diagram.py` writes the file, on top of `base/base.vsdx`.
- **Expecting identical output every run.** The AI is a language model, so item choices, models and picture choices can differ between runs. The footer, cable styles, bands, scope boxes and the placement of what is listed are produced by the program.

## Known limits and open items
- **Pictures are best-effort.** They need the AI's tool to download from the web (ChatGPT's code sandbox sometimes has no internet; Claude Code on a PC does but asks permission). If it cannot, items become plain boxes or library pictures. Users can swap pictures in Visio.
- **Picture licensing.** Web pictures (supplier photos, SAP/QGIS/Wazuh logos, stock icons) may be copyrighted. RPS should decide the policy before diagrams go to clients. Sources are stored in each picture shape's data and noted in the footer.
- **Placement is automatic but not perfect.** The program places v2 files itself and warns about overlaps and lines through shapes; a very full page steps the item size down (to 65 %) and then stops with "too large for one A3 page". Check the result in Visio.
- **Extra items.** The AI is told to draw only what the prompt asks for, and the program draws only what is listed; reviewers should still check the diagram against the request and the ASSUMED list.
- **Library is partial.** Only about 37 components have pictures; field transmitters, SIEM, SAP, GIS, etc. rely on web pictures (the library hook: add `layer: "Instrument"` entries to `data/components_extra.json`).
- **The switch picture is a placeholder** until the approved Avanceon symbol (and a better FO patch panel picture) is supplied.
- **Not verified in Visio.** The upgrade was built and tested without Visio: the arrowhead size, the closed ring polygon, the footer widths (the reference picture was not available) and the scope/header colours need a person to open the files and compare them with the document.
- **Acceptance testing is thin.** It has been tried on one prompt (42 pumping stations, Purdue model). Try at least three real RPS prompts, with a reviewer comparing each result.
- **The old sign-off document is out of date** (it describes the earlier strict approach). Still open.
- **The ChatGPT custom GPT is not set up yet.** RPS must confirm their plan allows custom GPTs and Code Interpreter.

## History in one paragraph
The project began as a strict pipeline (BOQ in, validated spec, automatic Purdue layout, every item checked against the component library). RPS then dropped the BOQ and later asked only for a consistent footer and cable colours plus an editable Visio version of what ChatGPT already drew. The strict code was removed in the free-form change (decision D43). The upgrade to the new Avanceon document (D44-D57) added a meaning-based spec with automatic placement in front of the same drawing code. It is still in the git history, and the cleanup also left a local copy outside the repo on the original developer's PC (`Downloads\out\removed_in_cleanup\strict_purdue_path`): copy that folder somewhere shared if it may be needed.

## Where things came from
- Footer layout and cable colours: the client's "System Architecture Drawing Instructions" Word document.
- Component library and pictures: `system_architecture_dataset.xlsx` (keep a copy; `import_dataset.py` reads it).
- Every design decision, with the reason: `docs/decisions.md`.
