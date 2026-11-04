# Handover guide

## What this is (and is not)
This is **not model training**. No AI model is trained, fine-tuned or changed, and nothing the engineers type is used to teach a model.

It is a **toolkit that an existing AI (ChatGPT or Claude) is told to use**:
1. A short **instruction text** tells the AI what to add to its answer: the team's fixed footer, the fixed cable colours, and a Visio file.
2. A small **program** (Python) does the part an AI cannot do reliably: it draws the editable `.vsdx` file with the footer and cable colours.
3. A **library** of component pictures and the cable/footer rules sits next to the program.

Analogy: the AI is a draughtsman. The instruction is the job brief; the program is the company's drawing template and stamp. The draughtsman designs the diagram, but every drawing leaves with the same title block and cable colours. Replacing the AI with a newer one needs no retraining: the same instruction and program still work.

## What is fixed and what is free
| Fixed (same for everyone) | Free (the AI decides) |
|---|---|
| The A3 footer: title block, notes, legend, Avanceon logo | What is in the diagram and how it is laid out |
| Cable types and colours: ethernet blue, fibre red, modbus green, bacnet purple, hardwired black | Whether to ask questions, what to add, which pictures to use |
| Output is one editable A3 `.vsdx` made by the program | Pictures: web, library, or none |

The footer values (End User, Contractor, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev) come from the user's prompt; missing ones print `TBC`.

## How a user uses it
1. Write a normal prompt (optionally attach an RFQ or BOQ). Say the project name and any footer details in the prompt.
2. The AI designs the diagram, writes a small `diagram.json`, runs the program, and returns `Architecture.vsdx`.
3. The user opens it in Visio and edits it freely.

In Claude, the AI asks once whether it may download pictures from the web; say yes (or write "download real product pictures from the web" in the prompt).

## The parts of the repo
```
chatgpt-plugin/instructions.md   THE instruction text. One source for both platforms.
chatgpt-plugin/make_package.py   builds arch_plugin.zip (ChatGPT) and regenerates the Claude skill from instructions.md
.claude-plugin/                  Claude plugin + marketplace manifests (plugin version lives here)
skills/architecture-diagram/     the Claude skill (generated file: edit instructions.md, not this)
scripts/build_diagram.py         the program: diagram.json -> .vsdx
scripts/vsdx_writer.py           writes the Visio package on top of base/base.vsdx
scripts/footer.py, cables.py     the two fixed things
scripts/draw.py, textfit.py      pictures/boxes and text fitting
scripts/components.py            the component library loader
scripts/import_dataset.py        refreshes the library from the dataset workbook (maintenance only)
data/cable_types.json            cable names and colours (client's drawing instructions)
data/components.json + icons/    library components and pictures
base/base.vsdx                   empty A3 Visio page made by Visio itself (do not edit)
docs/diagram-format.md           the diagram.json format the AI follows
docs/setup.md                    ChatGPT and Claude setup steps
docs/decisions.md                every decision and why (D43 = current free-form design)
tests/                           run: python -m unittest discover -s tests
```

## Setting it up
See [setup.md](setup.md). Short version:
- **Claude:** `/plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-_plugin`, then `/plugin install architecture-diagram@rps-architecture`. Needs Python 3 on the PC.
- **ChatGPT:** create a custom GPT: paste `instructions.md` as its instructions, upload `arch_plugin.zip` and the client's Word drawing-rules document as knowledge, turn on Code Interpreter and Web search.

## Making a change (release routine)
1. Change the instruction (`instructions.md`) or the code. Never hand-edit `SKILL.md`.
2. `python -m unittest discover -s tests` (expect 57 tests, 2 skipped).
3. `python chatgpt-plugin/make_package.py` (rebuilds the zip in `Downloads\out` and rewrites `SKILL.md`).
4. Raise `version` in `.claude-plugin/plugin.json` (Claude only notices updates when the version changes).
5. Commit, merge to `main` (Claude reads `main`), push.
6. Claude users: refresh the marketplace, update the plugin, start a new session. ChatGPT users: replace the custom GPT's instruction and knowledge file by hand.

Typical changes: a new cable colour or type (`data/cable_types.json`), a new library component (update the workbook, run `import_dataset.py`), a footer change (`scripts/footer.py`, then every user must update), wording of the instruction.

## Things people get wrong
- **"It is trained on our data."** No. See the first section.
- **Editing files on a PC and expecting Claude to change.** Claude uses its own cached copy; only a pushed, version-raised update reaches it.
- **Hand-written Visio files.** The AI must never write the `.vsdx` itself: Visio rejects it (wrong XML namespace, missing shape geometry, missing package parts). Only `build_diagram.py` writes the file, on top of `base/base.vsdx`.
- **Expecting identical output every run.** The AI is a language model, so layouts and picture choices differ between runs. Only the footer and cable colours are guaranteed.

## Known limits and open items
- **Pictures are best-effort.** They need the AI's tool to download from the web (ChatGPT's code sandbox sometimes has no internet; Claude Code on a PC does but asks permission). If it cannot, items become plain boxes or library pictures. Users can swap pictures in Visio.
- **Picture licensing.** Web pictures (supplier photos, SAP/QGIS/Wazuh logos, stock icons) may be copyrighted. RPS should decide the policy before diagrams go to clients. Sources are stored in each picture shape's data and noted in the footer.
- **Layout is not checked for neatness.** The program warns about overlaps and lines through shapes but does not fix them. An optional "tidy" layout mode was discussed, not built.
- **Extra items.** The AI may add equipment the user did not ask for (switches, WAN routers). That is allowed by design; reviewers should check the diagram against the request.
- **Library is partial.** Only about 37 components have pictures; field transmitters, SIEM, SAP, GIS, etc. rely on web pictures.
- **Acceptance testing is thin.** It has been tried on one prompt (42 pumping stations, Purdue model). Try at least three real RPS prompts, with a reviewer comparing each result.
- **The old sign-off document is out of date** (it describes the earlier strict approach).
- **The ChatGPT custom GPT is not set up yet.** RPS must confirm their plan allows custom GPTs and Code Interpreter.

## History in one paragraph
The project began as a strict pipeline (BOQ in, validated spec, automatic Purdue layout, every item checked against the component library). RPS then dropped the BOQ and later asked only for a consistent footer and cable colours plus an editable Visio version of what ChatGPT already drew. The strict code was removed in the free-form change (decision D43). It is still in the git history, and the cleanup also left a local copy outside the repo on the original developer's PC (`Downloads\out\removed_in_cleanup\strict_purdue_path`): copy that folder somewhere shared if it may be needed.

## Where things came from
- Footer layout and cable colours: the client's "System Architecture Drawing Instructions" Word document.
- Component library and pictures: `system_architecture_dataset.xlsx` (keep a copy; `import_dataset.py` reads it).
- Every design decision, with the reason: `docs/decisions.md`.
