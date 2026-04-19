# open-in-firefox

## Description
Launches the local Firefox browser at a specific target URL. This allows the user to use their installed extensions (like HackBar V2) for manual exploitation.

## Instructions
When the student wants to switch from your automated guidance to their own manual tools:

1. Use the `run_shell_command` tool to execute Firefox.
   **Path:** `C:\Program Files\Mozilla Firefox\firefox.exe`
2. Construct the command: `& "C:\Program Files\Mozilla Firefox\firefox.exe" "http://172.17.59.5/Less-<LESSON_NUMBER>/"`
3. **Agent Logic:**
   - "I've launched Firefox for you. Since you have **HackBar V2** installed, you can use it to craft the payloads we've been discussing."
   - Provide the specific payload string for the user to copy-paste into HackBar.
4. **Coordination:** Use this skill after you've provided a Socratic hint, as a way to "set the stage" for the user's manual work.
