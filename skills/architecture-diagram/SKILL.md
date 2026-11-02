---
name: architecture-diagram
description: Make an editable one-page A3 Visio (.vsdx) system-architecture diagram (for example a Purdue-model diagram) from the user's request, with the team's fixed footer and cable colours. Use whenever the user asks for an architecture diagram or a Visio file of a system.
---

Do the user's request exactly as you normally would: ask questions, research, design, use any tools or pictures you can. This add-on restricts nothing about that. It only adds three things to the result (pictures are welcome too, see the end):

1. **Footer.** The diagram carries a fixed A3 footer (title block, notes, legend). Give it the values you have: End User, Contractor, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev. Missing ones print TBC.
2. **Cable colours.** Every line is one of these cable types, and its colour is set by the add-on, the same for everyone: ethernet, fibre, modbus, bacnet, hardwired.
3. **Visio output.** The finished diagram is delivered as an editable .vsdx, made by the supplied program (a hand-written .vsdx will not open in Visio).

To produce the file: describe your diagram in a JSON file following docs/diagram-format.md in this plugin's folder (samples/diagram_example.json is an example: shapes with positions and sizes, optional pictures, lines with a cable type), save it in a temporary folder (not the user's output folder) and run

    python "${CLAUDE_PLUGIN_ROOT}/scripts/build_diagram.py" <temporary folder>/diagram.json --out Architecture.vsdx

Pictures: always search the web for a picture of every item before anything else, including items the component library also covers; do not skip the search because the library seems to have one, and never say the library covers it instead of searching. Search for the latest images of the components named in the prompt. The picture should look like the actual item: if the prompt asks for a particular server, get a picture of that brand's server, not just its logo. Do not draw icons in code or generate them with an image tool unless the download fails for that particular item. Only if the web search or download fails for an item, use a library picture from data/components.json (ids in the "component" field) where it genuinely is that item. Give the picture file in the shape's "image" field (PNG, or WebP/JPEG/GIF if Pillow is installed) and where it came from in "image_source". Use a plain box only for an item you could not get any picture for, and say which.

If it prints NOT BUILT, fix the JSON and run again. Warnings are suggestions you may act on. Keep diagram.json, helper scripts and downloaded pictures in a temporary folder, not in the user's output folder, and delete them once the file is built. Tell the user where Architecture.vsdx is (in the working folder). Say "built" only if the program did.

(The plugin folder is ${CLAUDE_PLUGIN_ROOT}: it holds scripts/, data/, base/, samples/ and docs/. If that variable is empty, it is two folders above this file.)
