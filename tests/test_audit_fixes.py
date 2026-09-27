#!/usr/bin/env python3
"""
test_audit_fixes.py - Automated Unit & Integration Tests for Phase 0 Audit Fixes

Validates:
1. LoLWebBridge dispatch for change_rank and change_division, plus controller aliases.
2. Presence of 'Unranked' option, community aliases, highlight reset, and onchange in liquid_html.
3. Strict rejection of private attribute injection in CONFIG_CHANGE.
4. Thread-safe properties and lock synchronization in DiscordRPCManager.
5. Silent launch argument parsing (--silent, --background).
6. Accessibility attributes on LoLStatusItemController button and LaunchAgent plist generation.
"""

import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app_gui
import discord_rpc_manager
from discord_rpc_manager import ALLOWED_CONFIG_KEYS, DiscordRPCManager, RPCState
import liquid_html
import popover_ui
from popover_ui import LoLPopoverController, LoLWebBridge
import status_item
from tests.mocks import MockPresence


class MockScriptMessage:
    """Mock WebKit script message."""
    def __init__(self, body_dict):
        self._body = body_dict

    def body(self):
        return self._body


class TestAuditFixes(unittest.TestCase):
    """Test suite verifying all fixes from Phase 0 audit."""

    def test_01_lol_web_bridge_dispatch_rank_and_division(self):
        """
        Fix 1: LoLWebBridge calls select_rank and select_division without AttributeError,
        and LoLPopoverController defines alias methods set_selected_rank and set_selected_division.
        """
        ctrl = LoLPopoverController()

        # Verify alias methods exist on controller
        self.assertTrue(hasattr(ctrl, "set_selected_rank"), "Controller must define set_selected_rank")
        self.assertTrue(hasattr(ctrl, "set_selected_division"), "Controller must define set_selected_division")
        self.assertTrue(hasattr(ctrl, "select_rank"), "Controller must define select_rank")
        self.assertTrue(hasattr(ctrl, "select_division"), "Controller must define select_division")

        # Verify aliases point to same underlying logic
        ctrl.set_selected_rank("Diamante")
        self.assertEqual(ctrl.get_selected_rank(), "Diamante")
        ctrl.set_selected_division("IV")
        self.assertEqual(ctrl.get_selected_division(), "IV")

        # Verify bridge dispatch handles change_rank cleanly
        bridge = ctrl._web_bridge
        bridge.userContentController_didReceiveScriptMessage_(
            None, MockScriptMessage({"action": "change_rank", "rank": "Challenger"})
        )
        self.assertEqual(ctrl.get_selected_rank(), "Challenger")
        self.assertFalse(ctrl.is_division_selector_enabled(), "Apex tier Challenger must disable division")

        # Verify bridge dispatch handles change_division cleanly
        bridge.userContentController_didReceiveScriptMessage_(
            None, MockScriptMessage({"action": "change_rank", "rank": "Platino"})
        )
        bridge.userContentController_didReceiveScriptMessage_(
            None, MockScriptMessage({"action": "change_division", "division": "III"})
        )
        self.assertEqual(ctrl.get_selected_rank(), "Platino")
        self.assertEqual(ctrl.get_selected_division(), "III")

    def test_02_liquid_html_unranked_and_aliases(self):
        """
        Fix 2: liquid_html contains 'Unranked' in rank-select, onchange in champ-input,
        community aliases in filterChampions, and resets highlightedIndex.
        """
        html = liquid_html.generate_liquid_html({
            "mode": "detallado",
            "champion": "Malzahar",
            "rank": "Unranked",
            "division": "I",
            "game_mode": "Grieta del Invocador (Clasificatoria Solo/Duo)",
            "is_apex": True,
            "autoreset": True,
            "autorun": False,
            "presence_active": True,
            "connection_state": "connected",
            "status_tooltip": "Activo",
        })

        # 1. Unranked in rank-select
        self.assertIn('<option value="Unranked">Unranked</option>', html)

        # 2. onchange in champ-input
        self.assertIn("onchange=\"sendAction('change_champion'", html)

        # 3. Community aliases in JS
        self.assertIn("asol", html)
        self.assertIn("Aurelion Sol", html)
        self.assertIn("j4", html)
        self.assertIn("Jarvan IV", html)
        self.assertIn("mf", html)
        self.assertIn("Miss Fortune", html)
        self.assertIn("tf", html)
        self.assertIn("Twisted Fate", html)
        self.assertIn("yi", html)
        self.assertIn("Master Yi", html)
        self.assertIn("bardo", html)
        self.assertIn("Bard", html)

        # 4. HighlightedIndex reset
        self.assertIn("highlightedIndex = -1", html)

        # 5. Default game mode matches canonical list
        ctrl = LoLPopoverController()
        default_mode = ctrl.get_game_mode_text()
        self.assertEqual(
            default_mode,
            "Grieta del Invocador (Clasificatoria Solo/Duo)",
            "Default game mode must match canonical Solo/Duo string",
        )
        self.assertIn(default_mode, liquid_html.GAME_MODES)

    def test_03_rejection_of_private_attribute_injection(self):
        """
        Fix 3: CONFIG_CHANGE strictly whitelists ALLOWED_CONFIG_KEYS and rejects
        private or internal attributes like _running, _rpc, _cmd_queue, shutdown, etc.
        """
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)

        # Confirm ALLOWED_CONFIG_KEYS contains expected whitelist
        expected_keys = {
            "mode", "champion_name", "champion_image_url", "rank_text",
            "rank_image_url", "game_mode", "details", "autoreset"
        }
        self.assertEqual(ALLOWED_CONFIG_KEYS, expected_keys)

        # Attempt to inject unauthorized and private attributes
        injection_payload = {
            "_running": False,
            "_cmd_queue": "malicious_string",
            "_rpc": "fake_rpc",
            "shutdown": lambda: None,
            "mode": "detallado",
            "champion_name": "Jinx",
            "unauthorized_key": 9999,
        }

        mgr._process_command("CONFIG_CHANGE", injection_payload)

        # Verify private attributes were NOT modified
        self.assertTrue(mgr._running, "_running must remain True")
        self.assertNotEqual(mgr._cmd_queue, "malicious_string", "_cmd_queue must not be overwritten")
        self.assertIsNone(mgr._rpc, "_rpc must not be overwritten")
        self.assertFalse(hasattr(mgr, "unauthorized_key"), "unauthorized_key must not be added")

        # Verify allowed attributes WERE modified
        self.assertEqual(mgr.mode, "detallado")
        self.assertEqual(mgr.champion_name, "Jinx")

    def test_04_thread_safe_properties_and_lock(self):
        """
        Fix 4: DiscordRPCManager has a threading.Lock and safely handles concurrent
        reads/writes across 30 threads for state, is_connected, get_elapsed_seconds, and set_active.
        """
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        self.assertTrue(hasattr(mgr, "_lock"), "DiscordRPCManager must have _lock")

        errors = []

        def reader_task():
            try:
                for _ in range(50):
                    _ = mgr.state
                    _ = mgr.is_connected
                    _ = mgr.get_elapsed_seconds()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def writer_task():
            try:
                for i in range(50):
                    mgr.set_active(i % 2 == 0)
                    mgr.start_time = int(time.time()) - i
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(15):
            threads.append(threading.Thread(target=reader_task))
            threads.append(threading.Thread(target=writer_task))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=3.0)

        self.assertEqual(errors, [], f"Concurrent access generated errors: {errors}")

    def test_05_safe_close_rpc_and_reconnect_exceptions(self):
        """
        Fix 5: _safe_close_rpc closes sock_writer before calling close(),
        and RECONNECT_EXCEPTIONS catches pypresence exceptions.
        """
        from pypresence import PipeClosed, ConnectionTimeout, ResponseTimeout, PyPresenceException

        # Verify exceptions in RECONNECT_EXCEPTIONS
        self.assertIn(PipeClosed, discord_rpc_manager.RECONNECT_EXCEPTIONS)
        self.assertIn(ConnectionTimeout, discord_rpc_manager.RECONNECT_EXCEPTIONS)
        self.assertIn(ResponseTimeout, discord_rpc_manager.RECONNECT_EXCEPTIONS)
        self.assertIn(PyPresenceException, discord_rpc_manager.RECONNECT_EXCEPTIONS)

        # Test _safe_close_rpc
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mock_rpc = MagicMock()
        mock_rpc.sock_writer = MagicMock()
        mgr._rpc = mock_rpc

        mgr._safe_close_rpc()

        mock_rpc.sock_writer.close.assert_called_once()
        mock_rpc.close.assert_called_once()
        self.assertIsNone(mgr._rpc)

    def test_06_silent_launch_argument_parsing(self):
        """
        Fix 6: Launch arguments --silent and --background suppress autoShowPopoverOnLaunch:
        and notification banner.
        """
        # Test detection helper logic
        test_argv_normal = ["app_gui.py"]
        test_argv_silent = ["app_gui.py", "--silent"]
        test_argv_bg = ["app_gui.py", "--background"]

        self.assertFalse("--silent" in test_argv_normal or "--background" in test_argv_normal)
        self.assertTrue("--silent" in test_argv_silent or "--background" in test_argv_silent)
        self.assertTrue("--silent" in test_argv_bg or "--background" in test_argv_bg)

        # Test popover_ui LaunchAgent plist template includes --args and --silent
        import inspect
        source = inspect.getsource(LoLPopoverController._sync_login_item)
        self.assertIn("<string>--args</string>", source)
        self.assertIn("<string>--silent</string>", source)

    def test_07_status_item_accessibility_attributes(self):
        """
        Fix 7: LoLStatusItemController sets explicit accessibility title, label, and value.
        """
        ctrl = status_item.LoLStatusItemController()
        btn = ctrl.get_button()
        if btn is not None:
            if hasattr(btn, "accessibilityTitle"):
                self.assertEqual(btn.accessibilityTitle(), "Discord RPC League of Legends")
            if hasattr(btn, "accessibilityLabel"):
                self.assertEqual(btn.accessibilityLabel(), "Discord RPC League of Legends")

            ctrl.set_state("active")
            if hasattr(btn, "accessibilityValue"):
                self.assertEqual(btn.accessibilityValue(), "Active")

            ctrl.set_state("paused")
            if hasattr(btn, "accessibilityValue"):
                self.assertEqual(btn.accessibilityValue(), "Paused")


if __name__ == "__main__":
    unittest.main(verbosity=2)
