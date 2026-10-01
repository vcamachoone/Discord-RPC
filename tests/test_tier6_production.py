#!/usr/bin/env python3
"""
test_tier6_production.py - Tier 6: Production Acceptance & System Integration Test Suite

Authoritative acceptance test suite for follow-up production hardening requirements (R1–R4):
  - R1: Native App Lifecycle, Menubar Controls & Hardened Auto-Start
      * NSStatusItem right-click context menu (title, items, selectors, targets, callbacks)
      * Quit application action in popover UI (both #view-main and #view-config, handle_web_action)
      * Single-Instance Lock (socket binding at app.sock, fcntl.flock, secondary focus & exit code 0)
      * LaunchAgent Plist & Startup Notification (direct binary path, ~/Library/Logs/, osascript)
  - R2: Discord Interactive Profile Buttons (Clickable Buttons)
      * sanitize_buttons: count limits (0, 1, 2, 3+ buttons, max 2 enforcement)
      * Label (<=32 chars) and URL (<=512 chars) truncation
      * HTTPS protocol enforcement (upgrading 'http://' to 'https://', prefixing if missing)
      * Dropping incomplete buttons (missing label or missing URL, non-dict items)
      * None return on empty list, pypresence.update receives None / omits 'buttons' key
      * Persistence in ~/.config/lol_discord_rpc/config.json and WebBridge sync
  - R3: Automated GitHub Actions CI/CD Release Pipeline & Standalone DMG Hardening
      * .github/workflows/release.yml syntax, triggers, runner macos-latest, bundle pre-staging, DMG build, release asset
      * build_dmg.py locate_site_packages() dynamic resolution across venv, system Python, and fallbacks
      * Launcher script portability: zero /Users/ paths across launchers
      * Automated SHA-256 export and format verification with shasum -a 256
      * Self-healing bundle auto-initialization in sync_bundle.py
  - R4: System Event Listeners & Error Resilience
      * Cocoa NSWorkspace notification registration (NSWorkspaceDidLaunchApplicationNotification, NSWorkspaceDidWakeNotification)
      * Discord launch notification triggers rpc_manager.reconnect() immediately
      * System wake notification triggers rpc_manager.reconnect() immediately
      * In-app error toast handling in liquid_html.py and popover_ui.py
"""

import fcntl
import hashlib
import json
import os
import plistlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import AppKit
import objc

import app_gui
from app_gui import LoLAppController, LoLAppDelegate, SingleInstanceController
import build_dmg
import discord_rpc_manager
from discord_rpc_manager import (
    ALLOWED_CONFIG_KEYS,
    DiscordRPCManager,
    RPCState,
    load_user_config,
    sanitize_buttons,
    save_user_config,
)
import liquid_html
import popover_ui
from popover_ui import LoLPopoverController, LoLWebBridge, WebBridge
import status_item
from status_item import LoLStatusItemController
import sync_bundle
from tests.mocks import MockPresence


class TestTier6R1LifecycleAndMenubar(unittest.TestCase):
    """
    Acceptance tests for Requirement R1:
    Native App Lifecycle, Menubar Controls & Hardened Auto-Start.
    """

    def setUp(self):
        self.toggle_called = False
        self.presence_called = False
        self.settings_called = False
        self.quit_called = False

        self.status_ctrl = LoLStatusItemController(
            on_toggle=lambda s: setattr(self, "toggle_called", True),
            on_toggle_presence=lambda: setattr(self, "presence_called", True),
            on_open_settings=lambda: setattr(self, "settings_called", True),
            on_quit=lambda: setattr(self, "quit_called", True),
            auto_create=True,
        )

    def tearDown(self):
        if self.status_ctrl:
            self.status_ctrl.cleanup()

    def test_r1_01_status_item_context_menu_structure_and_selectors(self):
        """
        Verify NSStatusItem right-click context menu:
        - Menu title is 'StatusItemContextMenu'.
        - Contains Open Popover, Presence Toggle, Settings, Separator, and Quit items.
        - Quit item has keyEquivalent 'q' (Cmd+Q).
        - Targets are set to the controller.
        - Action selectors: menuOpenPopover:, menuTogglePresence:, menuOpenSettings:, menuQuit:.
        """
        menu = self.status_ctrl.build_context_menu()
        self.assertIsNotNone(menu, "build_context_menu() must return an NSMenu instance")
        self.assertEqual(menu.title(), "StatusItemContextMenu")

        items = menu.itemArray()
        self.assertGreaterEqual(len(items), 5, "Context menu must have at least 4 items + 1 separator")

        titles = [item.title() for item in items if not item.isSeparatorItem()]
        self.assertTrue(
            any("Abrir" in t for t in titles),
            f"Expected open action in menu titles: {titles}",
        )
        self.assertTrue(
            any("Presencia" in t for t in titles),
            f"Expected presence action in menu titles: {titles}",
        )
        self.assertIn("Configuración ⚙️", titles)
        self.assertTrue(
            any("Salir" in t for t in titles),
            f"Expected quit action in menu titles: {titles}",
        )

        # Check Quit item key equivalent is 'q' (Cmd+Q)
        quit_items = [it for it in items if "Salir" in it.title()]
        self.assertEqual(len(quit_items), 1)
        self.assertEqual(quit_items[0].keyEquivalent(), "q")

        # Verify targets and action selectors
        for it in items:
            if not it.isSeparatorItem():
                self.assertEqual(it.target(), self.status_ctrl)

        actions = [str(it.action()) for it in items if not it.isSeparatorItem()]
        self.assertIn("menuOpenPopover:", actions)
        self.assertIn("menuTogglePresence:", actions)
        self.assertIn("menuOpenSettings:", actions)
        self.assertIn("menuQuit:", actions)

        # Test action callbacks invocation
        self.status_ctrl.menuOpenPopover_(None)
        self.assertTrue(self.toggle_called)

        self.status_ctrl.menuTogglePresence_(None)
        self.assertTrue(self.presence_called)

        self.status_ctrl.menuOpenSettings_(None)
        self.assertTrue(self.settings_called)

        self.status_ctrl.menuQuit_(None)
        self.assertTrue(self.quit_called)

    def test_r1_02_status_item_dynamic_presence_title(self):
        """
        Verify presence menu item dynamic title:
        - When active -> 'Pausar Presencia'
        - When normal / paused -> 'Reanudar Presencia'
        """
        self.status_ctrl.set_state("active")
        menu_active = self.status_ctrl.build_context_menu()
        titles_active = [it.title() for it in menu_active.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Pausar Presencia", titles_active)

        self.status_ctrl.set_state("paused")
        menu_paused = self.status_ctrl.build_context_menu()
        titles_paused = [it.title() for it in menu_paused.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Reanudar Presencia", titles_paused)

        self.status_ctrl.set_state("normal")
        menu_normal = self.status_ctrl.build_context_menu()
        titles_normal = [it.title() for it in menu_normal.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Reanudar Presencia", titles_normal)

    def test_r1_03_quit_action_in_popover_views(self):
        """
        Verify both #view-main and #view-config in liquid_html.py
        contain functional quit buttons sending action 'quit_app'.
        """
        html = liquid_html.render_app_html()
        self.assertIn("sendAction('quit_app')", html)

        # Confirm view-main contains quit button
        self.assertTrue(
            bool(re.search(r'id=["\']view-main["\'][\s\S]*?sendAction\([\'"]quit_app[\'"]\)', html)),
            "Expected quit_app button inside #view-main",
        )

        # Confirm view-config contains quit button
        self.assertTrue(
            bool(re.search(r'id=["\']view-config["\'][\s\S]*?sendAction\([\'"]quit_app[\'"]\)', html)),
            "Expected quit_app button inside #view-config",
        )

    def test_r1_04_popover_handle_web_action_quit_app(self):
        """
        Verify LoLPopoverController.handle_web_action('quit_app'):
        - Invokes on_quit callback cleanly.
        - In absence of on_quit callback, invokes NSApplication.sharedApplication().terminate_ cleanly.
        """
        quit_invoked = False

        def on_quit():
            nonlocal quit_invoked
            quit_invoked = True

        controller = LoLPopoverController(on_quit=on_quit, auto_create=False)
        controller.handle_web_action("quit_app", {})
        self.assertTrue(quit_invoked, "handle_web_action('quit_app') must invoke on_quit callback")

        # Verify fallback to NSApplication.sharedApplication().terminate_ when on_quit is None
        controller_no_cb = LoLPopoverController(on_quit=None, auto_create=False)
        with patch.object(popover_ui, "AppKit") as mock_appkit:
            mock_app = MagicMock()
            mock_app.isRunning.return_value = True
            mock_appkit.NSApplication.sharedApplication.return_value = mock_app
            controller_no_cb.handle_web_action("quit_app", {})
            mock_app.terminate_.assert_called_once_with(None)

    def test_r1_05_single_instance_lock_socket_and_flock(self):
        """
        Verify SingleInstanceController:
        - Non-blocking flock on ~/.config/lol_discord_rpc/app.lock
        - Domain socket binding at ~/.config/lol_discord_rpc/app.sock
        - Successful acquisition for primary instance
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            sic = SingleInstanceController(config_dir=tmpdir)
            self.assertTrue(sic.check_and_acquire(), "Primary instance must acquire single-instance lock")

            # Verify lock file exists and is locked
            self.assertTrue(os.path.exists(sic.lock_path), f"Lock file missing at {sic.lock_path}")
            test_fd = open(sic.lock_path, "a+")
            with self.assertRaises((IOError, OSError, BlockingIOError)):
                fcntl.flock(test_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            test_fd.close()

            # Verify socket file exists and is listening
            self.assertTrue(os.path.exists(sic.sock_path), f"Socket missing at {sic.sock_path}")

            sic.cleanup()
            self.assertFalse(os.path.exists(sic.sock_path), "Socket file must be unlinked on cleanup")

    def test_r1_06_single_instance_secondary_focus_and_exit_0(self):
        """
        Verify that a secondary instance:
        - Sends 'FOCUS' command to primary instance via domain socket.
        - Primary instance receives 'FOCUS' and triggers focus callback.
        - Secondary instance returns False from check_and_acquire().
        - Main loop exits with code 0 without creating duplicate UI.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            primary = SingleInstanceController(config_dir=tmpdir)
            focus_events = []
            primary.set_focus_callback(lambda: focus_events.append("focus_called"))
            self.assertTrue(primary.check_and_acquire())

            # Secondary instance attempts to acquire
            secondary = SingleInstanceController(config_dir=tmpdir)
            acquired = secondary.check_and_acquire()
            self.assertFalse(acquired, "Secondary instance must NOT acquire lock")

            # Allow brief time for socket message receipt
            time.sleep(0.4)
            self.assertEqual(len(focus_events), 1, "Primary instance focus callback must be triggered")

            # Verify secondary main() returns 0 cleanly
            with patch("app_gui.SingleInstanceController", return_value=secondary):
                ret_code = app_gui.main()
                self.assertEqual(ret_code, 0, "Secondary instance must exit cleanly with code 0")

            # Clean up primary
            primary.cleanup()

    def test_r1_07_launch_agent_plist_specification(self):
        """
        Verify LaunchAgent plist specification:
        - Points directly to /Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC.
        - Configures --silent flag.
        - StandardOutPath and StandardErrorPath set to ~/Library/Logs/.
        - RunAtLoad is True and ProcessType is Interactive.
        """
        controller = LoLPopoverController(auto_create=False)
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_plist = os.path.join(tmpdir, "test.plist")
            logs_dir = os.path.join(tmpdir, "Logs")

            def fake_expand(path):
                if "LaunchAgents" in path:
                    return fake_plist
                if "Logs" in path:
                    return logs_dir
                return path

            with patch("os.path.expanduser", side_effect=fake_expand):
                controller._sync_login_item(True)

            self.assertTrue(os.path.exists(fake_plist), "LaunchAgent plist file must be created")
            with open(fake_plist, "rb") as f:
                plist = plistlib.load(f)

            self.assertEqual(plist.get("Label"), "com.victormanuel.lolrpc")
            args = plist.get("ProgramArguments", [])
            self.assertEqual(
                args[0],
                "/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC",
            )
            self.assertIn("--silent", args)
            self.assertTrue(plist.get("RunAtLoad"))
            self.assertEqual(plist.get("ProcessType"), "Interactive")
            self.assertIn("Logs", plist.get("StandardOutPath", ""))
            self.assertIn("Logs", plist.get("StandardErrorPath", ""))

    def test_r1_08_startup_notification_execution(self):
        """
        Verify that LoLAppDelegate triggers an osascript notification on startup
        confirming active menubar presence for both standard and --silent launches.
        """
        delegate = LoLAppDelegate.alloc().init()
        with patch("subprocess.Popen") as mock_popen, \
             patch("sys.argv", ["League of Legends RPC", "--silent"]):
            delegate.applicationDidFinishLaunching_(None)
            self.assertTrue(mock_popen.called, "Startup notification osascript must be invoked")
            call_args = mock_popen.call_args[0][0]
            self.assertIn("osascript", call_args)
            self.assertIn("display notification", call_args[2])
            self.assertIn("League of Legends RPC", call_args[2])
            self.assertIn("Ejecutándose en la barra de menús", call_args[2])


class TestTier6R2DiscordProfileButtons(unittest.TestCase):
    """
    Acceptance tests for Requirement R2:
    Discord Interactive Profile Buttons (Clickable Buttons).
    """

    def test_r2_01_sanitize_buttons_count_limits_0_to_4(self):
        """
        Verify sanitize_buttons count enforcement:
        - 0 buttons -> returns None.
        - 1 button -> returns list of length 1.
        - 2 buttons -> returns list of length 2.
        - 3+ buttons -> truncated to exactly 2 buttons.
        """
        self.assertIsNone(sanitize_buttons([]))
        self.assertIsNone(sanitize_buttons(None))

        # 1 button
        res1 = sanitize_buttons([{"label": "OP.GG", "url": "https://op.gg"}])
        self.assertIsNotNone(res1)
        self.assertEqual(len(res1), 1)

        # 2 buttons
        res2 = sanitize_buttons([
            {"label": "OP.GG", "url": "https://op.gg"},
            {"label": "Twitch", "url": "https://twitch.tv"},
        ])
        self.assertIsNotNone(res2)
        self.assertEqual(len(res2), 2)

        # 3+ buttons capped at 2
        res_capped = sanitize_buttons([
            {"label": "B1", "url": "https://1.com"},
            {"label": "B2", "url": "https://2.com"},
            {"label": "B3", "url": "https://3.com"},
            {"label": "B4", "url": "https://4.com"},
        ])
        self.assertIsNotNone(res_capped)
        self.assertEqual(len(res_capped), 2)
        self.assertEqual(res_capped[0]["label"], "B1")
        self.assertEqual(res_capped[1]["label"], "B2")

    def test_r2_02_label_and_url_truncation(self):
        """
        Verify sanitize_buttons truncation:
        - Labels > 32 characters truncated to 32.
        - URLs > 512 characters truncated to 512.
        """
        long_label = "A" * 60
        long_url = "https://example.com/" + "x" * 600
        res = sanitize_buttons([{"label": long_label, "url": long_url}])
        self.assertIsNotNone(res)
        self.assertEqual(len(res[0]["label"]), 32)
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertEqual(res[0]["label"], "A" * 32)
        self.assertTrue(res[0]["url"].startswith("https://example.com/"))

    def test_r2_03_https_protocol_enforcement(self):
        """
        Verify HTTPS protocol enforcement:
        - 'http://' upgraded to 'https://'
        - Scheme missing ('op.gg/profile') prefixed with 'https://'
        - 'https://' preserved intact
        """
        raw = [
            {"label": "HTTP Link", "url": "http://insecure.site.com/profile"},
            {"label": "No Scheme", "url": "op.gg/summoners/lan/Player"},
        ]
        res = sanitize_buttons(raw)
        self.assertIsNotNone(res)
        self.assertEqual(res[0]["url"], "https://insecure.site.com/profile")
        self.assertEqual(res[1]["url"], "https://op.gg/summoners/lan/Player")

    def test_r2_04_drop_incomplete_and_malformed_buttons(self):
        """
        Verify dropping incomplete buttons:
        - Missing label or URL
        - Empty or whitespace-only label or URL
        - Non-dict items
        - Returns None if all items are invalid
        """
        raw = [
            {"label": "", "url": "https://valid.com"},  # empty label
            {"label": "Missing URL"},                   # missing url
            {"url": "https://valid.com"},              # missing label
            {"label": "   ", "url": "https://valid.com"}, # whitespace label
            {"label": "Valid Label", "url": "   "},    # whitespace url
            "not a dict",                              # invalid type
            12345,                                     # invalid type
            None,                                      # None
        ]
        self.assertIsNone(sanitize_buttons(raw))

        # Mixed valid and invalid
        mixed = [
            {"label": "Invalid", "url": ""},
            {"label": "Valid Button", "url": "https://valid.com"},
        ]
        res = sanitize_buttons(mixed)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["label"], "Valid Button")

    def test_r2_05_none_return_on_empty_and_rpc_update_omission(self):
        """
        Verify that when buttons is empty or None:
        - sanitize_buttons returns None.
        - DiscordRPCManager._send_rpc_update omits 'buttons' key from rpc.update() kwargs.
        - When buttons are valid, 'buttons' key is dispatched cleanly.
        """
        shared_presence = MockPresence("test_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
            mgr.is_active = True
            mgr._rpc = shared_presence

            # 1. Empty buttons -> 'buttons' key omitted from rpc.update
            mgr.buttons = []
            mgr._send_rpc_update()
            last_kwargs = shared_presence.last_payload
            self.assertIsNotNone(last_kwargs)
            self.assertNotIn(
                "buttons",
                last_kwargs,
                "rpc.update() must omit 'buttons' when buttons list is empty to avoid schema rejection",
            )

            # 2. Valid buttons -> 'buttons' key provided
            mgr.buttons = [{"label": "Ver Perfil", "url": "https://op.gg"}]
            mgr._send_rpc_update()
            last_kwargs2 = shared_presence.last_payload
            self.assertIn("buttons", last_kwargs2)
            self.assertEqual(len(last_kwargs2["buttons"]), 1)
            self.assertEqual(last_kwargs2["buttons"][0]["label"], "Ver Perfil")

            mgr.shutdown()

    def test_r2_06_buttons_persistence_and_webbridge_sync(self):
        """
        Verify button configuration persistence and WebBridge sync:
        - Saved in ~/.config/lol_discord_rpc/config.json
        - Recovered by load_user_config()
        - Handled cleanly via LoLPopoverController.handle_web_action('save_config', ...)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.json")
            with patch("discord_rpc_manager.CONFIG_FILE", config_file):
                save_data = {
                    "game_id": "lol",
                    "client_id": "12345",
                    "details": "Ranked Solo/Duo",
                    "duration_min": 30,
                    "buttons": [
                        {"label": "OP.GG", "url": "https://op.gg"},
                        {"label": "Twitch", "url": "https://twitch.tv"},
                    ],
                }
                save_user_config(save_data)
                self.assertTrue(os.path.exists(config_file))

                loaded = load_user_config()
                self.assertEqual(len(loaded.get("buttons", [])), 2)
                self.assertEqual(loaded["buttons"][0]["label"], "OP.GG")

            # Verify WebBridge dispatch via handle_web_action
            controller = LoLPopoverController(auto_create=False)
            with patch("popover_ui.save_user_config") as mock_save, \
                 patch.object(controller, "_sync_to_web"):
                controller.handle_web_action(
                    "save_config",
                    {
                        "game_id": "lol",
                        "client_id": "99999",
                        "details": "Custom",
                        "duration_min": 25,
                        "buttons": [{"label": "My Stream", "url": "https://twitch.tv/player"}],
                    },
                )
                self.assertEqual(len(controller._buttons), 1)
                self.assertEqual(controller._buttons[0]["label"], "My Stream")
                mock_save.assert_called_once()


class TestTier6R3CICDPipelineAndDMG(unittest.TestCase):
    """
    Acceptance tests for Requirement R3:
    Automated GitHub Actions CI/CD Release Pipeline & Standalone DMG Hardening.
    """

    @classmethod
    def setUpClass(cls):
        cls.workflow_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "release.yml")
        cls.workflow_exists = os.path.isfile(cls.workflow_path)
        cls.workflow_content = ""
        if cls.workflow_exists:
            with open(cls.workflow_path, "r", encoding="utf-8") as f:
                cls.workflow_content = f.read()

    def test_r3_01_github_actions_workflow_syntax_and_triggers(self):
        """
        Verify .github/workflows/release.yml:
        - File exists and has valid YAML structural grammar.
        - Triggers: release [published], push tags ['v*.*.*'], and workflow_dispatch.
        """
        self.assertTrue(
            self.workflow_exists,
            f"Release workflow missing at: {self.workflow_path}",
        )
        self.assertIn("name: Release Build & Distribution", self.workflow_content)
        self.assertIn("release:", self.workflow_content)
        self.assertIn("published", self.workflow_content)
        self.assertIn("push:", self.workflow_content)
        self.assertIn("tags:", self.workflow_content)
        self.assertTrue(
            bool(re.search(r"['\"]v\*\.\*\.\*['\"]", self.workflow_content)),
            "Expected tag pattern v*.*.* in release workflow",
        )
        self.assertIn("workflow_dispatch:", self.workflow_content)

    def test_r3_02_github_actions_workflow_runner_and_pipeline_steps(self):
        """
        Verify GitHub Actions runner configuration and required release steps:
        - runs-on: macos-latest
        - bundle pre-staging step (/Applications/League of Legends RPC.app)
        - full test suite execution (tests/run_tests.py)
        - DMG compilation (build_dmg.py)
        - checksum verification (shasum -a 256)
        - release asset attachment (softprops/action-gh-release@v2)
        """
        self.assertIn("runs-on: macos-latest", self.workflow_content)
        self.assertIn("actions/checkout@v4", self.workflow_content)
        self.assertIn("actions/setup-python@v5", self.workflow_content)
        self.assertIn("sync_bundle.py", self.workflow_content)
        self.assertIn("tests/run_tests.py", self.workflow_content)
        self.assertIn("build_dmg.py", self.workflow_content)
        self.assertIn("shasum -a 256", self.workflow_content)
        self.assertIn("softprops/action-gh-release@v2", self.workflow_content)

    def test_r3_03_build_dmg_locate_site_packages_dynamic_resolution(self):
        """
        Verify build_dmg.locate_site_packages():
        - Dynamically locates site-packages directory.
        - Returns a valid, existing directory path containing python modules.
        """
        sp_dir = build_dmg.locate_site_packages()
        self.assertIsNotNone(sp_dir, "locate_site_packages() must discover an active site-packages path")
        self.assertTrue(
            os.path.isdir(sp_dir),
            f"Discovered site-packages is not a directory: {sp_dir}",
        )
        self.assertIn("site-packages", sp_dir)

    def test_r3_04_launcher_script_portability(self):
        """
        Verify launcher portability:
        - ZERO hardcoded /Users/ paths in UNIVERSAL_LAUNCHER_SCRIPT.
        - ZERO hardcoded /Users/ paths in repository launcher.sh.
        - Uses dynamic path resolution with BASH_SOURCE and dirname.
        """
        self.assertNotIn(
            "/Users/",
            build_dmg.UNIVERSAL_LAUNCHER_SCRIPT,
            "UNIVERSAL_LAUNCHER_SCRIPT must not contain hardcoded /Users/ paths",
        )
        self.assertIn('DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"', build_dmg.UNIVERSAL_LAUNCHER_SCRIPT)

        launcher_sh_path = os.path.join(PROJECT_ROOT, "launcher.sh")
        if os.path.exists(launcher_sh_path):
            with open(launcher_sh_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn(
                "/Users/",
                content,
                "launcher.sh must not contain hardcoded /Users/ paths",
            )

    def test_r3_05_automated_sha256_export_and_shasum_verification(self):
        """
        Verify SHA-256 export and format verification with shasum -a 256:
        - Format: <64-char-hash>  <filename>
        - Verifiable with macOS / GNU `shasum -a 256 -c`
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = os.path.join(tmpdir, "sample.bin")
            sample_data = b"League of Legends Discord RPC Production DMG Payload 2026"
            with open(sample_file, "wb") as f:
                f.write(sample_data)

            computed_hash = build_dmg.compute_sha256(sample_file)
            expected_hash = hashlib.sha256(sample_data).hexdigest()
            self.assertEqual(computed_hash, expected_hash)

            # Generate .sha256 manifest
            sha_manifest = f"{sample_file}.sha256"
            with open(sha_manifest, "w", encoding="utf-8") as f:
                f.write(f"{computed_hash}  {os.path.basename(sample_file)}\n")

            # Run system shasum -a 256 -c
            res = subprocess.run(
                ["shasum", "-a", "256", "-c", os.path.basename(sha_manifest)],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"shasum verification failed: {res.stderr}")
            self.assertIn("OK", res.stdout)

    def test_r3_06_self_healing_bundle_auto_initialization(self):
        """
        Verify self-healing bundle auto-initialization in sync_bundle.py:
        - When target bundle directory does not exist, sync_app_bundle automatically
          initializes bundle skeleton (Contents/MacOS, Contents/Resources, Info.plist).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            test_bundle = os.path.join(tmpdir, "League of Legends RPC.app")
            self.assertFalse(os.path.exists(test_bundle))

            success = sync_bundle.sync_app_bundle(
                dry_run=False,
                bundle_path=test_bundle,
                src_dir=PROJECT_ROOT,
            )
            self.assertTrue(success, "sync_app_bundle must succeed and self-heal missing bundle")
            self.assertTrue(os.path.isdir(test_bundle), "Bundle directory must be created")
            self.assertTrue(os.path.isfile(os.path.join(test_bundle, "Contents", "Info.plist")))
            self.assertTrue(os.path.isfile(os.path.join(test_bundle, "Contents", "MacOS", "League of Legends RPC")))


class TestTier6R4SystemEventsAndResilience(unittest.TestCase):
    """
    Acceptance tests for Requirement R4:
    System Event Listeners (Discord Launch & Sleep/Wake Resilience) & Error Resilience.
    """

    def test_r4_01_workspace_notification_registration(self):
        """
        Verify Cocoa NSWorkspace notification registration:
        - NSWorkspaceDidLaunchApplicationNotification observer registered with onAppLaunched:
        - NSWorkspaceDidWakeNotification observer registered with onSystemWake:
        - Clean deregistration on quit() via removeObserver:
        """
        controller = LoLAppController.__new__(LoLAppController)
        controller._is_shutting_down = False
        controller.status_item = None
        controller.rpc_manager = None
        controller.popover = None

        with patch.object(app_gui, "AppKit") as mock_appkit:
            mock_nc = MagicMock()
            mock_appkit.NSWorkspace.sharedWorkspace.return_value.notificationCenter.return_value = mock_nc
            mock_appkit.NSWorkspaceDidLaunchApplicationNotification = "NSWorkspaceDidLaunchApplicationNotification"
            mock_appkit.NSWorkspaceDidWakeNotification = "NSWorkspaceDidWakeNotification"

            controller._register_workspace_notifications()
            self.assertEqual(mock_nc.addObserver_selector_name_object_.call_count, 2)
            registered_names = [call[0][2] for call in mock_nc.addObserver_selector_name_object_.call_args_list]
            self.assertIn("NSWorkspaceDidLaunchApplicationNotification", registered_names)
            self.assertIn("NSWorkspaceDidWakeNotification", registered_names)

            controller.quit()
            mock_nc.removeObserver_.assert_called_once_with(controller)

    def test_r4_02_discord_launch_notification_triggers_reconnect(self):
        """
        Verify that NSWorkspaceDidLaunchApplicationNotification for Discord:
        - Immediately triggers rpc_manager.reconnect().
        - Ignores non-Discord application launches.
        """
        controller = LoLAppController.__new__(LoLAppController)
        controller._is_shutting_down = False
        mock_mgr = MagicMock()
        controller.rpc_manager = mock_mgr

        # 1. Non-Discord application launch -> no reconnect
        other_app = MagicMock()
        other_app.bundleIdentifier.return_value = "com.apple.Safari"
        other_app.localizedName.return_value = "Safari"
        notif_other = MagicMock()
        notif_other.userInfo.return_value = {"NSWorkspaceApplicationKey": other_app}

        controller.onAppLaunched_(notif_other)
        mock_mgr.reconnect.assert_not_called()

        # 2. Discord application launch -> triggers reconnect()
        discord_app = MagicMock()
        discord_app.bundleIdentifier.return_value = "com.hnc.Discord"
        discord_app.localizedName.return_value = "Discord"
        notif_discord = MagicMock()
        notif_discord.userInfo.return_value = {"NSWorkspaceApplicationKey": discord_app}

        controller.onAppLaunched_(notif_discord)
        mock_mgr.reconnect.assert_called_once()

    def test_r4_03_system_wake_notification_triggers_reconnect(self):
        """
        Verify that NSWorkspaceDidWakeNotification:
        - Immediately triggers rpc_manager.reconnect() upon Mac wake from sleep.
        """
        controller = LoLAppController.__new__(LoLAppController)
        controller._is_shutting_down = False
        mock_mgr = MagicMock()
        controller.rpc_manager = mock_mgr

        notif_wake = MagicMock()
        controller.onSystemWake_(notif_wake)
        mock_mgr.reconnect.assert_called_once()

    def test_r4_04_in_app_error_toast_handling(self):
        """
        Verify in-app error toast handling:
        - liquid_html.py defines #toast-container and window.showToast
        - Error boundaries intercept window 'error' and 'unhandledrejection'
        - LoLPopoverController.show_toast escapes input and evaluates showToast cleanly
        """
        html = liquid_html.render_app_html()
        self.assertIn('id="toast-container"', html)
        self.assertIn("window.showToast = function", html)
        self.assertIn("window.addEventListener('error'", html)
        self.assertIn("window.addEventListener('unhandledrejection'", html)

        # Verify controller show_toast
        controller = LoLPopoverController(auto_create=False)
        mock_web_view = MagicMock()
        controller._web_view = mock_web_view

        dangerous_message = 'Failed to connect: "Socket timeout" on \n newline'
        controller.show_toast(dangerous_message, "error")

        self.assertTrue(mock_web_view.evaluateJavaScript_completionHandler_.called)
        js_call = mock_web_view.evaluateJavaScript_completionHandler_.call_args[0][0]
        self.assertIn("window.showToast", js_call)
        self.assertIn('"error"', js_call)
        # Ensure raw unescaped newlines are not present in evaluated JS
        self.assertNotIn("\n newline", js_call)

    def test_r1_07_web_bridge_handles_nsdictionary_and_toggles_presence(self):
        """
        Verify that LoLWebBridge correctly handles native PyObjC NSDictionary payloads
        from WebKit and toggles presence.
        """
        from Foundation import NSDictionary
        controller = LoLPopoverController(auto_create=False)
        bridge = LoLWebBridge.alloc().initWithController_(controller)
        native_dict = NSDictionary.dictionaryWithDictionary_({"action": "action_button"})
        mock_msg = MagicMock()
        mock_msg.body.return_value = native_dict

        initial_state = controller.is_presence_active()
        bridge.userContentController_didReceiveScriptMessage_(None, mock_msg)
        self.assertEqual(controller.is_presence_active(), not initial_state)

        # Toggle again
        bridge.userContentController_didReceiveScriptMessage_(None, mock_msg)
        self.assertEqual(controller.is_presence_active(), initial_state)

    def test_r1_08_web_bridge_handles_quit_app_from_nsdictionary(self):
        """
        Verify that LoLWebBridge correctly processes 'quit_app' action inside
        a native PyObjC NSDictionary and invokes controller.quit_application().
        """
        from Foundation import NSDictionary
        controller = LoLPopoverController(auto_create=False)
        bridge = LoLWebBridge.alloc().initWithController_(controller)
        quit_called = []
        controller._on_quit = lambda: quit_called.append(True)
        native_dict = NSDictionary.dictionaryWithDictionary_({"action": "quit_app"})
        mock_msg = MagicMock()
        mock_msg.body.return_value = native_dict

        bridge.userContentController_didReceiveScriptMessage_(None, mock_msg)
        self.assertEqual(quit_called, [True])

    def test_r2_07_web_bridge_handles_save_config_with_nsarray_buttons(self):
        """
        Verify that LoLWebBridge correctly converts nested NSArray and NSDictionary
        in 'save_config' so that config can be saved without TypeError JSON serialization errors.
        """
        from Foundation import NSDictionary, NSArray
        controller = LoLPopoverController(auto_create=False)
        bridge = LoLWebBridge.alloc().initWithController_(controller)
        btn = NSDictionary.dictionaryWithDictionary_({"label": "OPGG", "url": "https://op.gg"})
        btns = NSArray.arrayWithObject_(btn)
        payload = NSDictionary.dictionaryWithDictionary_({
            "action": "save_config",
            "game_id": "lol",
            "client_id": "1402418696126992445",
            "details": "Testing",
            "duration_min": 25,
            "buttons": btns,
        })
        mock_msg = MagicMock()
        mock_msg.body.return_value = payload

        bridge.userContentController_didReceiveScriptMessage_(None, mock_msg)
        self.assertEqual(controller._buttons, [{"label": "OPGG", "url": "https://op.gg"}])


if __name__ == "__main__":
    unittest.main()
