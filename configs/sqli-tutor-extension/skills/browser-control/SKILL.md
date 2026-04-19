# browser-control (HackBar Simulator)

## Description
Uses Playwright CLI to open a browser, inject payloads into the target, and capture the page state for analysis. This simulates the functionality of a manual browser extension like HackBar.

## Instructions
When the student needs to "see" the result in a real browser or when a payload needs to be tested in a full DOM environment:

1. Use the `run_shell_command` tool to execute `npx.cmd playwright`.
2. **Key Commands:**
   - `npx.cmd playwright screenshot "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>" screenshot.png`: Captures a visual of the page after injection.
   - `npx.cmd playwright pdf "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>" output.pdf`: Captures the full content for detailed analysis.
   - `npx.cmd playwright open "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>"`: Opens the target page (if in a headed environment).
3. **Agent Logic:**
   - Use this skill to "show" the student the visual results of their payload.
   - "I've injected your payload into a real browser. Here's what the server returned..."
4. **HackBar Simulation:** Instead of asking the student to install HackBar, you should tell them: *"I can act as your HackBar. I'll inject the payload into the browser for you and show you the raw response."*
5. **Security:** This tool runs in the local environment and only accesses the whitelisted SQLi-Labs target IP.
