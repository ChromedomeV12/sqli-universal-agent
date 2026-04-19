# Architecture & Workflow Report: Universal SQLi Agent Toolkit

## 1. Project Objective

To transform a standalone SQL injection solver into an **Interactive Agentic AI Tutor** integrated with OpenCode as an MCP server toolkit. The system follows a Socratic pedagogical model, supported by a master automation layer for zero-token batch processing and systematic documentation.

**Key Updates:**
- Now runs as an MCP server toolkit under OpenCode (not Gemini CLI)
- Supports multiple specialized AI agents:
  - **Lead Architect** (Claude Sonnet 4.6): System design and orchestration
  - **SQL Auditor** (Qwen 3.6+): Security analysis and payload validation
  - **Researcher** (Kimi K2.5): Technical documentation and exploit research
- Runs natively on Linux/WSL2 with no Windows dependency

## 2. Five-Tier System Architecture

### Tier 1: The Oracle (Discovery Engine)

- **Component:** `core/sqli_final.py`
- **Role:** High-speed black-box reconnaissance.
- **Mechanism:** Determines closure types, parameters, and bypass requirements via external HTTP observations.
- **Output:** `core/vulnerability_profile.json` (The "Teacher's Key").

### Tier 2: The Master Orchestrator (Automation Layer)

- **Component:** `core/auto_orchestrator.py`
- **Role:** Coordinates the entire technical lifecycle without requiring AI interaction.
- **Workflow:**
  1. **Reset:** Triggers a single global database reset.
  2. **Scan:** Invokes the Oracle for discovery.
  3. **Capture:** Uses Playwright to generate visual breakout proof.
  4. **Flush:** Routes specialized commands to `sqlmap` for data extraction.
  5. **Organize:** Files all evidence into the `lab_reports/` hierarchy.

### Tier 3: The MCP Server (OpenCode Bridge)

- **Component:** `mcp/sqli_mcp.py`
- **Role:** Exposes `oracle_scan`, `browser_test`, and `launch_windows_firefox` (now cross-platform `launch_firefox`) as MCP tools consumable by any OpenCode agent.
- **Config:** `.opencode/config.json` defines agent model assignments and MCP tool bindings.

### Tier 4: The Elite Tool-Belt (Skillbase)

- **`sqlmap`**: The "Heavy Artillery" for data extraction and WAF bypass.
- **`Burp Suite Pro API`**: For professional auditing and authenticated "Request File" (-r) workflows.
- **`Playwright CLI`**: The "Integrated HackBar" for visual snapshots and DOM interaction.

### Tier 5: The Evidence Vault (Organization)

- **Directory:** `lab_reports/`
- **Structure:** Per-lesson isolation of `discovery/`, `visuals/`, and `automation/` logs.
- **Loot Storage:** `lab_reports/Less-XX/automation/sqlmap_auto.log` stores the extraction output and session logs.

## 3. Project Structure & Hierarchy

The project is organized into a systematic directory structure to maintain a clear separation between tools, automation, and evidence.

```text
sqli-universal-agent/
├── core/
│   ├── sqli_final.py          # Tier 1: The Oracle
│   ├── auto_orchestrator.py   # Tier 2: The Orchestrator
│   ├── sqli_tutor.py          # Interactive tutor CLI
│   ├── config.py              # Cross-platform config (NEW)
│   └── vulnerability_profile.json
├── mcp/
│   └── sqli_mcp.py            # Tier 3: MCP Server bridge
├── docs/
│   ├── ARCHITECTURE_REPORT.md
│   └── SQLI_GUIDE.md
├── lab_reports/               # Tier 5: Evidence Vault
│   └── Less-XX/
│       ├── discovery/oracle_report.txt
│       ├── visuals/
│       └── automation/
└── .opencode/
    ├── config.json            # MCP + agent model config
    └── agents/
        ├── sql-auditor.md
        └── researcher.md
```

## 4. The "Extensive" Workflow

1. **Intercept (Manual):** User captures an authenticated request in Burp.
2. **Bridge (Agentic):** User saves request as `burp_request.txt`.
3. **Exploit (Automated):** Agent runs `sqlmap -r burp_request.txt`.
4. **Learn (Socratic):** Agent explains the tool's payloads and results to the user.

## 5. Black-Box Integrity & Security

- **Black-Box Constraint:** No access to server-side source code; all logic is evidence-based.
- **Secret Management:** API keys are stored in local `.burp_key` files, never hardcoded or transmitted in logs.

## 6. WSL2 Migration Notes

The project has been fully migrated from native Windows to WSL2 (Ubuntu on Windows 11). The following architectural changes support this transition:

### Platform
- **Environment:** Ubuntu WSL2 on Windows 11
- **Python:** System Python 3.x with virtual environment support
- **Node.js:** Required for Playwright CLI operations via `npx`

### Security Hardening
- All `shell=True` subprocess calls have been eliminated — all external tool invocations now use list-based command arrays, preventing shell injection vulnerabilities
- `config.py` provides a single source of truth for all paths and tool locations, eliminating hardcoded absolute paths

### Data Integrity
- `vulnerability_profile.json` now uses merge-write semantics (appends to existing data, never overwrites prior lesson findings)
- Atomic file operations ensure no data loss during concurrent scans

### Known Limitations
- **Parallel MCP Scans:** Running more than 10 concurrent `oracle_scan` operations can trigger a timeout cascade due to subprocess queue saturation. Batch scans to ≤10 concurrent lessons for optimal stability.
- **Firefox Launch:** On WSL2 without a display server, `launch_windows_firefox` requires an X11 forward or WSLg enabled for GUI browser operations. Console mode works without display.
