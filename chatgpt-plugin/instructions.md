
Do the user's request exactly as you normally would: ask questions, research, design, use any tools or pictures you can. This add-on restricts nothing about that. It adds what every Avanceon architecture drawing must carry, and a program that draws it, so all diagrams look the same.

**Fixed by the program (you cannot change it):** the A3 footer (Client, Project, Documentation Name, Prepared by, Checked by, Approved by, Rev, notes, scope legend, cable legend); the five cable types: ethernet (blue dashed), fibre (green dashed), modbus (red solid), bacnet (purple solid), hardwired (black solid, arrowhead at the `to` end); one sky-blue band per Purdue level that is used, with a dark-blue vertical title strip on its left; grey boxes for Avanceon scope and pink for Client/Other scope; a version stamp. **Free:** what is drawn, names, models, pictures, protocols.

**Write a v2 spec, no coordinates.** JSON that says what exists (`items`), at which level, in whose scope, and how it connects (`links`). The program places everything. Describe it following docs/diagram-format-v2.md in the attached arch_plugin.zip (samples/diagram_example_v2.json is the example), extract the zip (for example to /mnt/data) and run

    python arch_plugin/scripts/build_diagram.py /mnt/data/diagram.json --out /mnt/data/Architecture.vsdx

**Draw only what the prompt asks for.** Never add switches, a ring, a DMZ, servers, printers or anything else by default.

**Levels** (`level`): L0 instruments and actuators; L1 PLC, RTU, RIO, controllers; L2 SCADA, HMI, workstations, engineering, printer; L3 site operations; L3.5 DMZ and firewalls; L4 business; L5 enterprise. If unsure, ask.

**Scope** (`scope`): `avanceon` or `other` (client or third party) for every item. If it is not stated, or is both, ask.

**Cables.** Pick each link's medium and protocol by the relevant standard or your own engineering judgement, but never change an interface the prompt specifies. Label protocols (`"label": "Modbus RTU"`, `"OPC UA"`, `"4-20 mA"`; a modbus link needs RTU or TCP). For hardwired, `from` is the signal source and `to` the receiver. Mark every item or link you inferred, not the prompt, with `"assumed": true`; the drawing shows `*` and the build report lists it.

**Ring, only if asked:** `rings` with `first` (the Main PLC) and `members` (RIO-1 ... RIO-n): one closed fibre ellipse, order Main PLC, RIO-1 ... RIO-n, back to the Main PLC. The program adds the ring switches: 2 at the Main PLC, 2 at each RIO.
**Redundancy, only if asked:** `redundancy` with `primary` and `secondary`: drawn as Primary Controller and Secondary Controller with two links. State links of the secondary yourself.
**Switches and patch panels, only if asked:** `"kind": "switch"` or `"patch_panel"`; the approved symbol is used automatically, never a web picture. "SCADA switches" = two L2 switches, every SCADA device linked to both; "local switches" = two per control area at L1.

**Every item gets a picture; a box is a failure, not a default.** Servers, workstations and firewalls get a generic library picture automatically; instruments, analyzers, third-party PLCs and anything else need one from you: search the web, download the PNG (in a temporary folder) and set `image`. Build only when every item has a picture, or you have really tried and the web is unreachable (then say so).

**Pictures, in this order.** 1) Library: run `python arch_plugin/scripts/find_component.py "<words>"` and use the id as `component` (a library picture always wins). 2) The exact model's picture from the manufacturer's own site: `image`, `image_source` (the URL), `image_match: "exact"`. 3) A generic picture of that type, also from a manufacturer: `image_match: "generic"`. 4) Nothing found: no `image`; the item is a labelled box and the report says so. If the prompt names only a type ("pressure transmitters"), ask for the model; if the user declines, use 3). Do not draw or generate pictures; use stock or marketplace images only when no manufacturer image exists, and say so. Some tools ask permission before downloading: ask once if the user has not already allowed it. The build removes a plain white background itself (needs Pillow).

**Questions first, in one message, then build:** unknown or dual scope; the model of an L0 item; an interface that is ambiguous (what links the PLC to the third-party device?); whether the client has approved header colours (then `band_colors`, for example `{"L2": "#RRGGBB"}`). If it prints NOT BUILT with questions, ask the user those. Do not leave questions in the spec when you build.

**After the build** paste the ASSUMED, PICTURES and WARNINGS sections of the report into your reply, and say what ADDED BY RULE lists (for example the ring switches). Say "built" only if the program did. If it prints NOT BUILT, fix the JSON and run again. Keep diagram.json, helper scripts and downloaded pictures in a temporary folder, not in the user's output folder, and delete them once the file is built. Give the user only Architecture.vsdx.

**Where you run.** Claude: the plugin folder is `${CLAUDE_PLUGIN_ROOT}`; the file is written in the working folder; ask before `pip install pillow`. ChatGPT: unzip arch_plugin.zip to /mnt/data and write there; the sandbox may have no internet: if a download fails, use the generic picture or box and report it.

**Example.** Prompt: "pressure transmitters and an analyzer, redundant S7-1500 PLCs, 2 SCADA workstations", Avanceon scope throughout. After asking for the transmitter model, write:

    {"spec_version": 2, "project": {"client": "X", "project": "Y"},
     "items": [
      {"id": "pt", "label": "Pressure transmitter", "model": "Rosemount 3051", "level": "L0", "scope": "avanceon", "qty": 2,
       "image": "pt.png", "image_source": "https://www.emerson.com/...", "image_match": "exact"},
      {"id": "an", "label": "Analyzer", "level": "L0", "scope": "avanceon", "assumed": true},
      {"id": "plc1", "label": "PLC", "model": "Siemens S7-1500", "level": "L1", "scope": "avanceon", "component": "modular_plc_siemens"},
      {"id": "plc2", "label": "PLC", "model": "Siemens S7-1500", "level": "L1", "scope": "avanceon", "component": "modular_plc_siemens"},
      {"id": "ws", "label": "SCADA workstation", "level": "L2", "scope": "avanceon", "qty": 2, "component": "client_operator_workstation"}],
     "redundancy": [{"primary": "plc1", "secondary": "plc2", "links": 2, "cable": "ethernet", "assumed": true}],
     "links": [
      {"from": "pt", "to": "plc1", "cable": "hardwired", "label": "4-20 mA", "assumed": true},
      {"from": "an", "to": "plc1", "cable": "hardwired", "assumed": true},
      {"from": "plc1", "to": "ws", "cable": "ethernet", "label": "OPC UA", "assumed": true},
      {"from": "plc2", "to": "ws", "cable": "ethernet", "label": "OPC UA", "assumed": true}],
     "assumptions": ["Instruments are wired to the primary controller."]}

Result: only those items, the L2, L1 and L0 bands, Primary and Secondary Controller with two redundancy links, no switches, ring or DMZ.
