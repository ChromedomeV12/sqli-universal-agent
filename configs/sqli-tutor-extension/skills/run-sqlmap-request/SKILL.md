# run-sqlmap-request

## Description
Runs `sqlmap` using a raw HTTP request file (exported from Burp Suite). This is the most powerful way to handle authenticated or header-based injections.

## Instructions
When a standard scan fails or when dealing with complex headers/sessions:

1. **User Action:** Ask the user to:
   - "Intercept the request in Burp Proxy."
   - "Right-click -> Copy to file."
   - "Save it as `burp_request.txt` in the project root."
2. **Agent Action:** Use the `run_shell_command` tool to execute `sqlmap` using the `-r` flag.
   **Path:** `C:\Users\chrom\AppData\Roaming\Python\Python313\Scripts\sqlmap.exe`
   **Command:** `sqlmap.exe -r burp_request.txt --batch --dbs --proxy http://127.0.0.1:8080`
3. **Refinement:** If the user knows the injection point, ask them to add an asterisk (`*`) to the parameter or header in the file before saving.
4. **Agent Logic:** Parse the result and explain how `sqlmap` used the Burp request to bypass the issues encountered previously.
