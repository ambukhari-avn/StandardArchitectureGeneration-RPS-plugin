# Reference quality update — 1.0.2

## Follow-up — 1.0.3

- Short, closely spaced dashes throughout cables, ring ellipses/links, containers and legends. Internal pattern 2 now exports as native Visio pattern 23; the preview uses 2.5 pt strokes and 1.25 pt gaps. Pattern 23 is documented as tiny dashed in Microsoft's [VSDX line-pattern specification](https://learn.microsoft.com/en-us/openspecs/sharepoint_protocols/ms-vsdx/f718c500-6066-4fcc-8b66-4bb5015f133f).
- Continuous 1.5 pt blue vertical dividers separate layer headings from components. Zone borders are also bold blue.
- Footer grid borders are blue, 1.5 pt inside and 2 pt outside. Field text, scope labels and legend labels are bold, with text fitting measured in bold.
- Every bitmap Foreign shape explicitly disables inherited fill, outline and shadow, including its geometry, preventing template fills from showing as black rectangular frames. Original PNG alpha and black device details remain intact. This addresses generated frame boxes; baked-in source backgrounds still require a clean cutout.
- Updated references: `reference-style.png` and `reference-dashes.png`. Package-level tests inspect actual VSDX image-frame and dash cells. Native Microsoft Visio display remains to be checked in that application.

## Original quality changes

The attached PLC/SCADA reference is bundled as `docs/reference-style.png` and used as an appearance guide. Device counts, process topology and project metadata still come from the current request.

- Cables, FO ring links and legend samples: 1.75 pt. Layer and panel boundaries: 1.5 pt. Outer border: 2.25 pt.
- Pictures retain up to 2400 px instead of 700 px; transparent originals are cropped before resizing. Pillow applies EXIF orientation and Lanczos downsampling, saves lossless PNG, and preserves partial alpha.
- Automatic cleanup removes uniform light backdrops and connected neutral shadows, keeps enclosed white details and avoids guessing at complex backgrounds. `background: "keep"` preserves an intentional backdrop. The fallback PNG reader remains available without Pillow.
- External pictures below 150 source pixels per displayed inch produce a warning; the skill requests 300 for print quality. Upscaling cannot restore missing source detail.
- Previews use 200 dpi, bold fonts, proportional strokes, dashed rounded containers and ellipses. The skill requires visual inspection before delivery.

Validation: run `python -m unittest discover -s tests`, then `python scripts/build_diagram.py samples/reference_quality.json --out Architecture.vsdx --preview`. The image fixtures are for offline verification; production diagrams follow the skill's picture sourcing instructions.

This changes local source and the local plugin installation only. No upstream GitHub release is published. Rendering is verified through the builder and PNG preview; opening the result in Microsoft Visio remains a separate application check.
