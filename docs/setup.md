# Setting it up on another PC

## ChatGPT (custom GPT, recommended for the team)
1. Get `arch_plugin.zip` (made by `python chatgpt-plugin/make_package.py`, written to `Downloads\out`) and the client's Word document of drawing rules.
2. chatgpt.com -> Explore GPTs -> Create -> Configure.
3. Name: "Archi" (any name). Instructions: paste the whole text of `chatgpt-plugin/instructions.md`.
4. Knowledge: upload `arch_plugin.zip` and the Word document.
5. Capabilities: turn on Code Interpreter (data analysis) and Web search. Save it as "Only people with a link" or inside the workspace.
6. Test: open the GPT and send a prompt, for example the 42-pumping-stations one. ChatGPT unzips the knowledge file, writes diagram.json, runs the program and returns Architecture.vsdx.

Without a custom GPT: open a new chat, paste the instruction as the first message, attach the zip and the Word document, then send the prompt.
Footer values and pictures are best given in the prompt; anything missing prints TBC.

## Claude (Claude Code or the Claude desktop app)
Needs Python 3 on the PC (Pillow optional, for WebP/JPEG pictures).
1. Add the marketplace: `/plugin marketplace add <github-user>/<repo>`
2. Install: `/plugin install architecture-diagram@rps-architecture`
3. Ask for an architecture diagram; the skill runs `scripts/build_diagram.py` and writes Architecture.vsdx in the working folder.

## Updating
Change `chatgpt-plugin/instructions.md` or the code, run the tests, run `python chatgpt-plugin/make_package.py` (it also rewrites the Claude skill), then replace the GPT's instruction and knowledge file, and push the repo for Claude users.
