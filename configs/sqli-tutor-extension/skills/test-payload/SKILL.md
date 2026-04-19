# test-payload

## Description
Executes a user's proposed SQL injection payload against a local target URL using `curl`, returning the HTTP response for analysis.

## Instructions
When the user proposes a payload (e.g., `id=1'`), you must verify it before providing feedback.

1. Construct the target URL. For SQLi-Labs, it typically follows this pattern: `http://172.17.59.5/Less-<LESSON_NUMBER>/?<PARAMETER>=<PAYLOAD>`.
2. **Burp Interception Mode:** If the user wants to see the traffic in Burp Suite, route it through the Burp proxy.
   **Command:** `curl.exe -s -i --proxy http://127.0.0.1:8080 "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<USER_PAYLOAD>"`
3. **Direct Sandbox Mode:** To hit the lab directly while avoiding the system proxy at 7897, use the `--noproxy` flag.
   **Command:** `curl.exe -s -i --noproxy "*" "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=<USER_PAYLOAD>"`
4. Analyze the output of the curl command. Look for:
   - Changes in content length compared to a baseline.
   - Database error messages.
   - Specific markers indicating success.
5. Provide feedback to the user based on the real, observed behavior of their payload.