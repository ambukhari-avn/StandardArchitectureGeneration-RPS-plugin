# ChatGPT plugin

- `instructions.md` - the text to paste as the first message (or into a custom GPT's instruction field).
- `make_package.py` - makes `arch_plugin.zip` (scripts, data, base, samples, format references, `plugin.json` for the version stamp) to upload
  with it, and rewrites the Claude skill `skills/architecture-diagram/SKILL.md` from `instructions.md` (never edit `SKILL.md` by hand).

The user writes a prompt (optionally attaching an RFQ or BOQ). ChatGPT asks its questions once, writes a v2 `diagram.json` (items, levels,
scopes and links, no coordinates), runs `scripts/build_diagram.py`, and returns the editable `.vsdx` with the ASSUMED, PICTURES and WARNINGS
sections of the build report. See `docs/diagram-format-v2.md` (and `docs/diagram-format.md` for the free-form format it compiles to).
`instructions.md` must stay under 8,000 characters (the custom-GPT limit; a test checks it).
