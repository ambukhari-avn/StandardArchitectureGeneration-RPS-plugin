# Architecture diagram generator (ChatGPT and Claude plugin)

Turns an engineer's prompt (optionally with an RFQ or BOQ attached) into an editable one-page A3 Visio `.vsdx`.
ChatGPT designs the diagram and writes a small JSON file; fixed code draws it. Only two things are fixed, so they are the same for
every diagram the team makes: the **footer** (title block, notes, legend) and the **cable colours** (from the client's drawing
instructions). Everything else is free-form (decision D43).

## Install
- **ChatGPT:** create a custom GPT with `chatgpt-plugin/instructions.md` as its instructions and `arch_plugin.zip` plus the client's Word
  document as knowledge, with Code Interpreter on. Steps in [docs/setup.md](docs/setup.md).
- **Claude (Claude Code / desktop app), needs Python 3:**
  ```
  /plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-_plugin
  /plugin install architecture-diagram@rps-architecture
  ```

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
docs/             setup.md (ChatGPT and Claude setup), diagram-format.md (the JSON format), decisions.md, dataset-import-report.md
tests/
```

## Try it
```
python -m unittest discover -s tests
python scripts\build_diagram.py samples\diagram_example.json --preview
```
Output goes to `Downloads\out`. To make the zip for ChatGPT (this also regenerates the Claude skill): `python chatgpt-plugin\make_package.py`.
