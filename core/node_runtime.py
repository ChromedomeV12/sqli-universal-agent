"""Select a patched host Node for Playwright instead of its bundled runtime."""

import os
import re
import shutil
import subprocess

_MINIMUMS = {22: (23, 4), 24: (22, 1), 26: (12, 1)}


def patched_node_executable(candidate=None):
    """Validate a configured executable or the Node selected by the host PATH."""
    executable = shutil.which(candidate or "node")
    if not executable:
        raise RuntimeError("A patched Node.js installation is required; see README.md.")
    try:
        result = subprocess.run(
            [executable, "--version"], check=True, capture_output=True,
            text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Cannot verify the selected Node.js runtime.") from exc
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", result.stdout.strip())
    version = tuple(map(int, match.groups())) if match else ()
    if not version or version[0] not in _MINIMUMS or version[1:] < _MINIMUMS[version[0]]:
        raise RuntimeError(
            "Node.js must be >=22.23.4 <23, >=24.22.1 <25, or >=26.12.1 <27."
        )
    return executable


def configure_playwright_node():
    """Reject an unsafe override and never fall back to Playwright's bundled Node."""
    executable = patched_node_executable(os.environ.get("PLAYWRIGHT_NODEJS_PATH"))
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = executable
    return executable
