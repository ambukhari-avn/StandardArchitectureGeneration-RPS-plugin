"""Also rewrites skills/architecture-diagram/SKILL.md (the Claude plugin) from instructions.md.

Zip what ChatGPT's code tool needs to validate a spec and draw the .vsdx: scripts, data, base, the example diagram and the format reference.

    python chatgpt-plugin/make_package.py [out.zip]      (default: Downloads\\out\\arch_plugin_<version>.zip)

Upload the zip to the chat; the instructions tell the model to unzip it and run scripts/build_diagram.py.
Standard library only.
"""
import os
import sys
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
KEEP = ("scripts", "data", "base", "samples", os.path.join("docs", "diagram-format.md"), os.path.join("docs", "questionnaire-workflow.md"),
        os.path.join("docs", "mandatory-drawing-rules.md"), os.path.join("docs", "equipment-sizing-rules.md"), os.path.join("docs", "web-first-images.md"), os.path.join("docs", "fixed-library.md"), os.path.join("docs", "reference-layout.md"), os.path.join("docs", "reference-style.png"), os.path.join("docs", "reference-dashes.png"))
SKIP = ("__pycache__", ".pyc", "import_dataset.py", "xlsx_reader.py", os.path.join("samples", "examples"))


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
         ("extract the zip (for example to /mnt/data) and run", "save it in a temporary folder (not the user's output folder) and run"),
         ("python arch_plugin/scripts/build_diagram.py /mnt/data/diagram.json --out /mnt/data/Architecture.vsdx",
          'python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py" <temporary folder>/diagram.json --out Architecture.vsdx'),
         ("Give the user only Architecture.vsdx and architecture_spec.json (keep the specification for later revisions).",
          "Tell the user where Architecture.vsdx is (in the working folder) and keep architecture_spec.json next to it for later revisions."),
         ("python arch_plugin/scripts/arch_spec.py", 'python "${CLAUDE_PLUGIN_ROOT}/scripts/arch_spec.py"'))


def write_skill():
    """skills/architecture-diagram/SKILL.md for the Claude plugin, made from instructions.md so both platforms share one text."""
    with open(os.path.join(ROOT, "chatgpt-plugin", "instructions.md"), encoding="utf-8") as fh:
        body = fh.read().strip()
    v = version()
    gpt_head = body.split("\n", 1)[0]
    if not gpt_head.startswith("**Avanceon Architecture Diagram plugin \u2014 version %s.**" % v):
        raise SystemExit("instructions.md must start with the version %s header" % v)
    body = body.replace(gpt_head, "**Avanceon Architecture Diagram plugin \u2014 version %s** (Claude plugin; the ChatGPT package carries "
                                  "the same version)." % v, 1)
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


def version():
    """The release version. Single source: .claude-plugin/plugin.json."""
    import json
    with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


def version_mismatches():
    """Every place a user can see the version must show the same one, so Claude and ChatGPT installs never mix releases."""
    import json
    v, out = version(), []
    with open(os.path.join(ROOT, "plugin.json"), encoding="utf-8") as fh:
        if json.load(fh).get("version") != v:
            out.append("plugin.json")
    with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as fh:
        if any(p.get("version") != v for p in json.load(fh)["plugins"]):
            out.append(".claude-plugin/marketplace.json")
    with open(os.path.join(ROOT, "chatgpt-plugin", "instructions.md"), encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("**Avanceon Architecture Diagram plugin \u2014 version %s.**" % v) or "if it is not %s," % v not in text:
        out.append("chatgpt-plugin/instructions.md (header)")
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        if "**Current version: %s**" % v not in fh.read():
            out.append("README.md (Current version)")
    return out


if __name__ == "__main__":
    bad = version_mismatches()
    if bad:
        sys.exit("version %s is not shown in: %s. Update them together, then run this again." % (version(), ", ".join(bad)))
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads", "out", "arch_plugin_%s.zip" % version())
    write_skill()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files():
            z.write(full, "arch_plugin/" + rel.replace(os.sep, "/"))
        z.writestr("arch_plugin/VERSION", version() + "\n")
    print("wrote %s (%d files, %.1f MB)" % (out, len(z.namelist()), os.path.getsize(out) / 1e6))
