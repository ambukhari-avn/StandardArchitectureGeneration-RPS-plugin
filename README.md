# Architecture diagram generator (ChatGPT and Claude plugin)

**Current version: 1.7.2** (the same release for Claude and ChatGPT). Install both from the same `main` commit:

| Where | What to install | How to confirm the version |
|---|---|---|
| Claude | `/plugin marketplace update rps-architecture`, then update `architecture-diagram`, then start a new session | `/plugin` shows architecture-diagram 1.7.2 |
| ChatGPT (custom GPT) | Replace **both** the instructions (`chatgpt-plugin/instructions.md`) and the knowledge file (`arch_plugin_1.7.2.zip`) | The instructions start with "version 1.7.2"; the zip contains `arch_plugin/VERSION` = 1.7.2 |

Never mix an old zip with new instructions (or the reverse): the GPT stops and says so. Previous releases: branches `release/v1.7.1`, `release/v1.7.0` and `release/v1.6.0`.

## Version history

Version 1.7.2 moves correctness from the instructions into the engine (plan and conflicts resolved: [docs/v1.7.2-plan.md](docs/v1.7.2-plan.md)). One order of authority (locked template > confirmed specification > engineering rules > engine layout > presentation); `verify-diagram` / `--check-spec` refuse a drawing that changes confirmed quantities, units, connections or placement. The preview is rendered from the built page and locks the layout (`--preview` writes `<out>.layout.json`; `--locked-layout` exports only an identical layout). Functional rows for every layer, relative placement (`place --left-of/--right-of`) and layer heights from requirements. Logical connections are kept separately from their drawing: common network buses, point-to-point, cross-connections, chains, rings and consolidated hardwired (`edit-connection --display`, `layout --buses off`). Routing corridors per layer, attachment on the equipment picture, minimum clearances, locked `waypoints`. Minimum displayed sizes per equipment category with PLC and remote I/O first (`data/equipment_sizes.json`). An offline instrument library (35 drawn illustrations) with ISA-5.1 tag balloons as the last fallback, never a generic picture for an instrument. Every quality check is blocking with automatic correction (up to six passes); nothing is written while a defect remains. Revisions keep unaffected pictures, waypoints and weights (`to-diagram --previous`). Footer, logo, scope colours, cable legend, fixed artwork and editable A3 Visio are unchanged.

Version 1.7.1 shows one version everywhere so Claude and ChatGPT installs cannot mix releases: the marketplace entry, the instructions and Claude skill header, a `VERSION` file inside the ChatGPT zip and the zip name (`arch_plugin_1.7.1.zip`). The GPT refuses to draw when its instructions and zip differ; `make_package.py` and `tests/test_version.py` stop on any mismatch. No drawing changes from 1.7.0.

Version 1.7.0 also applies the Phase 7-12 appearance rules: vertical navy layer headings, content- and cable-sized layers, no boxes around Avanceon equipment, a representative I/O rack where the topology allows, control-layer order I/O → PLC → switches → FO panels, a field layer with instruments only, configurable arrowheads, separated cable tracks, automatic drawing checks on every build (`defect:` lines) and a locked header/footer/logo template. Acceptance examples A-D (questionnaire transcript, request, specification, Visio and preview) are in `samples/examples/`. The previous release is preserved on the `release/v1.6.0` branch.

Version 1.7.0 adds the [standardized architecture questionnaire](docs/questionnaire-workflow.md): project details, any combination of Purdue layers (now with separate Level 5 External and custom layers), equipment per layer, dynamically generated connectivity questions, an editable review/request, generation from a structured specification (`scripts/arch_spec.py`, `architecture_spec.json`) and targeted revisions that keep unrelated equipment and ids.

Version 1.4.0 adds the [mandatory drawing rules](docs/mandatory-drawing-rules.md), representative hardwire labels and explanatory notes. Technical topology review supplements structural checks. Previously fixed images, page fitting, header/footer styling, scope colours and cable colours are preserved.

Version 1.3.1 fits root equipment blocks across the available page width with equal narrow margins. Descriptions use a shallow row above the blocks, and the layout reserves no blank left column.

Version 1.3.0 matches the new header/footer reference: compact navy heading tabs and one continuous rectangular footer with shared dividers.

Version 1.2.2 removes the GSM module from the library, sample and packaged assets.

Turns an engineer's prompt (optionally with an RFQ or BOQ attached) into an editable one-page A3 Visio `.vsdx`.
Version 1.2.1 replaces five approved library pictures with the user's original high-resolution transparent PNGs, preserving their bytes and native detail exactly. The laptop keeps its existing approved version.
The current library contains six [fixed equipment images](docs/fixed-library.md): Ethernet switch (plus alternate), fiber optic patch panel, firewall, Avanceon laptop and video wall. They are used before web pictures and embedded unchanged unless the prompt explicitly requests a replacement. User-approved local background removal and mild enhancement preserve the supplied designs; tiny originals still limit fine detail.
Version 1.1.0 uses the latest [boxed reference layout](docs/reference-layout.md): navy tabs with white bold layer names, content-sized layers with a larger PLC/control area, nested equipment groups, optional requested side panels, shared instrument-to-I/O wiring and a joined rectangular footer. The existing cable colours are unchanged. Try `python scripts/build_diagram.py samples/reference_boxed.json --out out/Architecture.vsdx --preview`. Older layouts remain available with `layout_style: "legacy"`.
ChatGPT designs the diagram and writes a small JSON file; fixed code draws it. The **footer**, **cable colours**, and **approved image library** provide consistent defaults across diagrams. Fixed pictures change only when the prompt explicitly requests it.

## Install
- **ChatGPT:** create a custom GPT with `chatgpt-plugin/instructions.md` as its instructions and `arch_plugin_1.7.2.zip` plus the client's Word
  document as knowledge, with Code Interpreter on. Steps in [docs/setup.md](docs/setup.md).
- **Claude (Claude Code / desktop app), needs Python 3:**
  ```
  /plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-plugin
  /plugin install architecture-diagram@rps-architecture
  ```

## Get the code on your laptop (clone)
You need: [Git](https://git-scm.com/downloads), Python 3 (standard library only, no packages required; Pillow is optional, for converting
WebP/JPEG pictures and for the PNG preview), and access to the GitHub repo (ask the owner to add your GitHub account if it is private).

```
git clone https://github.com/ambukhari-avn/StandardArchitectureGeneration-RPS-plugin.git
cd StandardArchitectureGeneration-RPS-plugin
git checkout development
python -m unittest discover -s tests
python scripts/build_diagram.py samples/diagram_example.json --out Architecture_test.vsdx
```
`main` is the released version (Claude installs from it); day-to-day work happens on `development` or a feature branch. The tests should
pass and the last command should print `built` and create an editable Visio file.

To make a change: `git checkout -b feature/<what-you-change>`, edit, run the tests, commit, push the branch, and open a pull request into
`development`. Release steps (raise the version, `make_package.py`, merge to `main`) are in [docs/handover.md](docs/handover.md).

## Layout
```
chatgpt-plugin/   instructions.md (paste into ChatGPT), make_package.py (builds arch_plugin.zip; also rewrites the Claude skill), README
.claude-plugin/   Claude plugin + marketplace manifests;  skills/architecture-diagram/SKILL.md (generated from instructions.md)
scripts/          Python standard library only:
                  build_diagram.py   diagram.json -> .vsdx (the one command ChatGPT runs)
                  vsdx_writer, footer, footer_form, textfit, draw, cables, components   writing the page
                  import_dataset, xlsx_reader   refresh the component library from the dataset workbook (development)
                  dev_preview       PNG preview, needs Pillow (development)
data/             cable_types.json, footer_form.json, components.json + icons/ (library pictures)
base/             avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/          diagram_example.json
docs/             handover.md (start here), setup.md (ChatGPT and Claude setup), diagram-format.md (the JSON format), decisions.md, dataset-import-report.md
tests/
```

## Try it
```
python -m unittest discover -s tests
python scripts\build_diagram.py samples\diagram_example.json --preview
```
Output goes to `Downloads\out`. To make the zip for ChatGPT (this also regenerates the Claude skill): `python chatgpt-plugin\make_package.py`.
