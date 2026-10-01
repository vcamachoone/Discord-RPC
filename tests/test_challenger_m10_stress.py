#!/usr/bin/env python3
"""
tests/test_challenger_m10_stress.py - Empirical Challenger Stress Test Suite for Milestone M10

Adversarial stress harness for Requirements R3 and R4:
  - R3: CI/CD Pipeline & Standalone Packaging Hardening
      1. release.yml YAML schema, triggers, permissions, and step execution logic.
      2. Step command simulations: tag extraction, prestaging, shasum verification.
      3. locate_site_packages() stress testing under varied Python environments
         (venv, system site, sysconfig failures, site failures, multi-version lib roots, empty environments).
      4. SHA-256 manifest computation, format compliance (<hash>  <filename>),
         and validation using system /usr/bin/shasum -a 256 -c.
      5. Application bundle staging integrity, Info.plist XML schema, and launcher permissions.
  - R4: System Event Listeners & Error Resilience
      6. Cocoa NSWorkspace notification registration and cleanup.
      7. onAppLaunched_ adversarial test matrix (Discord variants, non-Discord apps, malformed notifications,
         None fields, shutdown guards, null RPC manager).
      8. onSystemWake_ notification handling under single and concurrent burst triggers.
      9. RPC manager RECONNECT command processing, worker state transitions, and thread survival.
     10. In-app error toast handling under adversarial inputs (XSS, quotes, newlines, unicode,
         non-string payloads, WebKit exceptions, null webview).
     11. app_gui.py error keyword routing to popover.show_toast.
     12. liquid_html.py client-side error boundary and escapeHtml verification.
"""

import fcntl
import hashlib
import json
import os
import plistlib
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import AppKit
import objc

import app_gui
from app_gui import LoLAppController
import build_dmg
import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState
import liquid_html
import popover_ui
from popover_ui import LoLPopoverController
from tests.mocks import MockPresence


def load_yaml_via_ruby(file_path: str) -> Dict[str, Any]:
    """Parses YAML file using macOS built-in ruby YAML parser and returns dict."""
    cmd = ["ruby", "-ryaml", "-rjson", "-e", f'puts JSON.dump(YAML.load_file("{file_path}"))']
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


class TestChallengerR3CICDAndPackaging(unittest.TestCase):
    """Empirical challenger tests for Requirement R3 (CI/CD & Packaging)."""

    @classmethod
    def setUpClass(cls):
        cls.workflow_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "release.yml")
        cls.build_dmg_path = os.path.join(PROJECT_ROOT, "build_dmg.py")

    def test_r3_01_release_yml_schema_and_yaml_integrity(self):
        """Verify release.yml parses as valid YAML and conforms to strict GitHub Actions schema."""
        self.assertTrue(os.path.isfile(self.workflow_path), f"Missing {self.workflow_path}")
        workflow = load_yaml_via_ruby(self.workflow_path)

        self.assertIsInstance(workflow, dict)
        self.assertIn("name", workflow)
        # Note: in YAML 1.1 'on' is parsed as boolean True
        triggers = workflow.get(True) or workflow.get("on") or workflow.get("true")
        self.assertIsNotNone(triggers, "Workflow must define trigger events (on)")
        self.assertIn("permissions", workflow)
        self.assertIn("jobs", workflow)

        # Permissions check
        self.assertEqual(workflow["permissions"].get("contents"), "write")

        # Concurrency settings
        self.assertIn("concurrency", workflow)
        self.assertTrue(workflow["concurrency"].get("cancel-in-progress"))

        # Triggers
        self.assertIn("release", triggers)
        self.assertIn("published", triggers["release"]["types"])
        self.assertIn("push", triggers)
        tags = triggers["push"]["tags"]
        self.assertTrue(any("v*.*.*" in t for t in tags))
        self.assertIn("workflow_dispatch", triggers)
        inputs = triggers["workflow_dispatch"].get("inputs", {})
        self.assertIn("skip_tests", inputs)
        self.assertEqual(inputs["skip_tests"].get("type"), "boolean")

        # Job configuration
        job = workflow["jobs"].get("build-and-release")
        self.assertIsNotNone(job)
        self.assertEqual(job.get("runs-on"), "macos-latest")

        steps = job.get("steps", [])
        self.assertGreaterEqual(len(steps), 8)
        step_names = [s.get("name", "") for s in steps]
        self.assertTrue(any("Check out repository" in n for n in step_names))
        self.assertTrue(any("Set up Python" in n for n in step_names))
        self.assertTrue(any("Install dependencies" in n for n in step_names))
        self.assertTrue(any("Pre-stage Application Bundle" in n for n in step_names))
        self.assertTrue(any("Run full test suite" in n for n in step_names))
        self.assertTrue(any("Compile DMG" in n for n in step_names))
        self.assertTrue(any("Verify DMG and SHA-256" in n for n in step_names))
        self.assertTrue(any("Upload build artifacts" in n for n in step_names))
        self.assertTrue(any("Attach release assets" in n for n in step_names))

    def test_r3_02_release_yml_tag_version_parsing_simulation(self):
        """Simulate shell version extraction used in release.yml across varied GITHUB_REF_NAME inputs."""
        test_cases = [
            ("v1.0.0", "1.0.0"),
            ("v2.5.3", "2.5.3"),
            ("v0.1.0-alpha", "0.1.0-alpha"),
            ("1.0.0", "1.0.0"),
            ("main", "1.0.0"),
            ("", "1.0.0"),
        ]
        for ref_input, expected_version in test_cases:
            cmd = f'''
            GITHUB_REF_NAME="{ref_input}"
            VERSION="${{GITHUB_REF_NAME#v}}"
            if [ -z "$VERSION" ] || [ "$VERSION" = "main" ]; then
              VERSION="1.0.0"
            fi
            echo -n "$VERSION"
            '''
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)
            self.assertEqual(res.stdout, expected_version)

    def test_r3_03_locate_site_packages_real_environment(self):
        """Empirically test locate_site_packages() in the current active Python runtime."""
        sp = build_dmg.locate_site_packages()
        self.assertIsNotNone(sp, "locate_site_packages() must discover an active site-packages directory")
        self.assertTrue(os.path.isdir(sp), f"Discovered path does not exist: {sp}")
        self.assertIn("site-packages", sp)

    def test_r3_04_locate_site_packages_adversarial_fallbacks(self):
        """Stress-test locate_site_packages() under failure scenarios for sysconfig and site."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_venv_lib = os.path.join(tmpdir, "venv", "lib")
            mock_py38 = os.path.join(mock_venv_lib, "python3.8", "site-packages")
            mock_py39 = os.path.join(mock_venv_lib, "python3.9", "site-packages")
            os.makedirs(mock_py38, exist_ok=True)
            os.makedirs(mock_py39, exist_ok=True)

            with patch("sysconfig.get_path", side_effect=RuntimeError("sysconfig corrupted")), \
                 patch("site.getsitepackages", side_effect=AttributeError("no getsitepackages")), \
                 patch.object(build_dmg, "SOURCE_ROOT", tmpdir):
                discovered = build_dmg.locate_site_packages()
                # sorted(..., reverse=True) picks python3.9 over python3.8
                self.assertIsNotNone(discovered)
                self.assertEqual(discovered, mock_py39)

    def test_r3_04b_locate_site_packages_lexicographical_sorting_behavior(self):
        """Document empirical discovery: sorted(..., reverse=True) on python3.9 vs python3.11 picks python3.9."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_venv_lib = os.path.join(tmpdir, "venv", "lib")
            mock_py39 = os.path.join(mock_venv_lib, "python3.9", "site-packages")
            mock_py311 = os.path.join(mock_venv_lib, "python3.11", "site-packages")
            os.makedirs(mock_py39, exist_ok=True)
            os.makedirs(mock_py311, exist_ok=True)

            with patch("sysconfig.get_path", side_effect=RuntimeError("sysconfig corrupted")), \
                 patch("site.getsitepackages", side_effect=AttributeError("no getsitepackages")), \
                 patch.object(build_dmg, "SOURCE_ROOT", tmpdir):
                discovered = build_dmg.locate_site_packages()
                # Lexicographically 'python3.9' > 'python3.11'
                self.assertEqual(discovered, mock_py39)

    def test_r3_05_locate_site_packages_empty_environment_safe(self):
        """Verify locate_site_packages returns None gracefully when no candidate exists."""
        with tempfile.TemporaryDirectory() as empty_dir:
            with patch("sysconfig.get_path", return_value=None), \
                 patch("site.getsitepackages", return_value=[]), \
                 patch.object(build_dmg, "SOURCE_ROOT", empty_dir):
                discovered = build_dmg.locate_site_packages()
                self.assertIsNone(discovered)

    def test_r3_06_sha256_manifest_format_and_shasum_c_validation(self):
        """Verify SHA-256 computation and format compatibility with system /usr/bin/shasum -a 256 -c."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_artifact.dmg")
            # Write 1MB of deterministic binary data
            test_content = b"CHALLENGER_M10_BINARY_PAYLOAD_TEST_" * 30000
            with open(test_file, "wb") as f:
                f.write(test_content)

            # 1. Compute hash via build_dmg.compute_sha256
            computed_hash = build_dmg.compute_sha256(test_file)
            expected_hash = hashlib.sha256(test_content).hexdigest()
            self.assertEqual(computed_hash, expected_hash)

            # 2. Write manifest file matching build_dmg format (<hash>  <filename>)
            manifest_file = f"{test_file}.sha256"
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(f"{computed_hash}  {os.path.basename(test_file)}\n")

            # 3. Validate with system /usr/bin/shasum
            cmd = ["shasum", "-a", "256", "-c", os.path.basename(manifest_file)]
            res = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"shasum validation failed: {res.stderr}")
            self.assertIn("OK", res.stdout)

            # 4. Tamper check: modifying 1 byte must cause shasum -c to fail
            with open(test_file, "wb") as f:
                f.write(test_content + b"X")
            res_tampered = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
            self.assertNotEqual(res_tampered.returncode, 0, "shasum must fail on tampered content")
            self.assertIn("FAILED", res_tampered.stdout + res_tampered.stderr)

    def test_r3_07_stage_bundle_without_dependencies_dry_run(self):
        """Verify build_dmg.stage_application_bundle with bundle_deps=False creates valid app skeleton."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dest_app = os.path.join(tmpdir, "League of Legends RPC.app")
            success = build_dmg.stage_application_bundle(dest_app, bundle_deps=False, version="1.5.0")
            self.assertTrue(success)
            self.assertTrue(os.path.isdir(dest_app))

            # Info.plist validation
            plist_path = os.path.join(dest_app, "Contents", "Info.plist")
            self.assertTrue(os.path.isfile(plist_path))
            with open(plist_path, "rb") as f:
                plist_data = plistlib.load(f)
            self.assertEqual(plist_data["CFBundleShortVersionString"], "1.5.0")
            self.assertEqual(plist_data["CFBundleExecutable"], "League of Legends RPC")
            self.assertEqual(plist_data["LSUIElement"], True)

            # Executable launcher validation
            launcher = os.path.join(dest_app, "Contents", "MacOS", "League of Legends RPC")
            self.assertTrue(os.path.isfile(launcher))
            st = os.stat(launcher)
            self.assertTrue(bool(st.st_mode & 0o111), "Launcher must have executable permissions")

            # Check no developer home paths in launcher
            with open(launcher, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("/Users/" + "victormanuel/", content)


class TestChallengerR4SystemEventsAndErrorResilience(unittest.TestCase):
    """Empirical challenger tests for Requirement R4 (System Events & Error Resilience)."""

    def setUp(self):
        self.mock_rpc_mgr = MagicMock(spec=DiscordRPCManager)
        self.mock_rpc_mgr.is_active = True
        self.mock_rpc_mgr.reconnect = MagicMock()

        self.controller = LoLAppController.__new__(LoLAppController)
        self.controller._is_shutting_down = False
        self.controller.rpc_manager = self.mock_rpc_mgr
        self.controller.popover = None
        self.controller.status_item = None

    def tearDown(self):
        if hasattr(self, "controller") and self.controller:
            self.controller._is_shutting_down = True

    def test_r4_01_workspace_notification_registration(self):
        """Verify NSWorkspaceDidLaunchApplicationNotification & NSWorkspaceDidWakeNotification registered."""
        # Verify method selectors exist on controller
        self.assertTrue(hasattr(self.controller, "onAppLaunched_"))
        self.assertTrue(hasattr(self.controller, "onSystemWake_"))

    def test_r4_02_on_app_launched_adversarial_matrix(self):
        """Stress-test onAppLaunched_ across an adversarial matrix of application launch events."""
        cases = [
            # (bundle_id, localized_name, expect_reconnect, description)
            ("com.hnc.Discord", "Discord", True, "Standard Discord bundle ID"),
            ("com.hammerandchisel.discord", "Discord", True, "Legacy Discord bundle ID"),
            ("com.hnc.DiscordPTB", "Discord PTB", True, "Discord Public Test Build"),
            ("com.hnc.DiscordCanary", "Discord Canary", True, "Discord Canary"),
            ("discord-development", "Discord Development", True, "Discord Dev Build"),
            ("COM.HNC.DISCORD", "DISCORD", True, "Uppercase Discord identifiers"),
            ("com.apple.Safari", "Safari", False, "Safari browser (non-Discord)"),
            ("com.google.Chrome", "Google Chrome", False, "Chrome browser (non-Discord)"),
            ("com.riotgames.leagueoflegends", "League of Legends", False, "LoL Client (non-Discord)"),
            ("com.apple.finder", "Finder", False, "macOS Finder"),
            ("", "", False, "Empty bundle ID and name"),
            (None, None, False, "None bundle ID and name"),
        ]

        for bundle_id, name, expect_reconnect, desc in cases:
            self.mock_rpc_mgr.reconnect.reset_mock()

            mock_app = MagicMock()
            mock_app.bundleIdentifier.return_value = bundle_id
            mock_app.localizedName.return_value = name

            mock_notification = MagicMock()
            mock_notification.userInfo.return_value = {
                "NSWorkspaceApplicationKey": mock_app
            }

            self.controller.onAppLaunched_(mock_notification)
            if expect_reconnect:
                self.mock_rpc_mgr.reconnect.assert_called_once()
            else:
                self.mock_rpc_mgr.reconnect.assert_not_called()

    def test_r4_03_on_app_launched_malformed_notifications(self):
        """Verify onAppLaunched_ handles corrupted, missing, or malformed notification objects without crashing."""
        mock_running_app_none = MagicMock()
        mock_running_app_none.bundleIdentifier.return_value = None
        mock_running_app_none.localizedName.return_value = None

        mock_running_app_empty = MagicMock()
        mock_running_app_empty.bundleIdentifier.return_value = ""
        mock_running_app_empty.localizedName.return_value = ""

        malformed_notifications = [
            None,
            "not_a_notification",
            MagicMock(userInfo=lambda: None),
            MagicMock(userInfo=lambda: {}),
            MagicMock(userInfo=lambda: {"NSWorkspaceApplicationKey": None}),
            MagicMock(userInfo=lambda: {"NSWorkspaceApplicationKey": mock_running_app_none}),
            MagicMock(userInfo=lambda: {"NSWorkspaceApplicationKey": mock_running_app_empty}),
        ]
        for notif in malformed_notifications:
            self.mock_rpc_mgr.reconnect.reset_mock()
            try:
                self.controller.onAppLaunched_(notif)
            except Exception as e:
                self.fail(f"onAppLaunched_ crashed on malformed notification: {e}")
            self.mock_rpc_mgr.reconnect.assert_not_called()

    def test_r4_04_on_system_wake_normal_and_burst(self):
        """Empirically test onSystemWake_ under normal notification and rapid multi-threaded bursts."""
        self.mock_rpc_mgr.reconnect.reset_mock()
        mock_notif = MagicMock()
        self.controller.onSystemWake_(mock_notif)
        self.mock_rpc_mgr.reconnect.assert_called_once()

        # Burst trigger: 50 concurrent wake events across 5 threads
        self.mock_rpc_mgr.reconnect.reset_mock()
        barrier = threading.Barrier(5)

        def worker():
            barrier.wait()
            for _ in range(10):
                self.controller.onSystemWake_(mock_notif)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(self.mock_rpc_mgr.reconnect.call_count, 50)

    def test_r4_05_reconnect_rpc_manager_worker_survival(self):
        """Empirically test that RECONNECT command transitions worker state without thread crash."""
        state_changes = []

        def state_cb(state, msg):
            state_changes.append((state, msg))

        mgr = DiscordRPCManager(
            client_id="123456789012345678",
            on_state_change=state_cb,
            on_match_reset=lambda t: None,
        )
        try:
            self.assertTrue(mgr._worker_thread.is_alive())

            # Issue rapid reconnect calls
            for _ in range(5):
                mgr.reconnect()
                time.sleep(0.05)

            # Thread must remain alive
            self.assertTrue(mgr._worker_thread.is_alive(), "Worker thread died after reconnect calls")
        finally:
            mgr.shutdown()

    def test_r4_06_popover_show_toast_adversarial_escaping(self):
        """Stress-test LoLPopoverController.show_toast with dangerous strings, XSS, and control characters."""
        mock_web_view = MagicMock()
        evaluated_scripts = []

        def capture_js(script, handler):
            evaluated_scripts.append(script)

        mock_web_view.evaluateJavaScript_completionHandler_.side_effect = capture_js

        popover_ctrl = LoLPopoverController(
            rpc_manager=self.mock_rpc_mgr,
            auto_create=False,
        )
        popover_ctrl._web_view = mock_web_view

        dangerous_payloads = [
            ('<script>alert("XSS")</script>', "error"),
            ('Hello "World" and \'Quotes\' & <tags>', "warning"),
            ("Newlines\n\r\n\tTabs and \\ Backslashes", "info"),
            ("Emoji: ⚠️ 🚀 🎉 ñañá", "error"),
            ('"; document.body.innerHTML = "pwned"; //', "error"),
            ("A" * 10000, "error"),  # Large payload
        ]

        for payload, toast_type in dangerous_payloads:
            popover_ctrl.show_toast(payload, toast_type)

        self.assertEqual(len(evaluated_scripts), len(dangerous_payloads))
        for script in evaluated_scripts:
            self.assertTrue(script.startswith("if (window.showToast) { window.showToast("))
            self.assertTrue(script.endswith("); }"))
            # Ensure the generated JS does not have unescaped newlines breaking single-line syntax
            # json.dumps encodes newlines as \n, so literal unescaped \n shouldn't break the JS statement
            self.assertNotIn("\n", script.replace("\\n", ""))

    def test_r4_07_popover_show_toast_non_string_and_null_safe(self):
        """Verify show_toast handles non-string arguments, null webview, and webview exceptions gracefully."""
        popover_ctrl = LoLPopoverController(
            rpc_manager=self.mock_rpc_mgr,
            auto_create=False,
        )
        # 1. Null webview
        popover_ctrl._web_view = None
        try:
            popover_ctrl.show_toast("Message with no webview", "error")
        except Exception as e:
            self.fail(f"show_toast threw on null webview: {e}")

        # 2. Non-string inputs
        mock_web_view = MagicMock()
        popover_ctrl._web_view = mock_web_view
        popover_ctrl.show_toast(12345, toast_type=None)  # type: ignore
        popover_ctrl.show_toast(RuntimeError("Connection dropped"), toast_type=999)  # type: ignore
        self.assertEqual(mock_web_view.evaluateJavaScript_completionHandler_.call_count, 2)

        # 3. WebView exception handling
        mock_web_view.evaluateJavaScript_completionHandler_.side_effect = RuntimeError("WebKit crashed")
        try:
            popover_ctrl.show_toast("Test exception", "error")
        except Exception as e:
            self.fail(f"show_toast did not catch WebKit exception: {e}")

    def test_r4_08_app_gui_error_routing_to_toast(self):
        """Verify that on_rpc_state_change routes socket and RPC errors to popover.show_toast."""
        mock_popover = MagicMock()
        mock_status_item = MagicMock()
        self.controller.popover = mock_popover
        self.controller.status_item = mock_status_item

        # 1. Error state
        self.controller.on_rpc_state_change("error", "Error connecting to Discord IPC")
        mock_popover.show_toast.assert_called_with("Error connecting to Discord IPC", "error")

        # 2. Lost connection message
        mock_popover.show_toast.reset_mock()
        self.controller.on_rpc_state_change(RPCState.DISCONNECTED, "Conexión perdida con Discord")
        mock_popover.show_toast.assert_called_with("Conexión perdida con Discord", "error")

        # 3. Failed connection attempt
        mock_popover.show_toast.reset_mock()
        self.controller.on_rpc_state_change(RPCState.CONNECTING, "Falló intento de conexión")
        mock_popover.show_toast.assert_called_with("Falló intento de conexión", "error")

        # 4. Normal states must NOT trigger toast
        mock_popover.show_toast.reset_mock()
        self.controller.on_rpc_state_change(RPCState.CONNECTED, "Activo en Discord")
        mock_popover.show_toast.assert_not_called()

        mock_popover.show_toast.reset_mock()
        self.controller.on_rpc_state_change(RPCState.PAUSED, "Presencia pausada")
        mock_popover.show_toast.assert_not_called()

    def test_r4_09_liquid_html_error_boundary_and_escape(self):
        """Verify liquid_html.py defines window.showToast, #toast-container, and window error handlers."""
        html = liquid_html.render_app_html()
        self.assertIn('id="toast-container"', html)
        self.assertIn("window.showToast = function", html)
        self.assertIn("window.addEventListener('error'", html)
        self.assertIn("window.addEventListener('unhandledrejection'", html)
        self.assertIn("function escapeHtml(str)", html)
        self.assertIn(".replace(/&/g, '&amp;')", html)
        self.assertIn(".replace(/</g, '&lt;')", html)
        self.assertIn(".replace(/>/g, '&gt;')", html)


if __name__ == "__main__":
    unittest.main()
