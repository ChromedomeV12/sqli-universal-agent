import os
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.node_runtime import configure_playwright_node, patched_node_executable


class PatchedNodeTests(unittest.TestCase):
    def check_version(self, version):
        with patch("core.node_runtime.shutil.which", return_value="/runtime/node"), patch(
            "core.node_runtime.subprocess.run", return_value=SimpleNamespace(stdout=version)
        ):
            return patched_node_executable()

    def test_rejects_affected_and_unknown_runtimes(self):
        for version in ("v20.20.0", "v22.23.3", "v24.22.0", "v26.12.0", "v23.9.0", "v28.0.0", "v24.22.1-rc.1", "invalid"):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                self.check_version(version)

    def test_accepts_patched_releases_and_later_same_major(self):
        for version in ("v22.23.4", "v24.22.1", "v26.12.1", "v24.23.0"):
            with self.subTest(version=version):
                self.assertEqual(self.check_version(version), "/runtime/node")

    def test_missing_or_unverifiable_node_fails(self):
        with patch("core.node_runtime.shutil.which", return_value=None), self.assertRaises(RuntimeError):
            patched_node_executable()
        with patch("core.node_runtime.shutil.which", return_value="/runtime/node"), patch(
            "core.node_runtime.subprocess.run", side_effect=subprocess.TimeoutExpired("node", 10)
        ), self.assertRaises(RuntimeError):
            patched_node_executable()

    def test_driver_override_uses_validated_host_and_rejects_unsafe_override(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "core.node_runtime.patched_node_executable", return_value="/runtime/node"
        ) as resolve:
            self.assertEqual(configure_playwright_node(), "/runtime/node")
            self.assertEqual(os.environ["PLAYWRIGHT_NODEJS_PATH"], "/runtime/node")
            resolve.assert_called_once_with(None)
        with patch.dict(os.environ, {"PLAYWRIGHT_NODEJS_PATH": "/old/node"}, clear=True), patch(
            "core.node_runtime.patched_node_executable", side_effect=RuntimeError("old Node")
        ) as resolve, self.assertRaises(RuntimeError):
            configure_playwright_node()
        resolve.assert_called_once_with("/old/node")


if __name__ == "__main__":
    unittest.main()
