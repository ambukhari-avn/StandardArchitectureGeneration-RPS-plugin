# Equipment pictures: web first (1.6.0)

**Fixed library (never searched, never replaced unless the prompt explicitly asks):** laptop / engineering laptop, video wall, Ethernet switch (and its alternate, only when requested), fibre optic patch panel. Set the matching `component`. They stay identical in every drawing.

**Every other device** (PLCs, remote I/O racks, SCADA servers, workstations, RTUs, firewalls, instruments, gateways, printers, UPS, ...) is sourced from the web before any library picture is used:

1. Search the web for an image of the actual equipment. With an OEM and model, use exactly that OEM and model. Prefer the manufacturer's site, product catalogue or datasheet.
2. Prefer a high-resolution PNG with a transparent background. Otherwise use a clean product photograph on a plain light background (the builder removes simple backgrounds without touching the equipment). Reject low-resolution, blurry, distorted or watermarked pictures and anything that is not the product.
3. Keep the real proportions. Never stretch a picture.
4. Cache it for the project and record provenance:
   `python scripts/image_cache.py add <downloaded file> --url <source URL> --oem <maker> --model <model>`
   prints the cached path; `image_cache.py find --oem ... --model ...` returns it when the same equipment appears again (download once, reuse everywhere in the project). `provenance.json` in the cache keeps URL, OEM, model, SHA-256 and date.
5. In the diagram file give the shape `"image": <cached path>`, `"image_source": <URL>`, `"oem"` and `"model"`. The component id may stay: it supplies the caption and is the offline fallback. The builder keeps the source in the Visio shape data.
6. For equipment without a specified model use a representative industrial product picture and treat it as illustrative: leave out `oem`/`model` (never invent them) and say so.
7. **No web access, or no suitable picture:** use the technically appropriate library picture (`component`) and report the fallback to the user. The builder prints a `notice:` for every device that used a fallback, and for every web picture missing `image_source`, `oem` or `model`; relay these.
8. Never mislabel a generic picture as an exact product and never invent a model. If the shell cannot download, ask the user to attach the picture.

Setting top-level `"image_policy": "library"` switches off the fallback notices (for a drawing deliberately made from library pictures).
