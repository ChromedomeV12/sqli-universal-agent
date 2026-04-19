"""
Cross-platform configuration module for the Universal SQLi Agent Toolkit.
Auto-detects platform, locates tools, reads runtime config from env vars,
and provides canonical path helpers.
"""

import os
import platform
import shutil
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Platform auto-detection
# ---------------------------------------------------------------------------
PLATFORM = platform.system().lower()  # "linux" | "windows" | "darwin"

# ---------------------------------------------------------------------------
# 2. Tool location (shutil.which with sensible fallbacks)
# ---------------------------------------------------------------------------
SQLMAP_BIN = shutil.which("sqlmap") or "sqlmap"
NPX_BIN = shutil.which("npx") or "npx"
PYTHON_BIN = sys.executable  # always correct

if PLATFORM == "windows":
    FIREFOX_BIN = "firefox.exe"
else:
    FIREFOX_BIN = shutil.which("firefox") or "firefox"

# ---------------------------------------------------------------------------
# 3. Runtime config from environment variables (with defaults)
# ---------------------------------------------------------------------------
TARGET_IP = os.environ.get("TARGET_IP", "172.18.0.1")
PROXY_HOST_IP = os.environ.get("PROXY_HOST_IP", "127.0.0.1")
PROXY_PORT = os.environ.get("PROXY_PORT", "8080")

# Derived URLs
BASE_URL = f"http://{TARGET_IP}/"
PROXY_URL = f"http://{PROXY_HOST_IP}:{PROXY_PORT}"

# ---------------------------------------------------------------------------
# 4. Canonical path helpers (pathlib.Path)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
CORE_DIR = PROJECT_ROOT / "core"
LAB_REPORTS_DIR = PROJECT_ROOT / "lab_reports"
VULNERABILITY_PROFILE = CORE_DIR / "vulnerability_profile.json"
ORACLE_SCRIPT = CORE_DIR / "sqli_final.py"

# ---------------------------------------------------------------------------
# 5. Startup banner (printed on import)
# ---------------------------------------------------------------------------
print(
    f"[config] Platform: {PLATFORM} | Target: {TARGET_IP} | sqlmap: {SQLMAP_BIN}"
)

# ---------------------------------------------------------------------------
# 6. Lesson directory helper
# ---------------------------------------------------------------------------

def get_lesson_dirs(lesson_num: int) -> dict:
    """Return canonical directory paths for a given lesson number."""
    base = LAB_REPORTS_DIR / f"Less-{lesson_num:02d}"
    return {
        "base": base,
        "discovery": base / "discovery",
        "visuals": base / "visuals",
        "automation": base / "automation",
    }
