# Approved fixed equipment images

Version 1.2.0 uses library images before web images. The seven approved cutouts
are indexed in `data/fixed_components.json`, alongside aliases and SHA-256 hashes.

| Component | Default use |
| --- | --- |
| `ethernet_switch` | Ethernet/network/SCADA switch |
| `fiber_optic_patch_panel` | Fiber/fibre optic patch panel, FO patch panel, FOPP |
| `firewall` | Firewall symbol |
| `laptop` | Laptop / engineering laptop, preserving Avanceon screen branding |
| `video_wall` | Video wall |
| `gsm_module` | GSM module / GSM modem symbol |
| `ethernet_switch_variant` | Alternate switch, only when requested |

Eight attachments contained seven unique images: the last two were identical.
Originals are retained in `data/fixed/originals/`. These are user-supplied
illustrations, not identification of specific equipment brands or models.

The user approved local processing after the built-in image editor failed to
connect. Edge-connected black backgrounds were removed, including around the
laptop; enclosed black details remain. The video wall has no exterior backdrop
to remove: the entire rectangle is screen content. Transparent margins were
added. Lanczos enlargement and mild sharpening smooth small images without
recovering missing details; the dark GSM symbol was brightened for legibility.
`scripts/import_fixed_images.py` records the reproducible offline workflow and
is never run during drawing generation.

Use `component` explicitly. Exact category labels also resolve automatically.
Fixed cutouts bypass runtime background cleanup and are embedded unchanged;
hash mismatches stop the build. No web search or image change is allowed for
these categories unless the current user prompt explicitly asks for one.
Model names alone do not authorize replacing the fixed category image.

An explicitly requested replacement uses `image`, `image_source`, and
`image_override: true`. This flag records authorization from the prompt; the
generator cannot independently verify the conversation. Updating the approved
library itself also requires an explicit user request and a new approved hash.
For uncovered categories, use the existing component library first, then request
a suitable image; download web images only with prompt authorization.
