# browser-control (HackBar Simulator)

## Description
Uses Playwright CLI to open a browser, inject payloads into the target, and capture the page state for analysis. This simulates the functionality of a manual browser extension like HackBar.

## Runtime preparation
Run from the repository root with the Python environment containing `requirements.txt` activated. Select patched host Node (see the root README), then configure Playwright's supported Node override in the same launch terminal. An unsafe or missing Node fails validation.

Bash / WSL:

```bash
export PLAYWRIGHT_NODEJS_PATH="$(python -c 'from core.node_runtime import configure_playwright_node; print(configure_playwright_node())')"
if [ -z "$PLAYWRIGHT_NODEJS_PATH" ]; then exit 1; fi
python -m playwright --version
```

PowerShell:

```powershell
$nodePath = python -c "from core.node_runtime import configure_playwright_node; print(configure_playwright_node())"
if ($LASTEXITCODE -ne 0) { throw "Patched Node verification failed." }
$env:PLAYWRIGHT_NODEJS_PATH = $nodePath
python -m playwright --version
```

Use the Python CLI from that prepared session. Do not fall back to npx or the wheel's bundled Node if validation fails.

## Instructions
When the student needs to "see" the result in a real browser or when a payload needs to be tested in a full DOM environment:

1. Use the `run_shell_command` tool to execute `python -m playwright`.
2. **Key Commands:**
   - `python -m playwright screenshot "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>" screenshot.png`: Captures a visual of the page after injection.
   - `python -m playwright pdf "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>" output.pdf`: Captures the full content for detailed analysis.
   - `python -m playwright open "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<PAYLOAD>"`: Opens the target page (if in a headed environment).
3. **Agent Logic:**
   - Use this skill to "show" the student the visual results of their payload.
   - "I've injected your payload into a real browser. Here's what the server returned..."
4. **HackBar Simulation:** Instead of asking the student to install HackBar, you should tell them: *"I can act as your HackBar. I'll inject the payload into the browser for you and show you the raw response."*
5. **Security:** This tool runs in the local environment and only accesses the whitelisted SQLi-Labs target IP.
