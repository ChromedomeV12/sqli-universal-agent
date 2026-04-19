# Project Work Log: Universal SQLi Agent Toolkit

**Period:** 2026-02-14 to 2026-04-19
**Final state:** Lessons 1-30 covered, WSL2 environment stable, MCP server production-ready
**Best single-run result:** 30/30. Sustained batch-mode result: 28/30 (93.3%)

---

## How to read this log

This is a chronological record of what broke, why it broke, and what was done about it. The failures come first because that is what actually took time. The successes were often short. The failures lasted days.

---

## Phase 1: First contact -- February 14 to March 10, 2026

### Log 01 -- The first hour: 502 before any code ran

I had not written a single line of scanner code. I ran `curl.exe http://172.17.59.5/` to confirm the Docker target was reachable.

```
HTTP/1.1 502 Bad Gateway
Connection: keep-alive
Keep-Alive: timeout=4
Content-Length: 0
Process Group PGID: 16780
```

My first guess was that the container was down. Ping said otherwise. I added `-v` to the curl command and read the output carefully. Line three:

```
* Uses proxy env variable http_proxy == 'http://127.0.0.1:7897'
```

A VPN client on the Windows host had written a global HTTP proxy to the environment. Every outbound HTTP request, including requests to `172.17.59.5` which is an internal Docker bridge address, was being forwarded to `127.0.0.1:7897`. That proxy had no idea what to do with a private subnet IP. It returned 502.

Fix: `self.session.trust_env = False` in `sqli_final.py`, and explicit `proxies={"http": None, "https": None}` on every direct HTTP call. The `setup.sh` script also writes `NO_PROXY=172.18.0.1` to `.bashrc` so the environment is clean from startup.

Without this, no scan ever reaches the target. Everything built on top of the scanner would be worthless.

### Log 02 -- The methodological decision: no source code

I could open the PHP files in SQLi-Labs and read exactly what each lesson does. I chose not to.

The reason is that real-world external testing does not come with source access. If the tool only works when you already know the answer, it has limited practical value. The constraint I wrote into the project spec was: all vulnerability detection must come from observable HTTP response behavior only.

This decision shaped every detection method in `scan_get()`, `scan_post()`, and `scan_headers()`. Response length deltas for Boolean-Blind. `SLEEP()` timing for Time-Blind. XPath error strings for Error-Based. Reflected hex markers for UNION. None of these require reading PHP.

### Log 03 -- Oracle v1.0: timing everything

The first scanner version tested all closures with a `SLEEP(3)` payload and measured response time. It worked for Time-Blind lessons. It also produced false positives on Error-Based lessons because a malformed query sometimes adds a few hundred milliseconds of processing delay. The 3-second threshold caught real sleeps but also occasionally triggered on noise.

The v2 scan order fixed this: UNION detection runs before Error-Based, which runs before Boolean-Blind, which runs before Time-Blind. Each method has a definitive success condition. UNION checks for a hex marker in the response body. Error-Based checks for XPath error syntax. Only Time-Blind falls back to timing. The false positive rate dropped to zero.

---

## Phase 2: Architecture takes shape -- March 10 to April 10, 2026

### Log 04 -- The JSON interface: giving the AI something it can read

The scanner printed results to a log file. An AI model reading that log had to parse unstructured text to extract closure type, injection method, column count, and tamper mode. That is error-prone.

Adding `--json` and a `record_vuln()` function produced structured output instead:

```python
def record_vuln(self, vuln_type, method, parameter, closure, tamper="none", extra=None):
    self.found_vulnerability = {
        "type": vuln_type,
        "method": method,
        "parameter": parameter,
        "closure": closure,
        "tamper": tamper
    }
    if extra:
        self.found_vulnerability["extra"] = extra
    all_scan_results[str(self.lesson_num)] = self.found_vulnerability
```

From that point, `vulnerability_profile.json` served as the single ground truth for both the AI teaching layer and the automated orchestration layer. The same file answers "what is the closure for Lesson 3?" whether you are a student being guided through the exercise or the orchestrator dispatching a sqlmap command.

### Log 05 -- First full scan: 18 of 30

The first complete run finished and printed 18 successes. Lessons 17-19 failed. Lessons 25-28 failed. The log at `ai_tool_dev_convo.json` line 5940 recorded:

```
[-] Less-17 Failed.
[-] Less-18 Failed.
[-] Less-19 Failed.
[-] Less-26 Failed.
[-] Less-27 Failed.
[-] Less-28 Failed.
```

Lesson 17 fails because the password parameter, not the username parameter, is the injection point, and the scan order tested username first. Lessons 18-19 fail because they inject into HTTP headers, and the generic `scan_headers()` function did not yet know the specific `INSERT` statement format those lessons use. Lessons 25-28 fail because keyword and space filtering blocks every standard tamper strategy that existed at the time.

These six failures became the work queue for the next six weeks.

### Log 06 -- Sentinel extraction and the 0x7e character

Getting an injection to succeed is one thing. Getting it to extract the right data reliably is another. The early extraction payloads used `concat(database(),0x3a,user())` which produced output like `security:root@localhost`. That format is not hard to parse, but it varies by lesson type.

Switching to `updatexml()` with `0x7e` (tilde character) as a delimiter produced consistent, parseable output regardless of injection type:

```python
payload_db = "updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1)"
```

The response contains something like `XPATH syntax error: '~Dumb~0,Angelina~I-kill-you,...~'`. The regex extracts everything between the outer tildes. The extraction code in `check_error_response()` strips the tilde and returns the raw credential string. This worked across all error-based lessons including the header and cookie injection variants.

### Log 07 -- The orchestrator: running without watching

Once single-lesson scans worked reliably, running them one at a time was tedious. `auto_orchestrator.py` automated the full pipeline for each lesson: database reset, Oracle scan, Playwright screenshot, sqlmap flush, file archival.

The first version of this file contained:

```python
SQLMAP_PATH = r"C:\Users\chrom\AppData\Roaming\Python\Python313\Scripts\sqlmap.exe"
BASE_URL    = "http://172.17.59.5/"
```

Both lines worked for two months. Both lines broke on the first day of WSL2 testing.

---

## Phase 3: The WSL2 migration -- April 18, 2026

### Log 08 -- Everything that assumed Windows

Moving to Ubuntu WSL2 revealed six categories of Windows assumptions buried in the codebase:

| Broken thing | Windows form | Linux replacement |
|--------------|-------------|-------------------|
| sqlmap path | `r"C:\Users\...\sqlmap.exe"` | `shutil.which("sqlmap")` |
| Python interpreter | `"python"` | `sys.executable` |
| Playwright call | `"npx.cmd playwright"` | `["npx", "playwright", ...]` |
| Proxy env var name | `WIN_HOST_IP` | `PROXY_HOST_IP` |
| Target IP | `172.17.59.5` | `172.18.0.1` |
| Subprocess execution | `shell=True` + string | list args, no `shell=True` |

The `shell=True` issue was the most dangerous because it produced no immediate error. On Windows, `shell=True` passes the command string to `cmd.exe`. On Linux, it passes to `bash`. Their quote-handling rules differ. A command like `npx.cmd playwright screenshot "http://172.18.0.1/Less-4/?id=1\" ) ORDER BY 1--+" output.png` would parse correctly on cmd.exe and produce a completely different argument split on bash. The Playwright call would fail with a cryptic "unknown option" error pointing at a SQL keyword in the URL. This took an afternoon to trace.

Replacement in every case:

```python
# Before
subprocess.run(f'npx.cmd playwright screenshot "{test_url}" {viz_path}', shell=True)

# After
subprocess.run(["npx", "playwright", "screenshot", test_url, viz_path], capture_output=True)
```

List-based subprocess calls pass each argument as a separate element. No shell interprets quotes. SQL characters in URLs pass through unmodified.

### Log 09 -- config.py: one place for everything

After fixing the Windows paths one by one across three files, I created `core/config.py` as a single source for all runtime configuration:

```python
PLATFORM    = platform.system().lower()
TARGET_IP   = os.environ.get("TARGET_IP", "172.18.0.1")
SQLMAP_BIN  = shutil.which("sqlmap") or "sqlmap"
PYTHON_BIN  = sys.executable
BASE_URL    = f"http://{TARGET_IP}/"
```

Import this module and you get the correct binary paths for the current OS. No hardcoded strings anywhere. The startup banner printed when you import it:

```
[config] Platform: linux | Target: 172.18.0.1 | sqlmap: /usr/local/bin/sqlmap
```

That single line confirms four things at once: the OS was detected, the target IP is set, sqlmap was found at a real path, and the module imported without errors.

### Log 10 -- The backtick-n artifact

After the WSL2 migration, the AST check on `sqli_final.py` returned:

```
File "<unknown>", line 303
    for c in closures: `n                print(f"[*] Testing POST closure: {c}...") `n ...
                       ^
SyntaxError: invalid syntax
```

The characters `` `n `` are not Python syntax. An AI editing tool had written multi-line string content into the file and rendered the `\n` escape sequence as the literal two-character sequence backtick-n. Two `print()` statements got collapsed onto the same line as the `for` header. The Python parser rejected it.

This happened four times total. Every time: fix it, run the AST check, confirm clean, move on. Three edits later: broken again. The same tool produced the same artifact when modifying adjacent code.

The permanent response was to add the AST check as a mandatory step after any file edit, and to add it explicitly to the project documentation. It runs in under 0.1 seconds:

```bash
python3 -c "import ast; ast.parse(open('core/sqli_final.py').read()); print('OK')"
```

---

## Phase 4: MCP architecture -- April 18-19, 2026

### Log 11 -- From Gemini CLI extension to universal MCP server

The project started as a Gemini CLI extension using platform-specific `SKILL.md` instruction files. Those files only worked inside the Gemini CLI environment. No other AI tool could use them.

Moving to MCP replaced the skill files with three Python functions decorated with `@mcp.tool()`:

```python
@mcp.tool()
def oracle_scan(lesson_number: int) -> str:
    """Runs the discovery scanner on the target lesson and returns the vulnerability profile."""
    ...

@mcp.tool()
def browser_test(url: str, payload: str, lesson_id: int) -> str:
    """Uses Playwright Python API to inject a payload and return a surgical DOM summary."""
    ...

@mcp.tool()
def get_lesson_guidance(lesson_number: int) -> str:
    """Returns Socratic teaching guidance for a lesson using the tutor's analysis logic."""
    ...
```

These functions are callable by any MCP-compatible client over JSON-RPC 2.0. The toolkit is no longer tied to one AI platform.

### Log 12 -- The concurrent scan cascade

To validate the WSL2 setup quickly, I fired 20 `oracle_scan()` calls in parallel -- one per lesson, lessons 1 through 20.

Lessons 1 through 17 returned correctly. Starting at Lesson 18:

```
MCP error -32001: Request timed out
MCP error -32000: Connection closed
```

The server process had crashed. Every subsequent tool call in that session failed. Restarting the OpenCode session restored functionality after about five minutes.

The cause: HEADER injection lessons (18-22) require establishing an authenticated session before sending any payload. That authentication step adds 15-25 seconds per lesson. With 20 concurrent scans running, the total time budget exceeded the 120-second MCP timeout. The FastMCP process received a timeout signal, crashed, and left all pending requests in a broken state.

Fix: 10 concurrent scans maximum per batch, with a 5-second cooldown between batches. Header and Cookie lessons run sequentially. The `--batch-size` argument in `auto_orchestrator.py` enforces the limit.

### Log 13 -- The profile overwrite bug

Running `auto_orchestrator.py --range 1-30` finished with a succession report showing only Lesson 30 as PASSED. All other lessons showed FAILED.

Each scan wrote to `vulnerability_profile.json` using:

```python
with open(JSON_FILE, "w") as f:
    json.dump(all_scan_results, f, indent=4)
```

`all_scan_results` only contains data from the current subprocess call -- one lesson. The `"w"` mode overwrites the entire file. After 30 sequential calls, the file contained only the Lesson 30 entry. The succession report read the file, found no data for lessons 1-29, and reported them all as failures.

The fix reads the file before writing, merges new results in, and writes back:

```python
existing = {}
if os.path.exists(JSON_FILE):
    with open(JSON_FILE, "r") as f:
        existing = json.load(f)
existing.update(all_scan_results)
with open(JSON_FILE, "w") as f:
    json.dump(existing, f, indent=4)
```

After this fix, running `--range 1-30` produces a profile with all 30 lessons intact.

### Log 14 -- Session caching for header injection

Lessons 18-22 inject into HTTP headers or cookies. They all require an authenticated session: you must log in first, get a session cookie, and then send the injection in a subsequent request carrying that cookie.

Each call to `sqli_final.py` creates a fresh `requests.Session()` with no cookies. Without session persistence, every header injection lesson starts unauthenticated and fails immediately.

The fix serializes session cookies to disk after login:

```python
def save_session(self):
    with open(self.cache_file, "w") as f:
        json.dump(requests.utils.dict_from_cookiejar(self.session.cookies), f)

def load_session(self):
    if os.path.exists(self.cache_file):
        with open(self.cache_file, "r") as f:
            cookies = json.load(f)
            self.session.cookies.update(requests.utils.cookiejar_from_dict(cookies))
```

`detect_and_login()` calls `save_session()` after a successful login. The next `sqli_final.py` invocation calls `load_session()` at startup. The authenticated cookie carries over.

After this change, Lessons 18 and 19 produced their first successful outputs:

```
[+] Less-18: User-Agent Injection Successful. DB: Dumb:Dumb,Angelina:I-kill-you,...
[+] Less-19: Referer Injection Successful. DB: Dumb:Dumb,Angelina:I-kill-you,...
```

### Log 15 -- Base64 generalization

Lessons 21 and 22 base64-encode the cookie value before sending. Lesson 21 uses `')` as its closure. Lesson 22 uses `"`. The original implementation handled this with hardcoded branches:

```python
elif self.lesson_num == 21:
    payload_raw = f"admin') and {payload_db} #"
    payload_b64 = base64.b64encode(payload_raw.encode()).decode()
```

This approach breaks if any other lesson uses a similar encoding scheme. The fix adds a `base64_cookie` tamper mode and updates `scan_headers()` to try it as a fallback after plain injection fails:

```python
candidates = [('none', raw_p)]
if header == 'Cookie':
    candidates.append(('base64_cookie', base64.b64encode(raw_p.encode()).decode()))

for tamper_mode, p in candidates:
    req_cookies[target_name] = p
    r = self.session.post(...)
    if self.check_error_response(r.text):
        self.record_vuln("Error-Based", "COOKIE", target_name, c, tamper=tamper_mode,
                         extra="Base64" if tamper_mode == 'base64_cookie' else None)
        return True
```

The scanner tries plain cookie injection first. If that fails, it tries base64-encoded injection. It no longer needs to know the lesson number to decide which encoding to use.

---

## Phase 5: DOM upgrade and Socratic bridge -- April 19, 2026

### Log 16 -- browser_test: from file path to JSON

The old `browser_test()` returned `"Screenshot saved to /path/to/file.png"`. An AI cannot determine injection success from a file path. It cannot read the PNG.

The new version uses the Playwright Python API directly and returns a DOM summary:

```json
{
  "status_code": 200,
  "page_title": "Less-1 **Error Based- String**",
  "body_snippet": "Welcome    Dhakkan\nYour Login name:security\nYour Password:3",
  "detected_errors": [],
  "screenshot": "/home/chrom/.../mcp_test.png"
}
```

The `body_snippet` field contains the rendered page text. For a successful UNION injection against Lesson 1 with `id=-1' UNION SELECT 1,database(),3--+`, the snippet shows `Your Login name:security`. The AI reads `security` and confirms the injection worked. The database name matches the expected `security` schema. No image analysis required.

### Log 17 -- get_lesson_guidance: the tutor enters MCP

`sqli_tutor.py` ran as an interactive CLI loop with `input()` prompts. No MCP client could call it programmatically. The teaching logic was inaccessible from the protocol layer.

The fix uses `importlib.util` to load `sqli_tutor.py` at runtime and `redirect_stdout` to capture `provide_guidance()` output as a string:

```python
spec = importlib.util.spec_from_file_location("sqli_tutor", CORE_DIR / "sqli_tutor.py")
tutor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tutor)

buf = io.StringIO()
with redirect_stdout(buf):
    tutor.provide_guidance(str(lesson_number), result_str, payload_str)

return json.dumps({
    "lesson": lesson_number,
    "vulnerability": result_str,
    "guidance": buf.getvalue()
}, indent=2)
```

Any MCP client can now call `get_lesson_guidance(21)` and receive the full structured analysis: vulnerability type, closure explanation, filter bypass description, and step-by-step guidance -- without reading a line of `sqli_tutor.py`.

---

## Summary table

| Issue | First seen | Status | Remaining risk |
|-------|-----------|--------|---------------|
| 502 proxy loop | 2026-02-14 | Fixed | None |
| Windows hardcoded paths | 2026-04-18 | Fixed | None |
| `shell=True` cross-platform | 2026-04-18 | Fixed | None |
| `` `n `` source corruption | 2026-04-18 | Fixed (recurs) | AST check required after each edit |
| Profile overwrite race | 2026-04-18 | Fixed | None |
| MCP cascade timeout | 2026-04-18 | Mitigated (batch <= 10) | Documented limit |
| `waf_bypass_newline` silent bug | 2026-04-19 | Fixed | None |
| Header session loss | 2026-04-18 | Fixed | None |
| Base64 cookie hardcoding | 2026-04-19 | Generalized | None |
| Lessons 17/26-28 exit logic | 2026-04-19 | Located, not yet fixed | Needs `solve()` priority refactor |
