"""Load the component dataset (data/components.json, produced by import_dataset.py). Standard library only."""
import json
import os
import hashlib
import re

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA = os.path.join(ROOT, "data")


class Components:
    def __init__(self, path=os.path.join(DATA, "components.json")):
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.source = raw["source"]
        self._dir = os.path.dirname(os.path.abspath(path))
        self.all = raw["components"]
        fixed_path = os.path.join(self._dir, 'fixed_components.json')
        self.fixed = {}
        self.fixed_aliases = {}
        if os.path.exists(fixed_path):
            with open(fixed_path, encoding='utf-8') as fh:
                loaded = json.load(fh)['components']
            # Only entries with "fixed": true are approved fixed images. Others in this file stay in the
            # library as offline fallbacks (equipment is sourced from the web first).
            fixed = [c for c in loaded if c.get('fixed')]
            self.fixed = {c['id']: c for c in fixed}
            loaded_ids = {c['id'] for c in loaded}
            self.all = [c for c in self.all if c['id'] not in loaded_ids] + loaded
            for c in fixed:
                for alias in [c['id'], c['label']] + c['aliases']:
                    self.fixed_aliases[self.normalise(alias)] = c['id']
        self.by_id = {c["id"]: c for c in self.all}
        if len(self.by_id) != len(self.all):
            raise ValueError("duplicate component ids in %s" % path)
        for c in self.all:
            if c["duplicate_of"] and c["duplicate_of"] not in self.by_id:
                raise ValueError("%s: duplicate_of %r is not a component" % (c["id"], c["duplicate_of"]))

    def get(self, cid):
        """Component by id; an exact repeat resolves to the component it repeats."""
        c = self.by_id[cid]
        return self.by_id[c["duplicate_of"]] if c["duplicate_of"] else c

    def distinct(self):
        return [c for c in self.all if not c["duplicate_of"]]

    def picture_path(self, cid):
        """Absolute path of the component's PNG, or None if it is drawn as a box."""
        p = self.get(cid)["picture"]
        if not p:
            return None
        full = os.path.join(self._dir, p)
        if not os.path.exists(full):
            raise FileNotFoundError("picture for %s is listed but missing: %s" % (cid, full))
        comp = self.get(cid)
        if comp.get('fixed'):
            with open(full, 'rb') as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            if digest != comp['sha256']:
                raise ValueError('Fixed image changed: %s. Restore the approved asset or explicitly update the library.' % cid)
        return full

    @staticmethod
    def normalise(value):
        return re.sub(r'[^a-z0-9]+', ' ', str(value).lower()).strip()

    def fixed_for(self, label):
        """Exact category/alias matches only; never guess a manufacturer's model."""
        return self.fixed_aliases.get(self.normalise(label))

    def layers(self):
        return sorted({c["layer"] for c in self.all})
