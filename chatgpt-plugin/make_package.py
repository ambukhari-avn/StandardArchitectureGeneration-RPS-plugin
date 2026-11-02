"""Also rewrites skills/architecture-diagram/SKILL.md (the Claude plugin) from instructions.md.

Zip what ChatGPT's code tool needs to validate a spec and draw the .vsdx: scripts, data, base, the example diagram and the format reference.

    python chatgpt-plugin/make_package.py [out.zip]      (default: Downloads\\out\\arch_plugin.zip)

Upload the zip to the chat; the instructions tell the model to unzip it and run scripts/build_diagram.py.
Standard library only.
"""
import os
import sys
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
KEEP = ("scripts", "data", "base", "samples", os.path.join("docs", "diagram-format.md"))
SKIP = ("__pycache__", ".pyc", "dev_preview.py", "import_dataset.py", "xlsx_reader.py")                  # development aids, not needed to draw


def files():
    for top in KEEP:
        path = os.path.join(ROOT, top)
        walk = [(path, [], [os.path.basename(path)])] if os.path.isfile(path) else os.walk(path)
        for d, _, names in walk:
            for n in names:
                full = os.path.join(d if not os.path.isfile(path) else os.path.dirname(path), n)
                if not any(s in full for s in SKIP):
                    yield full, os.path.relpath(full, ROOT)


SKILL_HEAD = """---
name: architecture-diagram
description: Make an editable one-page A3 Visio (.vsdx) system-architecture diagram (for example a Purdue-model diagram) from the user's request, with the team's fixed footer and cable colours. Use whenever the user asks for an architecture diagram or a Visio file of a system.
---

"""
SWAPS = (("following docs/diagram-format.md in the attached arch_plugin.zip", "following docs/diagram-format.md in this plugin's folder"),
         ("extract the zip (for example to /mnt/data) and run", "save it in the working folder and run"),
         ("python arch_plugin/scripts/build_diagram.py /mnt/data/diagram.json --out /mnt/data/Architecture.vsdx",
          'python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py" diagram.json --out Architecture.vsdx'),
         ("Give the user download links for Architecture.vsdx and diagram.json.", "Tell the user where Architecture.vsdx and diagram.json are."))


def write_skill():
    """skills/architecture-diagram/SKILL.md for the Claude plugin, made from instructions.md so both platforms share one text."""
    with open(os.path.join(ROOT, "chatgpt-plugin", "instructions.md"), encoding="utf-8") as fh:
        body = fh.read().strip()
    for old, new in SWAPS:
        if old not in body:
            raise SystemExit("instructions.md changed: update SWAPS in make_package.py (missing: %s)" % old[:50])
        body = body.replace(old, new)
    body += ("\n\n(The plugin folder is ${CLAUDE_PLUGIN_ROOT}: it holds scripts/, data/, base/, samples/ and docs/. "
             "If that variable is empty, it is two folders above this file.)\n")
    path = os.path.join(ROOT, "skills", "architecture-diagram", "SKILL.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(SKILL_HEAD + body)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads", "out", "arch_plugin.zip")
    write_skill()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files():
            z.write(full, "arch_plugin/" + rel.replace(os.sep, "/"))
    print("wrote %s (%d files, %.1f MB)" % (out, len(z.namelist()), os.path.getsize(out) / 1e6))
