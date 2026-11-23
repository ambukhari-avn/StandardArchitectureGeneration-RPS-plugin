"""Cable types (label, colour, dash) from data/cable_types.json. Standard library only.

The spec names cables only by id; colour and dash come from here, never from the spec (decisions D6), so the
footer legend and the drawn lines always agree.
"""
import json
import os
import re

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cable_types.json")


class CableError(ValueError):
    pass


class Cables:
    def __init__(self, path=PATH):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.status = raw.get("status", "unknown")          # 'placeholder' until the client's standard is in
        self.by_id = {}
        for c in raw["cables"]:
            if not re.fullmatch(r"#[0-9A-Fa-f]{6}", c.get("color", "")):
                raise CableError("cable %r: colour must be #RRGGBB" % c.get("id"))
            if c.get("pattern") not in (1, 2):
                raise CableError("cable %r: pattern must be 1 (solid) or 2 (dashed)" % c.get("id"))
            if not c.get("label", "").strip() or not c.get("id"):
                raise CableError("every cable needs an id and a label")
            if c["id"] in self.by_id:
                raise CableError("duplicate cable id %r" % c["id"])
            self.by_id[c["id"]] = c
        if not self.by_id:
            raise CableError("no cable types defined")

    def get(self, cid):
        if cid not in self.by_id:
            raise CableError("cable type %r is not defined (known: %s)" % (cid, ", ".join(sorted(self.by_id))))
        return self.by_id[cid]

    def line_style(self, cid):
        """(colour, pattern) for drawing."""
        c = self.get(cid)
        return c["color"], c["pattern"]

    def legend(self, used_ids):
        """Footer legend entries for the cable types actually drawn, in table order. Unknown ids raise."""
        for u in used_ids:
            self.get(u)
        return [{"label": c["label"], "color": c["color"], "pattern": c["pattern"], "kind": "line"}
                for cid, c in self.by_id.items() if cid in set(used_ids)]
