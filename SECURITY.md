# Security Policy

This is an offensive-security research toolkit. This policy covers two distinct things that often get confused: the security of this repository's code, and the security of the deliberately vulnerable benchmark it runs against. Read both sections before deploying anything.

## Supported Versions

| Version | Python compatibility | Status |
|---------|---------------------|--------|
| main    | 3.10 - 3.13         | Active, receives fixes |
| older commits | -             | Not supported; use main |

## Reporting a Vulnerability

**Do not open a public issue for security reports.**

This repository has GitHub Private Vulnerability Reporting enabled. Go to the *Security* tab and use *Report a vulnerability*. Reports go directly and privately to the maintainer.

- You will get an acknowledgement within 72 hours.
- Fix or a written mitigation decision within 14 days for anything rated High or above.
- Credit is given in the advisory if you want it; say so in your report.

Safe harbor: research performed in good faith against your own local deployment of this toolkit, or against a benchmark target you are authorized to test, will not be met with legal action. That offer ends the moment someone tests against a system they do not own or are not authorized to assess.

## Intended Use and Threat Model

- This toolkit attacks **intentionally vulnerable benchmark code** (SQLi-Labs). It exists for education and controlled research. Use it only against systems you own or have explicit written authorization to test.
- Every byte returned by the target is **untrusted, attacker-controllable data**, and it flows into `vulnerability_profile.json`, `scan_results.txt`, `payloads.txt`, `lab_reports/`, and from there into LLM context through the MCP tools. A benchmark page can therefore inject text into an agent's context. Run your AI agents with the least privilege that still works (no unrelated shell access, no unrelated repository write access) and treat tool outputs as data, never as instructions you execute blindly.
- Screenshots and payload files are written under `lab_reports/` and `visuals/`; review them before sharing anything publicly, they contain dumped passwords from the benchmark database.

## PHP2Shell Advisory: CVE-2026-109618 and CVE-2026-109619 (October 21, 2026)

On 2026-10-21 the PHP project shipped emergency patches for two critical, unauthenticated remote-code-execution vulnerabilities in PHP core (CVE-2026-109618, out-of-memory `longjmp()` state corruption; CVE-2026-109619, stale-global-state use-after-free), collectively known as "PHP2Shell". CVSS v4.0 9.2 per the PHP security team; some researchers rate 10.0. They affect every PHP installation that serves web requests, including Apache `mod_php`, PHP-FPM, `php-cgi`, FrankenPHP, and LiteSpeed. Fixed releases are PHP 8.2.35, 8.3.36, 8.4.27, and 8.5.12. EOL branches (PHP 5, 6, 7) get no patch at all.

Status for this project:

1. **The toolkit itself is not affected.** This repository contains zero PHP files. The scanner, orchestrator, tutor, and MCP server are Python; nothing here ships, requires, or executes PHP.
2. **The benchmark target historically is affected, and cannot be patched.** The classic SQLi-Labs image ships PHP 5.5.9 under Apache `mod_php`, which is squarely inside the affected product population, and PHP 5.x receives no fix for these CVEs. A lab target exposed to any network other than the machine itself is therefore exploitable by unauthenticated RCE, on top of the SQLi flaws that make it a benchmark in the first place.

If you deploy a lab target, the following controls are mandatory, not optional:

- Keep the target bound to a loopback or private container network. Never publish or port-forward it (`-p 80:80` on a public host is how PHP2Shell-class bugs get fired at your box within hours of disclosure).
- Point `TARGET_IP` at that private address only, and verify: `docker port <container>` should show nothing published, and a request to the target from any host other than the one it runs on should fail.
- Treat the container as assumed-compromised and disposable. Rebuild it rather than cleaning it.
- Consider replacing the EOL PHP 5.5.9 image with a self-built SQLi-Labs instance on a patched PHP 8.2+ runtime if you want to run longer-term experiments, since the intentional SQLi flaws come from the lesson PHP files, not from the interpreter version.

The Python toolkit does not enable or worsen these CVEs: it sends ordinary HTTP requests to the target and parses responses; it never parses or executes PHP itself.

## Dependency Health

- All runtime pins live in `requirements.txt` and are audit-checked on every push by the `pip-audit` GitHub Actions workflow; failures break the build on purpose.
- Dependabot alerts and automated security updates are enabled, and Dependabot opens version-bump PRs weekly (`pip` and `github-actions` ecosystems).
- Secret scanning and secret-scanning push protection are enabled at the repository level.

## What Is Automatically Enabled on This Repository

| Feature | State |
|---------|-------|
| Dependabot security alerts | Enabled |
| Dependabot automated security updates | Enabled |
| Dependabot version updates (pip, github-actions) | Enabled via `.github/dependabot.yml` |
| Private vulnerability reporting | Enabled |
| Secret scanning + push protection | Enabled |
| CodeQL static analysis | Enabled via `.github/workflows/codeql.yml` (Python, security-extended) |
| pip-audit dependency scan | Enabled via `.github/workflows/pip-audit.yml` (push + PR + daily schedule) |

## Operational Notes for Anyone Running This Toolkit

- Inventory data ends up in `lab_reports/` with real dumped credentials from the benchmark. That is evidence, do not publish it without review.
- `setup.sh` clones sqlmap from upstream at the time of install. That source is fetched, not vendored; CI does not cover it. If supply-chain integrity matters to you, clone sqlmap with a pinned commit hash instead of `--depth 1` at HEAD.
- The MCP server runs Playwright and launches a local browser. Do not expose the MCP server over a network; it expects a local agent client.
