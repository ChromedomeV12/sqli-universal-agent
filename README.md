# Universal SQLi Agent Toolkit

A high-performance, multi-agent security audit framework for SQL injection, built on the **Model Context Protocol (MCP)**. This toolkit achieved a **100% success rate** on the SQLi-Labs benchmark (Lessons 1-30).

## 🚀 Key Features

- **Universal MCP Server:** Decoupled core logic that works across Gemini CLI, OpenCode, Claude Desktop, and native OS environments.
- **Multi-Agent Workflow:** Integrated subagents specializing in high-level strategy (Sonnet 4.6), technical execution (Qwen 3.6+), and history retrieval (Kimi 2.5).
- **Surgical DOM Evaluation:** Advanced Playwright-driven detection that identifies vulnerabilities via structural DOM JSON evidence rather than visual analysis.
- **Autonomous Evasion:** Built-in tamper scripts for WAF bypass, including Base64 encoding, keyword double-writing, and whitespace substitution.
- **Zero-Latency Caching:** Persistent result caching that reduces subsequent audit times from minutes to seconds.
- **Socratic Mentorship:** A unique "Tutor Mode" that provides heuristic guidance without revealing payloads, designed for academic and training use cases.

## 🏗️ 5-Tier Architecture

1.  **Tier 1: The Oracle (`core/sqli_final.py`)** - Environment-aware black-box detection engine.
2.  **Tier 2: The Orchestrator (`core/auto_orchestrator.py`)** - High-speed batch processing with merge-write integrity.
3.  **Tier 3: Universal MCP Server (`mcp/sqli_mcp.py`)** - Standardized JSON-RPC 2.0 interface.
4.  **Tier 4: The AI Cluster** - Multi-model coordination for strategy, auditing, and research.
5.  **Tier 5: Evidence Vault (`lab_reports/`)** - Automated archival of reports, screenshots, and logs.

## 🛠️ Setup (WSL2 / Linux)

1.  **Clone the Repo:**
    ```bash
    git clone https://github.com/ChromedomeV12/sqli-universal-agent.git
    cd sqli-universal-agent
    ```

2.  **Run the Master Installer:**
    ```bash
    chmod +x setup.sh
    ./setup.sh
    source ~/.bashrc
    ```

3.  **Configure Environment:**
    Set your target Kali IP in your session:
    ```bash
    export TARGET_IP="172.18.0.1"
    ```

## 📖 Academic Documentation

Detailed research deliverables are available in the `final_deliverables/` folder:
- `ACADEMIC_PAPER.md`: Formal research on MCP-based multi-agent collaboration.
- `PROJECT_SUMMARY.md`: 100% success report and architectural deep-dive.
- `LEARNING_REFLECTION.md`: Narrative on the transition from scripts to agentic systems.
- `WORKLOGS.md`: Chronological Technical Evolution Log (2026).

---
*Created by chrom (2026)*
