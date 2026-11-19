"""Reproduce the user-approved local cleanup of the November 2026 supplied assets.

Offline only; never called by diagram generation. No device details are invented.
Usage: python scripts/import_fixed_images.py <folder containing clipboard PNGs>
"""
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = [
    ('ethernet_switch', 'Ethernet switch', 'f99a7952-e424-450d-9b74-caf1df477533', ['ethernet switch', 'network switch', 'scada switch']),
    ('fiber_optic_patch_panel', 'Fiber optic patch panel', '2f80a656-bb57-462b-b8cf-6396921a6437', ['fiber optic patch panel', 'fibre optic patch panel', 'fo patch panel', 'fopp']),
    ('firewall', 'Firewall', 'ab7eaf00-c312-4d6b-82b1-c793b6d0e0ad', ['firewall']),
    ('laptop', 'Laptop', 'f7c69e82-6261-4e6e-bb1f-9c107a7c08fb', ['laptop', 'engineering laptop']),
    ('video_wall', 'Video wall', 'd7537bf4-8fa2-4f0f-be4c-d65394ce4f36', ['video wall', 'videowall']),
    ('gsm_module', 'GSM module', '24b472f2-d9f4-429a-b856-97bfe304bae0', ['gsm module', 'gsm modem']),
    ('ethernet_switch_variant', 'Ethernet switch (alternate)', 'd0bb0e42-ab97-462c-a3d9-e8c3cd612e6b', ['ethernet switch alternate', 'alternate ethernet switch']),
]


def clean(source, cid):
    im = Image.open(source).convert('RGBA')
    if cid != 'video_wall':
        # Edge-connected black only: enclosed black ports and screen details stay.
        threshold = 3 if cid != 'laptop' else 7
        px = im.load()
        w, h = im.size
        seen, q = set(), deque()
        def add(x, y):
            if (x, y) not in seen and max(px[x, y][:3]) <= threshold:
                seen.add((x, y))
                q.append((x, y))
        for x in range(w):
            add(x, 0); add(x, h - 1)
        for y in range(h):
            add(0, y); add(w - 1, y)
        while q:
            x, y = q.popleft()
            px[x, y] = (0, 0, 0, 0)
            for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if 0 <= nx < w and 0 <= ny < h:
                    add(nx, ny)
    bounds = im.getchannel('A').getbbox()
    if not bounds:
        raise ValueError('Cleanup removed the entire image: ' + cid)
    im = im.crop(bounds)
    alpha = im.getchannel('A')
    rgb = im.convert('RGB')
    if cid == 'gsm_module':
        # Supplied symbol peaks at 53/255. Lift the existing dark grey for legibility.
        rgb = ImageEnhance.Brightness(rgb).enhance(3.2)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.04)
    rgb.putalpha(alpha)
    # Interpolation smooths low-resolution edges; it cannot recover missing detail.
    target = 1000 if cid == 'laptop' else 600
    scale = target / max(rgb.size)
    rgb = rgb.resize((max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale))), Image.Resampling.LANCZOS)
    a = rgb.getchannel('A')
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1, percent=75, threshold=3))
    rgb.putalpha(a)
    return ImageOps.expand(rgb, border=8, fill=(0, 0, 0, 0))


def main(folder):
    dest = ROOT / 'data' / 'fixed'
    originals = dest / 'originals'
    originals.mkdir(parents=True, exist_ok=True)
    items = []
    for cid, label, clipboard, aliases in ASSETS:
        source = Path(folder) / ('codex-clipboard-' + clipboard + '.png')
        raw = source.read_bytes()
        (originals / (cid + '.png')).write_bytes(raw)
        output = dest / (cid + '.png')
        clean(source, cid).save(output, dpi=(300, 300), optimize=True)
        items.append(dict(id=cid, label=label, title=label, layer='User-approved', brand=None,
                          part_number=None, confidence='User-supplied illustration; not model identification',
                          picture='fixed/' + cid + '.png', duplicate_of=None, source_row=None,
                          fixed=True, aliases=aliases, source='User attachment, November 2026',
                          original_sha256=hashlib.sha256(raw).hexdigest(),
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                          processing='Edge-connected black removal (video wall: retained screen content); Lanczos interpolation and mild sharpening; GSM contrast lift. No new detail.'))
    (ROOT / 'data' / 'fixed_components.json').write_text(json.dumps({'components':items}, indent=2)+'\n', encoding='utf-8')
    print('Imported 7 unique fixed images; attachments 7 and 8 are duplicates.')


if __name__ == '__main__':
    main(sys.argv[1])
