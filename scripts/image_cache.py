"""Per-project cache of web-sourced equipment pictures, with provenance. Standard library only.

    python image_cache.py add <downloaded-file> --url <source page or file URL> --oem <maker> --model <model> [--cache <dir>]
    python image_cache.py find --oem <maker> --model <model> [--cache <dir>]
    python image_cache.py list [--cache <dir>]

`add` copies the file into the cache (named after OEM and model, so the same equipment is downloaded once and reused
for every drawing of the project) and records the source URL, OEM, model, SHA-256 and date in provenance.json.
`find` prints the cached path (exit status 1 when the picture is not cached yet). Put the printed path in the shape's
"image" together with "image_source", "oem" and "model"; the builder keeps them in the Visio shape data.
Never invent an OEM or model: leave them out and describe the picture as a representative illustration instead.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

DEFAULT_CACHE = "image_cache"
INDEX = "provenance.json"


def slug(*parts):
    return re.sub(r"[^a-z0-9]+", "-", " ".join(p for p in parts if p).lower()).strip("-") or "picture"


def _load(cache):
    path = os.path.join(cache, INDEX)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {"pictures": []}


def _save(cache, data):
    with open(os.path.join(cache, INDEX), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def find(oem, model, cache=DEFAULT_CACHE):
    """Path of the cached picture for this OEM and model, or None."""
    key = slug(oem, model)
    for entry in _load(cache)["pictures"]:
        path = os.path.join(cache, entry["file"])
        if entry["key"] == key and os.path.exists(path):
            return path
    return None


def add(src, url, oem, model, cache=DEFAULT_CACHE):
    """Copy a downloaded picture into the cache and record where it came from. Returns the cached path."""
    if not url or not str(url).lower().startswith(("http://", "https://")):
        raise ValueError("a source URL (http/https) is required for provenance")
    if not (oem and model):
        raise ValueError("give both --oem and --model (a representative illustration needs no cache entry)")
    if not os.path.isfile(src):
        raise ValueError("no such file: %s" % src)
    os.makedirs(cache, exist_ok=True)
    key = slug(oem, model)
    ext = os.path.splitext(src)[1].lower() or ".png"
    name = key + ext
    dest = os.path.join(cache, name)
    shutil.copyfile(src, dest)
    with open(dest, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    data = _load(cache)
    data["pictures"] = [e for e in data["pictures"] if e["key"] != key]
    data["pictures"].append(dict(key=key, file=name, oem=oem, model=model, source_url=url, sha256=digest,
                                 fetched=datetime.date.today().isoformat()))
    _save(cache, data)
    return dest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("file")
    a.add_argument("--url", required=True)
    a.add_argument("--oem", required=True)
    a.add_argument("--model", required=True)
    f = sub.add_parser("find")
    f.add_argument("--oem", required=True)
    f.add_argument("--model", required=True)
    sub.add_parser("list")
    for p in (a, f, sub.choices["list"]):
        p.add_argument("--cache", default=DEFAULT_CACHE)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "add":
            print(add(args.file, args.url, args.oem, args.model, args.cache))
        elif args.cmd == "find":
            path = find(args.oem, args.model, args.cache)
            if not path:
                return 1
            print(path)
        else:
            for e in _load(args.cache)["pictures"]:
                print("%s  %s %s  %s" % (e["file"], e["oem"], e["model"], e["source_url"]))
    except ValueError as e:
        print("error:", e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
