#!/usr/bin/env python3
"""
test_milestone8_buttons.py - Comprehensive Unit & Integration Tests for Milestone M8
Requirement R2: Discord Interactive Profile Buttons (Clickable Buttons)

Tests:
1. sanitize_buttons helper function (validation, sanitization, truncation, HTTPS enforcement, discarding).
2. ALLOWED_CONFIG_KEYS configuration whitelist integrity.
3. DiscordRPCManager buttons state initialization, command queue dispatch, and presence updates.
4. LoLPopoverController buttons storage, config.json persistence, and WebBridge integration.
5. liquid_html Web UI structure, CSS styling, inputs, and JavaScript sanitization.
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import discord_rpc_manager
from discord_rpc_manager import (
    ALLOWED_CONFIG_KEYS,
    DiscordRPCManager,
    RPCState,
    sanitize_buttons,
)
import popover_ui
import liquid_html


class TestSanitizeButtons(unittest.TestCase):
    """Verifies sanitize_buttons validation, sanitization, length rules, and HTTPS enforcement."""

    def test_valid_single_button(self):
        """Single valid button with HTTPS remains intact."""
        raw = [{"label": "Ver Perfil", "url": "https://op.gg/summoners/lan/Player-LAN"}]
        res = sanitize_buttons(raw)
        self.assertEqual(res, [{"label": "Ver Perfil", "url": "https://op.gg/summoners/lan/Player-LAN"}])

    def test_valid_two_buttons(self):
        """Two valid buttons remain intact."""
        raw = [
            {"label": "OP.GG", "url": "https://op.gg"},
            {"label": "Twitch Stream", "url": "https://twitch.tv/streamer"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "OP.GG")
        self.assertEqual(res[1]["label"], "Twitch Stream")

    def test_maximum_two_buttons_enforced(self):
        """More than 2 buttons are truncated to exactly 2 buttons."""
        raw = [
            {"label": "Button 1", "url": "https://one.com"},
            {"label": "Button 2", "url": "https://two.com"},
            {"label": "Button 3", "url": "https://three.com"},
            {"label": "Button 4", "url": "https://four.com"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "Button 1")
        self.assertEqual(res[1]["label"], "Button 2")

    def test_label_truncation_to_32_chars(self):
        """Labels exceeding 32 characters are truncated to exactly 32."""
        long_label = "A" * 60
        raw = [{"label": long_label, "url": "https://example.com"}]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res[0]["label"]), 32)
        self.assertEqual(res[0]["label"], "A" * 32)

    def test_url_truncation_to_512_chars(self):
        """URLs exceeding 512 characters are truncated to exactly 512."""
        long_url = "https://example.com/" + ("b" * 600)
        raw = [{"label": "My Profile", "url": long_url}]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertTrue(res[0]["url"].startswith("https://example.com/"))

    def test_https_upgrade_from_http(self):
        """URLs using http:// are upgraded to https://."""
        raw = [{"label": "Insecure Link", "url": "http://op.gg/summoners"}]
        res = sanitize_buttons(raw)
        self.assertEqual(res[0]["url"], "https://op.gg/summoners")

    def test_https_prefix_for_missing_scheme(self):
        """URLs without a scheme (e.g. op.gg) are prefixed with https://."""
        raw = [
            {"label": "OP.GG", "url": "op.gg/summoners"},
            {"label": "Discord", "url": "discord.gg/community"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(res[0]["url"], "https://op.gg/summoners")
        self.assertEqual(res[1]["url"], "https://discord.gg/community")

    def test_drop_incomplete_missing_url(self):
        """Buttons missing URL or with empty URL are discarded."""
        raw = [
            {"label": "Empty URL", "url": ""},
            {"label": "Whitespace URL", "url": "   "},
            {"label": "Valid Button", "url": "https://valid.com"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["label"], "Valid Button")

    def test_drop_incomplete_missing_label(self):
        """Buttons missing label or with empty label are discarded."""
        raw = [
            {"label": "", "url": "https://test.com"},
            {"label": "   ", "url": "https://test.com"},
            {"label": "Valid Button", "url": "https://valid.com"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["label"], "Valid Button")

    def test_drop_non_dict_items(self):
        """Non-dictionary items in list are cleanly skipped without exception."""
        raw = [
            "invalid_string",
            12345,
            None,
            {"label": "Good Button", "url": "https://good.com"},
        ]
        res = sanitize_buttons(raw)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["label"], "Good Button")

    def test_returns_none_when_empty_or_all_invalid(self):
        """Returns None if list is empty or all items are invalid/discarded."""
        self.assertIsNone(sanitize_buttons(None))
        self.assertIsNone(sanitize_buttons([]))
        self.assertIsNone(sanitize_buttons([{}]))
        self.assertIsNone(sanitize_buttons([{"label": "", "url": ""}]))
        self.assertIsNone(sanitize_buttons([{"label": "A"}]))
        self.assertIsNone(sanitize_buttons([{"url": "https://example.com"}]))
        self.assertIsNone(sanitize_buttons("not-a-list"))
        self.assertIsNone(sanitize_buttons(12345))


class TestDiscordRPCManagerButtons(unittest.TestCase):
    """Verifies DiscordRPCManager handles buttons configuration and payload updates."""

    def test_buttons_in_allowed_config_keys(self):
        """Confirms 'buttons' is whitelisted in ALLOWED_CONFIG_KEYS."""
        self.assertIn("buttons", ALLOWED_CONFIG_KEYS)

    def test_rpc_manager_initializes_buttons_default(self):
        """Confirms buttons attribute defaults to empty list."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False, load_config=False)
        self.assertTrue(hasattr(mgr, "buttons"))
        self.assertEqual(mgr.buttons, [])

    def test_rpc_manager_loads_buttons_from_saved_config(self):
        """Confirms buttons are loaded from ~/.config/lol_discord_rpc/config.json when load_config=True."""
        saved_buttons = [{"label": "Saved OP.GG", "url": "https://op.gg"}]
        with patch("discord_rpc_manager.load_user_config", return_value={"buttons": saved_buttons}):
            mgr = DiscordRPCManager(client_id="test_client", auto_start=False, load_config=True)
            self.assertEqual(mgr.buttons, saved_buttons)

    def test_update_presence_config_updates_buttons(self):
        """Confirms update_presence_config updates self.buttons via worker command processing."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        new_buttons = [{"label": "Twitch", "url": "https://twitch.tv"}]
        mgr._process_command("CONFIG_CHANGE", {"buttons": new_buttons})
        self.assertEqual(mgr.buttons, new_buttons)

    def test_private_attribute_injection_still_prevented(self):
        """Ensures adding 'buttons' does not open private attribute injection vulnerabilities."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mgr._process_command(
            "CONFIG_CHANGE",
            {
                "_running": False,
                "_cmd_queue": "hacked",
                "buttons": [{"label": "Valid", "url": "https://valid.com"}],
            },
        )
        self.assertTrue(mgr._running)
        self.assertNotEqual(mgr._cmd_queue, "hacked")
        self.assertEqual(len(mgr.buttons), 1)

    def test_send_rpc_update_omits_buttons_when_empty(self):
        """rpc.update() is called without 'buttons' keyword argument when buttons is empty."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.mode = "oficial"
        mgr.buttons = []

        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        _, kwargs = mock_rpc.update.call_args
        self.assertNotIn("buttons", kwargs)

    def test_send_rpc_update_includes_buttons_when_valid_official_mode(self):
        """rpc.update() is called with 'buttons' keyword argument in official mode."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.mode = "oficial"
        mgr.buttons = [{"label": "My Profile", "url": "http://op.gg"}]

        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        _, kwargs = mock_rpc.update.call_args
        self.assertIn("buttons", kwargs)
        self.assertEqual(kwargs["buttons"], [{"label": "My Profile", "url": "https://op.gg"}])

    def test_send_rpc_update_includes_buttons_when_valid_detailed_mode(self):
        """rpc.update() is called with 'buttons' keyword argument in detailed mode."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.mode = "detallado"
        mgr.champion_name = "Ahri"
        mgr.buttons = [
            {"label": "OP.GG", "url": "https://op.gg"},
            {"label": "Discord", "url": "https://discord.gg"},
        ]

        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        _, kwargs = mock_rpc.update.call_args
        self.assertIn("buttons", kwargs)
        self.assertEqual(len(kwargs["buttons"]), 2)

    def test_send_rpc_update_includes_buttons_in_other_game_presets(self):
        """rpc.update() passes buttons for non-LoL game presets (e.g. valorant)."""
        mgr = DiscordRPCManager(client_id="test_client", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.selected_game_id = "valorant"
        mgr.buttons = [{"label": "Tracker", "url": "https://tracker.gg"}]

        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        _, kwargs = mock_rpc.update.call_args
        self.assertIn("buttons", kwargs)
        self.assertEqual(kwargs["buttons"], [{"label": "Tracker", "url": "https://tracker.gg"}])


class TestPopoverUIButtons(unittest.TestCase):
    """Verifies LoLPopoverController button state management, persistence, and bridge interaction."""

    def test_popover_controller_initializes_buttons(self):
        """LoLPopoverController has self._buttons initialized."""
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        self.assertTrue(hasattr(ctrl, "_buttons"))
        self.assertIsInstance(ctrl._buttons, list)

    def test_apply_config_persists_buttons(self):
        """apply_config saves buttons array in config dictionary and saves to config.json."""
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        saved_dict = {}

        def mock_save(cfg):
            nonlocal saved_dict
            saved_dict = cfg

        test_buttons = [
            {"label": "Button 1", "url": "https://b1.com"},
            {"label": "Button 2", "url": "https://b2.com"},
        ]

        with patch("popover_ui.save_user_config", side_effect=mock_save):
            ctrl.apply_config(
                game_id="lol",
                client_id="123456789",
                details="Test Details",
                duration_min=30,
                buttons=test_buttons,
            )

        self.assertEqual(ctrl._buttons, test_buttons)
        self.assertIn("buttons", saved_dict)
        self.assertEqual(saved_dict["buttons"], test_buttons)

    def test_apply_config_forwards_buttons_to_rpc_manager(self):
        """apply_config forwards buttons to rpc_manager.update_presence_config."""
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        mock_mgr = MagicMock()
        ctrl._rpc_manager = mock_mgr

        test_buttons = [{"label": "OP.GG", "url": "https://op.gg"}]
        ctrl.apply_config(
            game_id="lol",
            client_id="123456789",
            details="Test Details",
            buttons=test_buttons,
        )

        mock_mgr.update_presence_config.assert_called_with(buttons=test_buttons)

    def test_web_bridge_save_config_passes_buttons(self):
        """LoLWebBridge userContentController_didReceiveScriptMessage_ passes buttons to apply_config."""
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        ctrl.apply_config = MagicMock()
        bridge = popover_ui.LoLWebBridge.alloc().initWithController_(ctrl)

        msg = MagicMock()
        test_buttons = [{"label": "Bridge Btn", "url": "https://bridge.com"}]
        msg.body.return_value = {
            "action": "save_config",
            "game_id": "lol",
            "client_id": "111222333",
            "details": "Playing",
            "duration_min": 20,
            "buttons": test_buttons,
        }

        bridge.userContentController_didReceiveScriptMessage_(None, msg)
        ctrl.apply_config.assert_called_once_with(
            game_id="lol",
            client_id="111222333",
            details="Playing",
            duration_min=20,
            buttons=test_buttons,
        )


class TestLiquidHTMLButtons(unittest.TestCase):
    """Verifies that liquid_html contains interactive buttons UI, CSS, and JS logic."""

    def setUp(self):
        self.html = liquid_html.generate_liquid_html(
            {
                "buttons": [
                    {"label": "Btn 1 Label", "url": "https://btn1.com"},
                    {"label": "Btn 2 Label", "url": "https://btn2.com"},
                ]
            }
        )

    def test_html_contains_button_input_elements(self):
        """HTML output contains input elements for Button 1 and Button 2."""
        self.assertIn('id="config-btn1-label"', self.html)
        self.assertIn('id="config-btn1-url"', self.html)
        self.assertIn('id="config-btn2-label"', self.html)
        self.assertIn('id="config-btn2-url"', self.html)

    def test_html_contains_css_classes(self):
        """HTML output contains the expected CSS classes for the buttons section."""
        self.assertIn(".buttons-config-group", self.html)
        self.assertIn(".btn-config-card", self.html)
        self.assertIn(".btn-fields-grid", self.html)
        self.assertIn("overflow-y: auto", self.html)

    def test_javascript_contains_sanitization_and_state_sync(self):
        """JavaScript includes sanitizeBtn, saveConfig button packaging, and updateLiquidUI population."""
        self.assertIn("function sanitizeBtn", self.html)
        self.assertIn("config-btn1-label", self.html)
        self.assertIn("config-btn2-label", self.html)
        self.assertIn("currentState.buttons", self.html)


if __name__ == "__main__":
    unittest.main()
