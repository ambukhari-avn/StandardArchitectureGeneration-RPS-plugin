# Architecture diagram generator (ChatGPT and Claude plugin)

Turns an engineer's prompt (optionally with an RFQ or BOQ attached) into an editable one-page A3 Visio `.vsdx`.
Version 1.1.0 uses the latest [boxed reference layout](docs/reference-layout.md): rounded light-blue heading cards, content-sized layers with a larger PLC/control area, nested equipment groups, optional requested side panels, shared instrument-to-I/O wiring and a three-card footer. The existing cable colours are unchanged. Try `python scripts/build_diagram.py samples/reference_boxed.json --out out/Architecture.vsdx --preview`. Older layouts remain available with `layout_style: "legacy"`.
ChatGPT designs the diagram and writes a small JSON file; fixed code draws it. Only two things are fixed, so they are the same for
every diagram the team makes: the **footer** (title block, notes, legend) and the **cable colours** (from the client's drawing
instructions). Everything else is free-form (decision D43).

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
