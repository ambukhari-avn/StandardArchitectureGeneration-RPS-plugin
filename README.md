# Architecture diagram generator (ChatGPT and Claude plugin)

Turns an engineer's prompt (optionally with an RFQ or BOQ attached) into an editable one-page A3 Visio `.vsdx`.
The AI (ChatGPT or Claude) designs the diagram and writes a small JSON file that says **what exists, at which Purdue level, in whose scope
and how it connects** (the v2 format, no coordinates, [docs/diagram-format-v2.md](docs/diagram-format-v2.md)); fixed code places and draws it.
What is fixed, so every diagram the team makes looks the same (Avanceon "System Architecture Drawing Instructions"): the **footer** (title
block, notes, scope and cable legends), the **cable styles**, one **band per Purdue level** used with a dark-blue vertical title strip in a sky-blue box, **grey / pink scope
boxes** (Avanceon / Client-Other) and a **plugin version stamp**. Only what the prompt asks for is drawn: no switches, ring, DMZ or servers by
default. Everything else (items, names, models, pictures, protocols) is the AI's. The older free-form coordinates file still builds
(decisions D43, D44-D57).

## Install
- **ChatGPT:** create a custom GPT with `chatgpt-plugin/instructions.md` as its instructions and `arch_plugin.zip` plus the client's Word
  document as knowledge, with Code Interpreter on. Steps in [docs/setup.md](docs/setup.md).
- **Claude (Claude Code / desktop app), needs Python 3:**
  ```
  /plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-plugin
  /plugin install architecture-diagram@rps-architecture
  ```

## Get the code on your laptop (clone)
You need: [Git](https://git-scm.com/downloads), Python 3 (standard library only, no packages required; Pillow is optional, for converting
WebP/JPEG pictures, for removing the white background of web pictures, and for the PNG preview), and access to the GitHub repo (ask the owner to add your GitHub account if it is private).

```
git clone https://github.com/ambukhari-avn/StandardArchitectureGeneration-RPS-plugin.git
cd StandardArchitectureGeneration-RPS-plugin
git checkout development
python -m unittest discover -s tests
python scripts/build_diagram.py samples/diagram_example.json --out Architecture_test.vsdx
```
`main` is the released version (Claude installs from it); day-to-day work happens on `development` or a feature branch. The tests should
pass (221 tests; 2 are skipped unless the environment variable `ARCH_BASE_VSDX` points at `base\base.vsdx`, which tests the file writer) and the last command should print `built` and create a file that opens in Visio.

To make a change: `git checkout -b feature/<what-you-change>`, edit, run the tests, commit, push the branch, and open a pull request into
`development`. Release steps (raise the version, `make_package.py`, merge to `main`) are in [docs/handover.md](docs/handover.md).

## Layout
```
chatgpt-plugin/   instructions.md (paste into ChatGPT), make_package.py (builds arch_plugin.zip; also rewrites the Claude skill), README
.claude-plugin/   Claude plugin + marketplace manifests;  skills/architecture-diagram/SKILL.md (generated from instructions.md)
scripts/          Python standard library only:
                  build_diagram.py   diagram.json -> .vsdx (the one command the AI runs); prints the build report
                  compile_v2.py      v2 spec (meaning) -> free-form spec: validation, questions, placement, redundancy, rings
                  levels.py          Purdue levels, header and scope colours
                  find_component.py  look a component up in the library before searching the web
                  imaging.py         removes the white background of web pictures (Pillow, optional)
                  vsdx_writer, footer, footer_form, textfit, draw, cables, components   writing the page
                  import_dataset, xlsx_reader   refresh the component library from the dataset workbook (development)
                  dev_preview       PNG preview, needs Pillow (development)
data/             cable_types.json, footer_form.json, level_hints.json, components.json + components_extra.json + icons/ (library pictures)
base/             avanceon_logo.png, base.vsdx (empty A3 page on a Visio-made package skeleton)
samples/          diagram_example.json (free-form), diagram_example_v2.json (redundant PLCs), diagram_example_ring_v2.json (fibre ring)
docs/             handover.md (start here), setup.md (ChatGPT and Claude setup), diagram-format-v2.md (the format the AI writes),
                  diagram-format.md (the free-form format it compiles to), decisions.md, dataset-import-report.md
tests/
```

## Try it
```
python -m unittest discover -s tests
python scripts\build_diagram.py samples\diagram_example.json --preview        (free-form file)
python scripts\build_diagram.py samples\diagram_example_v2.json --preview     (v2 file: prints ADDED BY RULE / ASSUMED / PICTURES / WARNINGS)
python scripts\find_component.py S7                                          (library lookup)
```
Output goes to `Downloads\out`. To make the zip for ChatGPT (this also regenerates the Claude skill): `python chatgpt-plugin\make_package.py`.
