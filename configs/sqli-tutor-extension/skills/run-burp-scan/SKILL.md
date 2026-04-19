# run-burp-scan

## Description
Initiates an automated active scan on a target URL using the Burp Suite Professional REST API. Supports both unauthenticated and authenticated audits.

## Instructions
When the user wants to run a professional audit on a specific lesson:

1. **API Key Retrieval:** Check `sqli-tutor-extension/.burp_key`.
2. **Authenticated Workflow (Required for Lessons 11-22, 24):**
   - If the lesson requires a login, perform the login first using `curl` or `browser-control`.
   - Capture the session cookie (e.g., `PHPSESSID=...`).
3. **Trigger Scan:** Use the `run_shell_command` tool.
   **Command (Unauthenticated):**
   `curl.exe -s -k -X POST "http://127.0.0.1:1337/<API_KEY>/v0.1/scan" -d "{\"urls\":[\"http://172.17.59.5/Less-<LESSON_NUMBER>/\"], \"scan_configurations\": [{\"name\": \"Minimize false positives\", \"type\": \"named_configuration\"}]}" -H "Content-Type: application/json"`
4. **Agent Logic:** If issues are not found in an unauthenticated scan, advise the user that you can perform an "Authenticated Scan" by logging in first and passing the session state.