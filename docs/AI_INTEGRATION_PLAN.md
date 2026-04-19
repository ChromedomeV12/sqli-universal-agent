# AI Integration Plan: CLI Extension Architecture

## 1. The Goal
Transform our SQL injection solver into a natively integrated **AI CLI Extension** (for Gemini CLI, Claude Code, Qwen Code, etc.). Instead of building a custom Python chat loop, we will leverage the existing, powerful AI agents that developers already use. The extension will provide these agents with the specialized context, skills, and tools needed to act as an Interactive SQLi Tutor.

## 2. Architecture: The Extension Model
We are abandoning the standalone `ai_agent/instructor.py` script. The new system consists of:

1.  **The Oracle (Scanner):** `sqli_final.py` remains our core discovery engine. It outputs `vulnerability_profile.json`.
2.  **The Extension Context (`GEMINI.md` / `SKILL.md`):** Pre-configured context files injected into the AI CLI. This tells the AI: "You are a Socratic security mentor. Use the local JSON profile to guide the user. Do not give direct answers."
3.  **The Skills/Tools:** We provide the AI CLI with custom, isolated skills:
    *   `run-oracle`: A skill that lets the AI execute `sqli_final.py` to scan a target.
    *   `test-payload`: A sandboxed execution skill that allows the AI to securely test the user's payloads via `curl` against the target and analyze the response.

## 3. The New Workflow (AI CLI Native)
*   **User:** Runs `gemini` in their terminal with the SQLi Tutor extension active. "I want to start Less-1."
*   **AI Agent (Gemini):** Uses the `run-oracle` skill in the background to scan Less-1 and reads the JSON output.
*   **AI Agent:** "Alright, let's tackle Less-1. Start by manipulating the URL parameters to see how the application reacts. Try breaking the query syntax."
*   **User:** "I'll try `id=1'`"
*   **AI Agent:** Uses the `test-payload` skill to run `curl` with the payload against the local lab environment. Analyzes the HTML response.
*   **AI Agent:** "Good! That produced a syntax error in the response, confirming it's injectable. Based on the error, what type of database are we dealing with, and what closure might we need?"

## 4. Cross-Platform Compatibility & Future-Proofing
*   **Universal Design:** By using tools like `skill-porter`, the extension's metadata and tools can be adapted for Claude Code or Qwen Code.
*   **Generic Applicability:** The skills will be designed to accept arbitrary URLs and targets. While optimized for SQLi-Labs now, the architecture easily extends to any target (DVWA, real-world bug bounties) by simply running the Oracle against a new URL.

## 5. Next Steps
1.  **Clean up:** Remove the prototype `ai_agent/` directory.
2.  **Extension Scaffolding:** Create `sqli-tutor-extension/` with standard extension manifests (`gemini-extension.json`).
3.  **Context Definition:** Write the specialized `GEMINI.md` context for the tutor persona.
4.  **Skill Creation:** Build the declarative tools (`test-payload.sh` or `.js`) that the AI CLI will use to interact with the lab and the Oracle.