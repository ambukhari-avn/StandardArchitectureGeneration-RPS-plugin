# Setting it up on another PC

## ChatGPT (custom GPT, recommended for the team)
1. Get `arch_plugin.zip` (made by `python chatgpt-plugin/make_package.py`, written to `Downloads\out`) and the client's Word document of drawing rules.
2. chatgpt.com -> Explore GPTs -> Create -> Configure.
3. Name: "Archi" (any name). Instructions: paste the whole text of `chatgpt-plugin/instructions.md`.
4. Knowledge: upload `arch_plugin.zip` and the Word document.
5. Capabilities: turn on Code Interpreter (data analysis) and Web search. Save it as "Only people with a link" or inside the workspace.
6. Test: open the GPT and send a prompt, for example "pressure transmitters and an analyzer, redundant S7-1500 PLCs, 2 SCADA workstations". ChatGPT asks its questions once, unzips the knowledge file, writes diagram.json, runs the program and returns Architecture.vsdx with the ASSUMED, PICTURES and WARNINGS lists.

Without a custom GPT: open a new chat, paste the instruction as the first message, attach the zip and the Word document, then send the prompt.
Footer values and pictures are best given in the prompt; anything missing prints TBC. ChatGPT's sandbox has Pillow (white backgrounds of web pictures are removed) but may have no internet: when a picture cannot be downloaded the item gets a generic picture or a labelled box and the report says so. ChatGPT may ask for permission before downloading pictures; say yes once.

## Claude (Claude Code or the Claude desktop app)
Needs Python 3 on the PC. Pillow is optional but recommended (`pip install pillow`, once): it removes the white background of web pictures and converts WebP/JPEG pictures to PNG. Without it the pictures are placed as they are and the build report says so.
1. Add the marketplace: `/plugin marketplace add ambukhari-avn/StandardArchitectureGeneration-RPS-plugin`
2. Install: `/plugin install architecture-diagram@rps-architecture`
3. Ask for an architecture diagram; the skill asks its questions once, asks permission before downloading pictures from the web, runs `scripts/build_diagram.py` and writes Architecture.vsdx in the working folder. Claude asks before it installs Pillow.

## Updating
Change `chatgpt-plugin/instructions.md` or the code, run the tests, run `python chatgpt-plugin/make_package.py` (it also rewrites the Claude skill), then replace the GPT's instruction and knowledge file, and push the repo for Claude users.
