---
name: architecture-diagram
description: Make an editable one-page A3 Visio (.vsdx) system-architecture diagram (for example a Purdue-model diagram) from the user's request, with the team's fixed footer and cable colours. Use whenever the user asks for an architecture diagram or a Visio file of a system.
---

Do the user's request exactly as you normally would: ask questions, research, design, use any tools or pictures you can. This add-on restricts nothing about that. It only adds three things to the result (pictures are welcome too, see the end):

1. **Footer.** The diagram carries a fixed A3 footer (title block, notes, legend). Give it the values you have: End User, Contractor, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev. Missing ones print TBC.
2. **Cable colours.** Every line is one of these cable types, and its colour is set by the add-on, the same for everyone: ethernet, fibre, modbus, bacnet, hardwired.
3. **Visio output.** The finished diagram is delivered as an editable .vsdx, made by the supplied program (a hand-written .vsdx will not open in Visio).

To produce the file: describe your diagram in a JSON file following docs/diagram-format.md in this plugin's folder (samples/diagram_example.json is an example: shapes with positions and sizes, optional pictures, lines with a cable type), save it in the working folder and run

    python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py" diagram.json --out Architecture.vsdx

Pictures: use your own logic to get the relavant component images from the web. You can do better in searching the latest icons/images of the components asked in the user prompt. Make sure that the images that you use are not always the logos. for example, if i ask for a particular server then you should get a picture/icon that actually looks like a server of that particular brand. Do not draw icons in code or generate them with an image tool unless the download fails for that particular item. A library picture from data/components.json (ids in the "component" field) is also fine where it genuinely is that item. Give the picture file in the shape's "image" field (PNG, or WebP/JPEG/GIF if Pillow is installed) and where it came from in "image_source". Use a plain box only for an item you could not get any picture for, and say which.

If it prints NOT BUILT, fix the JSON and run again. Warnings are suggestions you may act on. Tell the user where Architecture.vsdx and diagram.json are. Say "built" only if the program did.

(The plugin folder is ${CLAUDE_PLUGIN_ROOT}: it holds scripts/, data/, base/, samples/ and docs/. If that variable is empty, it is two folders above this file.)
