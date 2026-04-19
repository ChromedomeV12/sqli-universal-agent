# Project Summary: Universal SQLi Agent Toolkit

**Project:** Universal SQLi Agent Toolkit
**Environment:** Ubuntu WSL2 / Windows 11 · Docker (SQLi-Labs) · Target: `http://172.18.0.1/`
**Duration:** 2026-02-14 to 2026-04-19
**Result:** 30/30 detection in direct scan mode. 28/30 (93.3%) in MCP batch mode.

---

## What this project is

A multi-agent security audit framework that covers all 30 lessons of the SQLi-Labs benchmark suite, running on Ubuntu WSL2 with an AI decision layer driven through the Model Context Protocol.

The framework has five components. At the bottom, `core/sqli_final.py` scans a target at `172.18.0.1` using a class called `SQLiSolver`, detects injection types from HTTP response behavior, and writes structured results to `vulnerability_profile.json`. Above that, `core/auto_orchestrator.py` runs the scanner in batch, drives sqlmap for credential extraction, captures Playwright screenshots, and organizes output into `lab_reports/Less-XX/`. The `mcp/sqli_mcp.py` server exposes three callable tools -- `oracle_scan`, `browser_test`, and `get_lesson_guidance` -- to any AI client speaking JSON-RPC 2.0. A cross-platform configuration module, `core/config.py`, locates tools dynamically using `shutil.which()` and `sys.executable` so the codebase runs without modification on Linux, macOS, or Windows. The AI layer, running Claude Sonnet 4.6 for architecture, Qwen 3.6+ for code execution, and Kimi K2.5 for log analysis, calls into the MCP server to drive the whole thing.

---

## What the scanner actually detects

The scanner detects four injection types across five delivery methods. It uses no server-side source code. All decisions come from HTTP response behavior.

**UNION-Based (GET and POST):** The scanner tries `ORDER BY N` incrementally until the column count causes a page break, then sends a UNION with hex-encoded marker values (`gemini_marker`) in each column position. If a marker appears in the response body, that column reflects data. The extraction payload then puts `GROUP_CONCAT(username,0x7e,password) FROM users` into the reflecting column. Lessons 1-4, 11, 12, 23, 25, 29, 30.

**Error-Based:** The scanner injects `updatexml(1,concat(0x7e,SUBQUERY,0x7e),1)` and checks the response for `XPATH syntax error: '~DATA~'`. The `0x7e` character (tilde) delimits the extracted data from surrounding noise. The regex in `check_error_response()` pulls out the content between the tildes. Lessons 5, 6, 17, 18, 19, 20.

**Boolean-Blind:** The scanner sends one payload that should evaluate as TRUE and one that should evaluate as FALSE. If the response length difference exceeds 20 bytes, an injection point exists. Lessons 9, 10, 28.

**Time-Blind:** The scanner measures HTTP response time with `SLEEP(3)` in the payload. If elapsed time is 3 seconds or more, the injection worked. Lessons 7, 8.

For Cookie injection (Lessons 20-22), the scanner first tries the payload in plaintext. If that fails and the injection point is a cookie, it automatically retries with the payload base64-encoded. This covers Lessons 21 and 22 without hardcoding lesson numbers:

```python
candidates = [('none', raw_p)]
if header == 'Cookie':
    candidates.append(('base64_cookie', base64.b64encode(raw_p.encode()).decode()))
```

Second-order injection (Lesson 24) requires two separate HTTP sessions: register a username containing `admin'#`, log in as that user, attempt a password change, then verify that the admin account's password changed. The scanner handles this in `scan_second_order_generic()`.

---

## WAF bypass strategies

Lessons 25-28 use PHP `preg_replace` to strip SQL keywords and whitespace. The scanner has six tamper modes in `apply_tamper()` to handle filter variations:

`space_bypass` replaces spaces with `%0a` (URL-encoded newline). MySQL accepts newlines as whitespace. Most simple space filters do not block `%0a`.

`keyword_replace` double-writes keywords: `UNION` becomes `ununionion`. If the filter performs a single non-recursive replacement, removing the inner `UNION` leaves the outer letters to collapse into a new `UNION`.

`inline_comment` wraps keywords in MySQL inline comment syntax: `/*!UNION*/`. MySQL executes this. Many filters classify it as a comment and skip it.

`waf_bypass` combines newline-as-whitespace with URL-encoded logical operators: `AND` becomes `%26%26`, `OR` becomes `%7C%7C`, spaces become `%0a`.

`waf_bypass_newline` uses the same substitutions but replaces comment terminators (`-- -`) with logical true balancing (`'1'='1`), targeting WAFs that strip both `--` and `#`. This mode had a bug for the entire early development period: the `elif` branch was missing from `apply_tamper()`, so the function returned the payload unchanged without any terminator. All tests using that mode silently failed. The fix added the branch with the correct logic:

```python
elif mode == 'waf_bypass_newline':
    p = p.replace(" ", "%0a").replace("AND", "anandd").replace("OR", "oorr") \
         .replace("UNION", "ununionion").replace("SELECT", "selselectect")
    p += "%0a'1'='1" if closure == "'" else \
         ("%0a\"1\"=\"1\"" if closure == '"' else "%0a1=1")
```

`base64_cookie` encodes the entire payload with base64 and returns immediately without appending a comment terminator. The comment would get base64-encoded too, making it part of the decoded SQL rather than a trailing comment character.

---

## The MCP interface

The three MCP tools use JSON-RPC 2.0. A call to `oracle_scan` looks like this on the wire:

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

The server spawns `sqli_final.py --lesson 1 --json --no-reset` as a subprocess, reads `vulnerability_profile.json` after it finishes, extracts the Lesson 1 entry, and returns it. The AI model receives:

```json
{
  "type": "UNION-Based",
  "method": "GET",
  "parameter": "id",
  "closure": "'",
  "tamper": "none",
  "extra": "Cols:3"
}
```

All error paths return structured JSON rather than Python exceptions:

```python
except subprocess.TimeoutExpired:
    return json.dumps({"error": f"Oracle scan for lesson {lesson_number} timed out after 120s."})
except Exception as e:
    return json.dumps({"error": str(e)})
```

The `browser_test` tool uses the Playwright Python API directly. The original implementation called the Playwright CLI through `subprocess` and returned a screenshot file path. An AI model cannot determine injection success from a file path. The replacement navigates to the target URL using a headless Chromium instance, intercepts the HTTP response to capture the status code, extracts the page body text with `page.inner_text("body")`, checks for SQL error strings, and returns a structured summary:

```json
{
  "status_code": 200,
  "page_title": "Less-1 **Error Based- String**",
  "body_snippet": "Your Login name:security\nYour Password:3",
  "detected_errors": [],
  "screenshot": "/home/chrom/sqli-universal-agent/lab_reports/Less-01/visuals/mcp_test.png"
}
```

The `body_snippet` field contains the rendered page text. The string `security` in that field is the MySQL `database()` return value. The AI can read that and confirm the injection worked without analyzing an image.

The `get_lesson_guidance` tool loads `sqli_tutor.py` at runtime using `importlib.util` and captures the output of `provide_guidance()` into a string buffer using `redirect_stdout`. This makes the Socratic teaching logic accessible through the MCP interface without requiring any direct import of the tutor module at server startup.

---

## Failures that shaped the final design

**Profile overwrite race condition.** `auto_orchestrator.py` called `sqli_final.py` separately for each lesson. Each call wrote `json.dump(all_scan_results, f, indent=4)` with mode `"w"`. After 30 calls, the file contained only Lesson 30. The succession report showed 29 failures. Fixing this required changing the write logic to read-merge-write on every call.

**502 proxy loop.** Before any scan ran, every HTTP request returned 502. A system-wide proxy at `127.0.0.1:7897` was intercepting requests to the internal Docker subnet. The fix was `trust_env = False` on the requests session and `proxies={"http": None, "https": None}` on all direct calls.

**MCP cascade timeout.** Running 20 concurrent `oracle_scan()` calls crashed the MCP server. HEADER injection lessons require authentication before payload delivery, which adds 15-25 seconds per lesson. Twenty concurrent 30-second scans exceeded the 120-second timeout budget. The server crashed and locked out all tool calls for the remainder of the session. The operational limit is now 10 concurrent scans per batch.

**Source corruption artifact.** An AI editing tool converted `\n` escape sequences to the literal characters `` `n `` when writing multi-line content to `sqli_final.py`. This produced an `invalid syntax` error at the `for` loop lines affected. The artifact recurred four times. The response was a mandatory AST syntax check after every file edit: `python3 -c "import ast; ast.parse(open(f).read()); print('OK')"`.

**Session loss for header injection.** Lessons 18-22 require an authenticated session. Each independent call to `sqli_final.py` started with an empty session. The fix serializes session cookies to `session_cache.json` after login and restores them at startup.

---

## What does not work yet

**Lessons 17, 26, 27, 28 at 93.3% accuracy.** The `solve()` method uses short-circuit return: the first detected injection type terminates the scan. For lessons where multiple injection types coexist, the wrong type may win. Lesson 26 detects both Error-Based and Boolean-Blind. If Boolean-Blind is detected first, `flush_data()` returns a confidence-check payload rather than a credential extraction payload. Detection succeeds; the lesson is counted as failed because no credentials are extracted.

Fixing this requires rewriting `solve()` to collect all detected injection types and select the highest-priority extraction path (UNION preferred over Error-Based, Error-Based over Boolean-Blind, Boolean-Blind over Time-Blind) rather than stopping at the first hit.

**Time-Blind extraction.** Lessons 7-9 detect the injection successfully through `SLEEP(3)` timing. The `get_extraction_payload()` function returns only an existence check, not a character-level extraction payload. Pulling actual credential data from a Time-Blind injection requires a binary search over ASCII values using `ascii(substring(SUBQUERY,N,1))` with conditional `SLEEP()` calls. Each character takes roughly 7 HTTP requests. A 12-character password at 3-second delays takes about 4 minutes per credential. This is not implemented.

**MCP server-side queue.** The current concurrency mitigation relies on the operator knowing the 10-scan limit. Moving the rate limiting into the MCP server itself, using a request queue that serializes header injection requests, would remove the constraint from the operator's responsibility.

---

## Validation results

Single scan run from `injection_script_convo.json` line 667: Total Successful Injections: 30/30.

| Type | Lessons | Confirmed |
|------|---------|-----------|
| GET UNION | 1, 2, 3, 4, 23, 25, 29, 30 | 8/8 |
| GET Error-Based | 5, 6 | 2/2 |
| GET Time-Blind | 7, 8 | 2/2 |
| GET Boolean-Blind | 9, 10, 28 | 3/3 |
| POST UNION | 11, 12 | 2/2 |
| POST Login-Bypass | 13, 14, 15, 16 | 4/4 |
| POST Error-Based | 17 | 1/1 |
| Header/User-Agent | 18, 19 | 2/2 |
| Cookie Plain | 20 | 1/1 |
| Cookie Base64 | 21, 22 | 2/2 |
| Comment-Strip WAF | 23 | 1/1 |
| Second-Order | 24 | 1/1 |
| Keyword WAF | 25, 27 | 2/2 |
| Space WAF | 26 | 1/1 |
| HPP | 29 | 1/1 |
| Double-quote UNION | 30 | 1/1 |

Extracted data from `scan_results.txt`:

```
[+] Less-18: User-Agent Injection Successful. DB: Dumb:Dumb,Angelina:I-kill-you,...
[+] Less-21: Cookie Injection (B64) Successful. DB: Dumb:Dumb,Angelina:I-kill-you,...
[+] Less-24: Second Order Injection Successful (User: admin'#).
```
