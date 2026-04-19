from mcp.server.fastmcp import FastMCP
import subprocess
import sys
import json
import platform
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

mcp = FastMCP("SQLi-Universal-Tutor")

# Resolve paths from this file's location — immune to $HOME and cwd changes
_PROJECT_ROOT = Path(__file__).parent.parent
CORE_DIR      = _PROJECT_ROOT / "core"
LAB_REPORTS_DIR = _PROJECT_ROOT / "lab_reports"

@mcp.tool()
def oracle_scan(lesson_number: int) -> str:
    """Runs the discovery scanner on the target lesson and returns the vulnerability profile."""
    try:
        cmd = [sys.executable, str(CORE_DIR / "sqli_final.py"), "--lesson", str(lesson_number), "--json", "--no-reset"]
        subprocess.run(cmd, cwd=str(CORE_DIR), capture_output=True, text=True, timeout=120)
        profile_path = CORE_DIR / "vulnerability_profile.json"
        if profile_path.exists():
            with open(profile_path, "r") as f:
                profile = json.load(f)
            lesson_data = profile.get(str(lesson_number))
            if lesson_data:
                return json.dumps(lesson_data, indent=2)
            return json.dumps({"error": f"Lesson {lesson_number} not found in profile. Lesson may be out of range (1-30)."})
        return json.dumps({"error": "Scan completed but vulnerability_profile.json not found."})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": f"Oracle scan for lesson {lesson_number} timed out after 120s."})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.tool()
def browser_test(url: str, payload: str, lesson_id: int) -> str:
    """Uses Playwright Python API to inject a payload and return a surgical DOM summary."""
    viz_dir = LAB_REPORTS_DIR / f"Less-{lesson_id:02d}" / "visuals"
    viz_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = str(viz_dir / "mcp_test.png")
    target = f"{url}{payload}"

    result = {
        "target_url": target,
        "screenshot": screenshot_path,
        "status_code": None,
        "page_title": None,
        "detected_errors": [],
        "body_snippet": None,
        "error": None,
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Capture HTTP status via response interception
            response_ref = {}
            def on_response(response):
                if response.url == target or response.url.rstrip("/") == target.rstrip("/"):
                    response_ref["status"] = response.status
            page.on("response", on_response)

            try:
                page.goto(target, wait_until="domcontentloaded", timeout=15000)
            except PlaywrightTimeoutError:
                result["error"] = "Page load timed out after 15s"
                browser.close()
                return json.dumps(result, indent=2)

            result["status_code"] = response_ref.get("status", "unknown")
            result["page_title"] = page.title()

            # Capture body text (first 500 chars) for surgical analysis
            body_text = page.inner_text("body") if page.query_selector("body") else ""
            result["body_snippet"] = body_text[:500].strip()

            # Detect error patterns relevant to SQLi
            error_patterns = [
                "you have an error in your sql syntax",
                "warning: mysql",
                "xpath syntax error",
                "unclosed quotation mark",
                "quoted string not properly terminated",
                "division by zero",
                "supplied argument is not a valid mysql",
            ]
            lower_body = body_text.lower()
            result["detected_errors"] = [
                p for p in error_patterns if p in lower_body
            ]

            page.screenshot(path=screenshot_path)
            browser.close()

    except Exception as e:
        result["error"] = str(e)

    return json.dumps(result, indent=2)

@mcp.tool()
def get_lesson_guidance(lesson_number: int) -> str:
    """Returns Socratic teaching guidance for a lesson using the tutor's analysis logic."""
    try:
        # Load vulnerability profile for this lesson
        profile_path = CORE_DIR / "vulnerability_profile.json"
        if not profile_path.exists():
            return json.dumps({"error": "vulnerability_profile.json not found. Run oracle_scan first."})

        with open(profile_path, "r") as f:
            profile = json.load(f)

        lesson_data = profile.get(str(lesson_number))
        if not lesson_data:
            return json.dumps({"error": f"No profile found for lesson {lesson_number}. Run oracle_scan({lesson_number}) first."})

        # Import tutor logic from core/
        import importlib.util
        spec = importlib.util.spec_from_file_location("sqli_tutor", CORE_DIR / "sqli_tutor.py")
        tutor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tutor)

        # Construct a result string in the format provide_guidance() expects
        vuln_type  = lesson_data.get("type", "Unknown")
        method     = lesson_data.get("method", "GET")
        closure    = lesson_data.get("closure", "")
        tamper     = lesson_data.get("tamper", "none")
        extra      = lesson_data.get("extra", "")
        result_str = f"{vuln_type} | Method: {method} | Closure: {closure} | Tamper: {tamper}"
        if extra:
            result_str += f" | Extra: {extra}"

        # Load saved payload if available
        payload_file = CORE_DIR / "payloads.txt"
        payload_str = "[No saved payload — run oracle_scan to generate payloads.txt]"
        if payload_file.exists():
            content = payload_file.read_text(encoding="utf-8")
            import re
            blocks = re.split(r"\[Less-(\d+)[^\]]*\]", content)
            for i in range(1, len(blocks), 2):
                if blocks[i] == str(lesson_number):
                    payload_str = blocks[i + 1].strip()
                    break

        # Capture provide_guidance() output as a string
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            tutor.provide_guidance(str(lesson_number), result_str, payload_str)
        guidance_text = buf.getvalue()

        return json.dumps({
            "lesson": lesson_number,
            "vulnerability": result_str,
            "guidance": guidance_text,
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def launch_windows_firefox(url: str) -> str:
    """Launches the local Firefox browser (cross-platform)."""
    try:
        if platform.system().lower() == "windows":
            browser = "firefox.exe"
        else:
            browser = shutil.which("firefox") or "firefox"
        subprocess.Popen([browser, url])
        return f"Launched Firefox at {url}."
    except Exception as e:
        return f"Error launching Firefox: {str(e)}"

if __name__ == "__main__":
    mcp.run()
