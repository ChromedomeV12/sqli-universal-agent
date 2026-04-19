# run-oracle

## Description
Executes the `sqli_final.py` script to scan a specific target and update the `vulnerability_profile.json` file.

## Instructions
When the user asks for help with a specific SQLi-Labs lesson, and the information is not already present in `vulnerability_profile.json`, use this skill.

1. **Environment Reset:** Before running any scan, ensure the lab database is in a clean state by navigating to: `http://172.17.59.5/sql-connections/setup-db.php`.
2. Use the `run_shell_command` tool to execute the scanner script: `python sqli_final.py --lesson <LESSON_NUMBER> --json`. (The script also handles the reset automatically).
3. Wait for the command to complete.
4. Read the updated `vulnerability_profile.json` file to gather the required closure, parameter, and vulnerability type for the specified lesson.
5. Use this newly gathered information as your "Teacher's Key" to guide the user.