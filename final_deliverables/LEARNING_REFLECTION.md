# Learning Reflection: What 65 Days of Broken Scans Actually Taught Me

**Author:** Maozheng Chen
**Date:** 2026-04-19
**Duration:** February to April 2026, roughly 65 working days

---

The number I remember is not 30 out of 30. It is 18.

When the scanner ran all 30 lessons for the first time, it got 18. Twelve lessons failed. Some of the failures were obvious after five minutes of reading the logs. Others took days. At the time, 18 felt like a problem. Looking back, the 12 failures were where most of the actual learning happened.

---

## What I thought I was building vs. what I was actually building

The project description said: build an AI-assisted SQLi scanner that covers all 30 SQLi-Labs lessons. That is what I thought I was doing.

What I was actually building was a distributed system -- scanner subprocess, MCP server process, AI model, file-based shared state, browser automation, and an orchestrator that tied it together. Each of those components had its own failure modes. Most of those failure modes were invisible until they collided with each other.

The `vulnerability_profile.json` overwrite issue is a clean example. The scanner itself worked perfectly. Write one lesson's data to a JSON file -- that's a single Python function, two lines. It worked every time I tested it manually. What I had not tested was 30 sequential calls from the orchestrator, where each call's `json.dump(all_scan_results, f, indent=4)` with mode `"w"` erased everything from the previous call. The scanner worked. The system did not. Those are different problems.

I suspect this distinction -- between a component working and a system working -- is where a lot of people get stuck when they move from writing scripts to writing tools that other tools depend on.

---

## The proxy incident was not about networking

The first real obstacle was the 502 Bad Gateway error. My instinct was to check if the Docker container was running. It was. Then I checked if the web server inside it was responding. It was. The `curl` request still returned 502.

Running `curl -v` showed the actual path the request took:

```
* Uses proxy env variable http_proxy == 'http://127.0.0.1:7897'
```

A VPN client on my Windows host had set a system-wide HTTP proxy. Every network request, including requests to the internal Docker subnet at `172.17.59.5`, routed through it. The proxy did not know what to do with a private subnet address. It returned 502.

The technical fix was two lines: `trust_env = False` and explicit `proxies={"http": None, "https": None}`. That is not the interesting part.

The interesting part is that I spent about 30 minutes assuming the problem was in my code before I ran the verbose flag. The environment was wrong, not the code. You can review `scan_get()` ten times and never find the bug if the bug is in the network stack below your code.

After that day, I started treating the environment as a variable rather than a constant. Before debugging any failure, check what the actual HTTP request looks like at the wire level. Check what process is actually being called. Check whether the file you think exists actually exists. Do not assume the environment matches your mental model of it.

---

## The backtick-n corruption: how the same bug can be unfixable

There is a syntax error that appeared in `sqli_final.py` four separate times over the course of the project. It looked like this:

```python
for c in closures: `n                print(f"[*] Testing POST closure: {c}...") `n ...
```

The characters `` `n `` are not Python. They do not mean anything in Python. An AI editing tool was converting newline escape sequences (`\n`) in multi-line string arguments into the literal two-character sequence backtick-n, and collapsing the result onto one line. The Python parser rejected it with `SyntaxError: invalid syntax`.

I fixed it the first time. Fixed it the second time. Fixed it the third time. The fourth time I was certain I had understood the root cause and it would not happen again. It happened again.

The correct response, it turns out, is not to find the "right" way to fix it permanently. It is to accept that some tools introduce errors systematically and build a detection step that runs faster than the errors accumulate. An AST syntax check on the file takes under 0.1 seconds:

```python
python3 -c "import ast; ast.parse(open('core/sqli_final.py').read()); print('OK')"
```

I run this now after any edit to any of the five core files. If it fails, I know immediately. If it passes, I know the file is at least syntactically valid. The tool is still broken in the same way. The mitigation is just faster than the problem.

There is probably a broader lesson here about systems that include AI-generated code. The AI is not malicious. It is not failing. It is just systematically wrong in a specific narrow pattern. You cannot fix the AI. You can add a check that catches what it gets wrong.

---

## Moving from single-process thinking to shared-state thinking

The merge-write race condition was the most instructive failure, partly because I understand exactly why I did not anticipate it.

When you write a function, you think about inputs and outputs. The function takes a lesson number, scans it, writes the result to a file, done. That reasoning is correct when you run the function once. It breaks when 30 orchestrator calls run the function sequentially, each one overwriting what the previous call wrote.

The file `vulnerability_profile.json` is not just output. It is shared state. It is read by the orchestrator to decide what to do next. It is read by the MCP server to respond to AI queries. It is read by the Socratic tutor to generate lesson guidance. Every component that reads it depends on every component that writes it doing so correctly.

Shared state has rules. You have to read before you write. You have to merge, not overwrite. You have to handle the case where the file does not exist yet or contains corrupted data. None of this is obvious when you are thinking about a single function call.

```python
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
```

This is not difficult code. It is about 10 lines. What it requires is thinking about the file from the perspective of every caller, not just the one you are currently writing.

---

## Portability: the thing you do not think about until you migrate

I ran the scanner on Windows for two months. It worked. I moved to Ubuntu WSL2. Six things broke immediately.

The most instructive was `shell=True`. On Windows, `subprocess.run(cmd, shell=True)` passes `cmd` to `cmd.exe`. On Linux, it passes to `bash`. Their quote-parsing rules are different. A command string containing SQL injection payloads -- which often include single quotes, double quotes, parentheses, and dashes -- would be parsed differently by the two shells. On Linux, what appeared to be a valid URL argument would be split at the quote characters into separate arguments that Playwright did not recognize.

The error message was something like `playwright screenshot: error: unknown option: 'ORDER'`. The word `ORDER` appeared because it was part of the SQL payload in the URL, and bash had split the quoted string at the wrong point. It took a while to connect that error message back to the `shell=True` call that caused it.

```python
# What I had
subprocess.run(f'npx.cmd playwright screenshot "{test_url}" {viz_path}', shell=True)

# What I needed
subprocess.run(["npx", "playwright", "screenshot", test_url, viz_path], capture_output=True)
```

List-based subprocess calls do not go through a shell. Each list element is one argument. SQL characters in the URL are just characters. No shell parses them.

After fixing this, I audited every subprocess call in the codebase for `shell=True` and converted all of them. There were six.

---

## On AI assistance and what it actually does

Claude Sonnet, Qwen, and Kimi were used throughout this project. They wrote large amounts of the code, identified several bugs I had missed, and analyzed log files I did not have time to read carefully.

They also introduced the `` `n `` corruption four times and occasionally produced code that was syntactically valid but logically wrong in ways that took hours to find.

The pattern I noticed: when I brought a well-formed question -- "here is the error, here is the relevant code, here is what I tried" -- the AI gave useful answers. When I brought an ill-formed question -- "why is this lesson failing?" without the log output -- the AI gave plausible-sounding answers that were wrong.

AI assistance appears to scale with the quality of the question. If you understand the problem well enough to describe it precisely, the AI can often solve it faster than you can. If you do not understand the problem yet, the AI's answer may point you in a wrong direction confidently.

This is not a criticism. It is a description of how the tool actually behaves in practice. The implication is that you still need to understand what you are building well enough to evaluate whether the AI's output is correct. You cannot outsource that evaluation.

---

## The Socratic mode question

This project implemented two operating modes: direct audit, which returns full technical data immediately, and Socratic guidance, which returns questions and hints constructed from the same underlying data.

I spent some time thinking about whether a Socratic mode in a security tool is actually useful or whether it is just a feature that sounds educational without being so.

My current view, which I hold with some uncertainty, is that it depends entirely on when you use it. If a student uses Socratic mode to understand how UNION injection works before they have tried anything, it is useful -- it gives them a guided path through the reasoning. If someone uses Socratic mode to avoid doing the work and just asks "what is the answer?" repeatedly until the hints converge on the payload, it is not useful at all.

The tool cannot distinguish between those two users. That distinction is the user's responsibility, not the tool's. I built the mode. What it actually does depends on how you use it.

---

## What the 65 days produced besides a scanner

A list of things that are now habits, or close to habits:

Run `python3 -c "import ast; ast.parse(open(f).read()); print('OK')"` after every file edit. Takes 0.1 seconds. Catches corruption before it reaches a test.

Use list arguments for subprocess calls, never string commands. The cost is zero. The benefit is deterministic behavior across operating systems.

Treat every file that more than one process writes to as shared state. Read before writing. Merge, do not overwrite. Handle missing and corrupt files explicitly.

Check the network path before debugging the code. `curl -v` shows you what the request actually does. `trust_env = False` isolates your requests from system proxy settings.

Test at the boundaries. The scanner worked on single-lesson runs. The race condition only appeared in batch runs. The MCP cascade only appeared with 20 concurrent calls. Some bugs only exist in conditions you do not test until production.

None of these are novel observations. They are standard practices in any production software context. It took breaking things repeatedly in specific ways for them to become practical knowledge rather than abstract advice.
