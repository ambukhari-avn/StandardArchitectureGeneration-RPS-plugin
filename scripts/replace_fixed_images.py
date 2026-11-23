"""Replace explicitly approved library assets without altering supplied PNG bytes.

Offline maintenance only, never run during diagram generation.
Usage: python scripts/replace_fixed_images.py <clipboard folder>
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLACEMENTS = {
    'firewall': '8aaa635b-6460-4a81-a4f4-fe5636213fe5',
    'fiber_optic_patch_panel': '430bff8d-39f3-4aab-9816-57f80ad4d890',
    'ethernet_switch': '9bcde536-3995-4aac-b43c-b9408f977d2d',
    'video_wall': 'aea6b824-1358-4c8a-970f-8610869680aa',
    'ethernet_switch_variant': '12da9f96-8b5f-4173-ae86-815540c60e0f',
}


def main(folder):
    registry = ROOT / 'data' / 'fixed_components.json'
    data = json.loads(registry.read_text(encoding='utf-8'))
    # Read every input before changing the library.
    inputs = {cid: (Path(folder) / ('codex-clipboard-' + source + '.png')).read_bytes()
              for cid, source in REPLACEMENTS.items()}
    for cid, raw in inputs.items():
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Not a PNG: ' + cid)
    for component in data['components']:
        cid = component['id']
        if cid not in inputs:
            continue
        raw = inputs[cid]
        (ROOT / 'data' / component['picture']).write_bytes(raw)
        (ROOT / 'data' / 'fixed' / 'originals' / (cid + '.png')).write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        component.update(source='User-approved high-resolution replacement, 2026-11-23',
                         original_sha256=digest, sha256=digest,
                         processing='None. Original high-resolution PNG bytes and supplied alpha preserved exactly.')
    registry.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print('Replaced five approved assets with original high-resolution PNGs. Laptop unchanged.')


if __name__ == '__main__':
    main(sys.argv[1])
