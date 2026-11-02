# ChatGPT plugin

- `instructions.md` - the text to paste as the first message (or into a custom GPT's instruction field).
- `make_package.py` - makes `arch_plugin.zip` (scripts, data, base, sample, format reference) to upload with it.

The user writes a prompt (optionally attaching an RFQ or BOQ). ChatGPT writes `diagram.json`, runs `scripts/build_diagram.py`, and returns
the editable `.vsdx`. See `docs/diagram-format.md`.
