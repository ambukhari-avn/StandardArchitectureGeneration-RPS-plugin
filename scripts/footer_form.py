"""The footer form: what the /arch command asks, and how a filled-in form is read back. Standard library only.

The questions live in data/footer_form.json (the single source of truth). A filled form can be plain text,
one 'Label: value' per line, or JSON keyed by field key:

    Client: King Saud University
    Project: ...
    ...
    Notes:
    Two ASPs are considered for each existing building.
    Redundant networking is considered for each building.

Unknown labels and stray lines are rejected instead of guessed at.
"""
import json
import os
import re

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "footer_form.json")


class FormError(ValueError):
    pass


def load_template(path=TEMPLATE):
    with open(path, encoding="utf-8") as fh:
        t = json.load(fh)
    return t["fields"], t.get("notes_label", "Notes")


def blank_form_text(path=TEMPLATE):
    """The form as plain text for the user to fill in (defaults pre-filled)."""
    fields, notes_label = load_template(path)
    lines = ["%s: %s" % (f["label"], f.get("default", "")) for f in fields]
    return "\n".join(lines + ["%s:" % notes_label, ""])


def parse_form(text, path=TEMPLATE):
    """Filled form (text or JSON) -> (fields dict keyed by field key, notes list). Blank values are omitted."""
    fields, notes_label = load_template(path)
    by_label = {}
    for f in fields:                                    # a form that still says "End User:" parses through the alias
        for name in [f["label"]] + list(f.get("aliases", [])):
            by_label[name.lower()] = f["key"]
    keys = {f["key"] for f in fields}
    key_alias = {a: f["key"] for f in fields for a in f.get("key_aliases", [])}
    out, notes = {}, []
    if text.lstrip().startswith("{"):
        data = {key_alias.get(k, k): v for k, v in json.loads(text).items()}
        unknown = set(data) - keys - {"notes"}
        if unknown:
            raise FormError("unknown form key(s): %s" % ", ".join(sorted(unknown)))
        out = {k: v for k, v in data.items() if k != "notes" and str(v).strip()}
        notes = [str(n).strip() for n in data.get("notes", []) if str(n).strip()]
        return out, notes
    in_notes = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^([^:]+?)\s*:\s*(.*)$", line)
        label = m.group(1).lower() if m else None
        if label == notes_label.lower():
            in_notes = True
            if m.group(2).strip():
                notes.append(m.group(2).strip())
        elif label in by_label:
            in_notes = False
            if m.group(2).strip():
                out[by_label[label]] = m.group(2).strip()
        elif in_notes:
            notes.append(re.sub(r"^\d+[.)]\s*", "", line))      # drop the user's own numbering; the footer numbers notes
        else:
            raise FormError("unrecognised line in form: %r" % line[:60])
    return out, notes
