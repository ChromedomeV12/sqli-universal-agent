# get-burp-issues

## Description
Retrieves the status and vulnerabilities found by a specific Burp Suite scan task.

## Instructions
After initiating a scan using `run-burp-scan` and receiving a `task_id`, use this skill to check the results.

1. **API Key Retrieval:**
   - First, check if the file `sqli-tutor-extension/.burp_key` exists.
   - If it exists, read the key from that file.
   - If it does not exist, ask the user to provide their Burp REST API Key.
2. Use the `run_shell_command` tool to execute `curl`.
3. Construct the command to fetch the scan status and issues:
   `curl.exe -s -k -X GET "http://127.0.0.1:1337/<API_KEY>/v0.1/scan/<TASK_ID>"`
4. Parse the JSON response. Look for the `scan_status` and the `issue_events` array.
5. If issues are found, specifically look for SQL Injection vulnerabilities. Summarize these findings for the user and correlate them with the "Oracle's" known vulnerability profile for that lesson.