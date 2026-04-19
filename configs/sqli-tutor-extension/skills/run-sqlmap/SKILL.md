# run-sqlmap

## Description
Uses `sqlmap` to automate the discovery and extraction of database information.

## Instructions
When the student is ready to automate or when you need to confirm a complex vulnerability:

1. Use the `run_shell_command` tool to execute `sqlmap`. 
   **Path:** `C:\Users\chrom\AppData\Roaming\Python\Python313\Scripts\sqlmap.exe`
2. Construct the command based on the target and the Oracle's data. 
3. **Common flags to include:**
   - `-u "http://172.17.59.5/Less-<LESSON_NUMBER>/?id=1"` (Target URL).
   - `--batch` (Always use this to prevent sqlmap from hanging on interactive prompts).
   - `--dbs` (To list databases).
   - `-D security --tables` (To list tables in a specific database).
   - `-D security -T users --dump` (To extract data).
4. **Agent Logic:** 
   - After the command finishes, you must parse the output and explain the "Magic" to the student. 
   - "sqlmap detected that this parameter is injectable via a boolean-based blind technique. Here is the database it found..."
5. **Educational Tip:** Always mention to the student that sqlmap is doing exactly what you've been practicing manually, but faster. Explain which `sqlmap` flags correspond to manual steps (e.g., `--dbs` is like a manual UNION query on `information_schema.schemata`).
