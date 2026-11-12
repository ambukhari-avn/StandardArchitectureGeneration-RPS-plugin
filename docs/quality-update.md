# Reference quality update — 1.0.2

The attached PLC/SCADA reference is bundled as `docs/reference-style.png` and used as an appearance guide. Device counts, process topology and project metadata still come from the current request.

- Cables, FO ring links and legend samples: 1.75 pt. Layer and panel boundaries: 1.5 pt. Outer border: 2.25 pt.
- Pictures retain up to 2400 px instead of 700 px; transparent originals are cropped before resizing. Pillow applies EXIF orientation and Lanczos downsampling, saves lossless PNG, and preserves partial alpha.
- Automatic cleanup removes uniform light backdrops and connected neutral shadows, keeps enclosed white details and avoids guessing at complex backgrounds. `background: "keep"` preserves an intentional backdrop. The fallback PNG reader remains available without Pillow.
- External pictures below 150 source pixels per displayed inch produce a warning; the skill requests 300 for print quality. Upscaling cannot restore missing source detail.
- Previews use 200 dpi, bold fonts, proportional strokes, dashed rounded containers and ellipses. The skill requires visual inspection before delivery.

Validation: run `python -m unittest discover -s tests`, then `python scripts/build_diagram.py samples/reference_quality.json --out Architecture.vsdx --preview`. The image fixtures are for offline verification; production diagrams follow the skill's picture sourcing instructions.

This changes local source and the local plugin installation only. No upstream GitHub release is published. Rendering is verified through the builder and PNG preview; opening the result in Microsoft Visio remains a separate application check.
