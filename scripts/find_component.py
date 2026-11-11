#!/usr/bin/env python3
"""Look a component up in the library before looking anywhere else for a picture.   Standard library only.

    python scripts/find_component.py "S7"
    python scripts/find_component.py "siemens plc"

Searches the title, brand, part number, layer and id of every component in data/components.json and data/components_extra.json (every word
you type must appear somewhere in those fields; case does not matter) and prints the matching ids. A library component always wins over a
picture from the web: when this finds the right one, use it as the item's "component". Exit status 0 = at least one match, 1 = none.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from components import Components

FIELDS = ("id", "title", "label", "brand", "part_number", "layer")


def find(text, comps=None):
    """The library components (exact repeats left out) whose fields contain every word of `text`, best match first."""
    comps = comps or Components()
    words = [w.lower() for w in str(text).split() if w.strip()]
    if not words:
        return []
    hits = []
    for c in comps.distinct():
        hay = " | ".join(str(c.get(f) or "") for f in FIELDS).lower()
        if all(w in hay for w in words):
            title = " ".join(str(c.get(f) or "") for f in ("id", "title", "brand")).lower()
            score = (sum(1 for w in words if w in title), c["id"] == text.strip().lower())      # words found in the id/title/brand rank first
            hits.append((score, c))
    hits.sort(key=lambda h: (not h[0][1], -h[0][0], h[1]["id"]))
    return [c for _, c in hits]


def describe(c, comps):
    return "%-36s %s%s%s  [%s]  %s%s" % (
        c["id"], c["title"], " - " + c["brand"] if c.get("brand") else "", " (" + c["part_number"] + ")" if c.get("part_number") else "",
        c["layer"], "picture" if c.get("picture") else "no picture (drawn as a box)", "  [extra]" if c["id"] in comps.extra_ids else "")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("text", nargs="+", help="words to look for, e.g. S7  or  siemens plc")
    args = ap.parse_args(argv)
    comps = Components()
    hits = find(" ".join(args.text), comps)
    if not hits:
        print("No library component matches %r. Next: look for the exact model's picture on the manufacturer's own site, "
              "else a generic picture of that kind of instrument, else leave the item without a picture (it is drawn as a labelled box)."
              % " ".join(args.text))
        return 1
    for c in hits:
        print(describe(c, comps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
