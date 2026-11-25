# ChatGPT plugin

- `instructions.md` - the text to paste as the first message (or into a custom GPT's instruction field).
- `make_package.py` - makes `arch_plugin_<version>.zip` (scripts, data, base, samples, format references and a `VERSION` file) to upload with it.
  It stops if the version in `.claude-plugin/plugin.json`, `plugin.json`, the marketplace entry, the instructions header and the README differ.
  Always replace the GPT's instructions and its zip together.

The user writes a prompt (optionally attaching an RFQ or BOQ). ChatGPT writes `diagram.json`, runs `scripts/build_diagram.py`, and returns
the editable `.vsdx`. See `docs/diagram-format.md`.
