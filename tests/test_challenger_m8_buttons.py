#!/usr/bin/env python3
"""
test_challenger_m8_buttons.py - Empirical Challenger Stress Test Suite for Milestone M8
Requirement R2: Discord Interactive Profile Buttons (Clickable Buttons)

Covers:
1. sanitize_buttons empirical stress testing:
   - Huge URL strings (>1000 chars, up to 10,000 chars) -> truncated to 512
   - Long labels (>100 chars, up to 1,000 chars, multi-byte Unicode) -> truncated to 32
   - Array of 10 buttons -> exactly at most 2 kept
   - Array of 10 buttons with interleaved invalid elements -> extracts first 2 valid
   - Non-list types, empty lists, None, integers, strings, floats, booleans, dicts -> returns None
   - Incomplete dicts (missing/empty label or url) -> discarded
   - HTTPS upgrades and scheme additions on boundary inputs
2. Payload verification for pypresence.update:
   - When 0 buttons (empty, None, or invalid): "buttons" key must not be present or must be None
   - When 2 buttons: "buttons" key must contain valid 2-item list
   - When >2 buttons: "buttons" key must contain truncated 2-item list
   - Verifies across "oficial", "detallado", and external game presets
3. Concurrency and actor queue integration:
   - Config change queue processing of buttons
   - Exception resilience during pypresence.update failure
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from discord_rpc_manager import (
    ALLOWED_CONFIG_KEYS,
    DiscordRPCManager,
    RPCState,
    sanitize_buttons,
)


class TestChallengerSanitizeButtons(unittest.TestCase):
    """Adversarial and boundary stress tests for sanitize_buttons."""

    def test_huge_url_strings_truncated_to_512(self):
        """Huge URL strings (>1000 chars, 2000 chars, 5000 chars) must be truncated to 512."""
        test_lengths = [1001, 1500, 2048, 5000, 10000]
        for length in test_lengths:
            huge_url = "https://example.com/" + ("x" * (length - 20))
            self.assertGreater(len(huge_url), 1000)
            raw = [{"label": "Huge URL", "url": huge_url}]
            res = sanitize_buttons(raw)

            self.assertIsNotNone(res, f"Failed for length {length}")
            self.assertEqual(len(res), 1)
            self.assertEqual(
                len(res[0]["url"]),
                512,
                f"URL with original length {length} was not truncated to 512 (got {len(res[0]['url'])})",
            )
            self.assertTrue(res[0]["url"].startswith("https://example.com/"))

    def test_huge_url_with_http_upgrade_truncated_to_512(self):
        """Huge HTTP URL must be upgraded to HTTPS and truncated to exactly 512 chars."""
        raw_url = "http://example.com/path?" + ("param=" + "a" * 100 + "&") * 10
        self.assertGreater(len(raw_url), 1000)
        res = sanitize_buttons([{"label": "Test", "url": raw_url}])
        self.assertIsNotNone(res)
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertTrue(res[0]["url"].startswith("https://example.com/path?"))

    def test_huge_url_missing_scheme_prefixed_and_truncated_to_512(self):
        """Huge URL with no scheme must be prefixed with https:// and truncated to 512."""
        raw_url = "mywebsite.org/profile/" + ("z" * 1500)
        res = sanitize_buttons([{"label": "NoScheme", "url": raw_url}])
        self.assertIsNotNone(res)
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertTrue(res[0]["url"].startswith("https://mywebsite.org/profile/"))

    def test_long_labels_truncated_to_32(self):
        """Long labels (>100 chars, up to 1000 chars) must be truncated to 32."""
        test_lengths = [101, 200, 500, 1000]
        for length in test_lengths:
            long_label = "L" * length
            self.assertGreater(len(long_label), 100)
            raw = [{"label": long_label, "url": "https://valid.com"}]
            res = sanitize_buttons(raw)

            self.assertIsNotNone(res)
            self.assertEqual(len(res), 1)
            self.assertEqual(
                len(res[0]["label"]),
                32,
                f"Label with original length {length} was not truncated to 32 (got {len(res[0]['label'])})",
            )
            self.assertEqual(res[0]["label"], "L" * 32)

    def test_long_labels_unicode_and_emojis_truncated_to_32(self):
        """Unicode strings and multi-byte characters are truncated to at most 32 characters."""
        unicode_label = "🔥🕹️🎮 Super Pro League Champion Extraordinaire" * 3
        raw = [{"label": unicode_label, "url": "https://op.gg"}]
        res = sanitize_buttons(raw)
        self.assertIsNotNone(res)
        self.assertLessEqual(len(res[0]["label"]), 32)
        self.assertEqual(res[0]["label"], unicode_label[:32])

    def test_array_of_10_buttons_keeps_at_most_2(self):
        """Array of 10 valid buttons must strictly keep only the first 2 buttons."""
        raw_10 = [{"label": f"Button {i}", "url": f"https://btn{i}.com"} for i in range(1, 11)]
        self.assertEqual(len(raw_10), 10)

        res = sanitize_buttons(raw_10)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2, f"Expected exactly 2 buttons, got {len(res)}")
        self.assertEqual(res[0]["label"], "Button 1")
        self.assertEqual(res[0]["url"], "https://btn1.com")
        self.assertEqual(res[1]["label"], "Button 2")
        self.assertEqual(res[1]["url"], "https://btn2.com")

    def test_array_of_10_buttons_with_interleaved_invalids(self):
        """Array of 10 buttons with invalid items must cleanly pick the first 2 valid ones."""
        raw_interleaved = [
            {"label": "", "url": "https://bad1.com"},          # Invalid (empty label)
            "not a dict",                                       # Invalid (string)
            None,                                              # Invalid (None)
            {"label": "Valid First", "url": "https://first.com"},# Valid #1
            {"url": "https://no-label.com"},                   # Invalid (missing label)
            {"label": "Valid Second", "url": "https://second.com"}, # Valid #2
            {"label": "Valid Third", "url": "https://third.com"},  # Valid but surplus
            {"label": "Valid Fourth", "url": "https://fourth.com"},# Valid but surplus
            12345,                                             # Invalid (int)
            {},                                                # Invalid (empty dict)
        ]
        self.assertEqual(len(raw_interleaved), 10)

        res = sanitize_buttons(raw_interleaved)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "Valid First")
        self.assertEqual(res[0]["url"], "https://first.com")
        self.assertEqual(res[1]["label"], "Valid Second")
        self.assertEqual(res[1]["url"], "https://second.com")

    def test_array_of_10_invalid_buttons_returns_none(self):
        """Array of 10 buttons where all are invalid returns None."""
        raw_invalids = [
            {"label": "", "url": ""},
            {"label": "   ", "url": "   "},
            {"label": None, "url": None},
            {},
            [],
            "string",
            12345,
            {"label": "Only Label"},
            {"url": "https://only-url.com"},
            {"label": "   ", "url": "https://valid-url.com"},
        ]
        self.assertEqual(len(raw_invalids), 10)
        res = sanitize_buttons(raw_invalids)
        self.assertIsNone(res)

    def test_non_list_and_empty_types_return_none(self):
        """Empty lists, None, integers, strings, floats, booleans, dicts must return None."""
        bad_inputs = [
            [],
            (),
            None,
            12345,
            0,
            -1,
            3.14159,
            "https://discord.com",
            "",
            "   ",
            True,
            False,
            {"label": "Btn", "url": "https://btn.com"}, # dict instead of list
            set(),
            object(),
        ]
        for val in bad_inputs:
            res = sanitize_buttons(val)
            self.assertIsNone(
                res,
                f"sanitize_buttons({val!r}) did not return None, got {res!r}",
            )


class TestChallengerRPCManagerPayload(unittest.TestCase):
    """Empirical verification of the payload passed to pypresence.update."""

    def setUp(self):
        self.mgr = DiscordRPCManager(client_id="challenger_test", auto_start=False, load_config=False)
        self.mock_rpc = MagicMock()
        self.mgr._rpc = self.mock_rpc
        self.mgr.is_active = True

    def test_payload_when_zero_buttons_oficial_mode(self):
        """When 0 buttons (empty or None), 'buttons' key must NOT be present in kwargs (oficial mode)."""
        for zero_input in [[], None, [{"label": "", "url": ""}], "invalid"]:
            self.mock_rpc.reset_mock()
            self.mgr.mode = "oficial"
            self.mgr.buttons = zero_input

            self.mgr._send_rpc_update()
            self.assertTrue(self.mock_rpc.update.called, "rpc.update was not called")
            _, kwargs = self.mock_rpc.update.call_args
            self.assertNotIn(
                "buttons",
                kwargs,
                f"Failed for input {zero_input!r}: 'buttons' key should not be in kwargs",
            )

    def test_payload_when_zero_buttons_detallado_mode(self):
        """When 0 buttons (empty or None), 'buttons' key must NOT be present in kwargs (detallado mode)."""
        for zero_input in [[], None, [{"label": "", "url": ""}]]:
            self.mock_rpc.reset_mock()
            self.mgr.mode = "detallado"
            self.mgr.buttons = zero_input
            self.mgr.champion_name = "Yasuo"

            self.mgr._send_rpc_update()
            self.assertTrue(self.mock_rpc.update.called)
            _, kwargs = self.mock_rpc.update.call_args
            self.assertNotIn("buttons", kwargs)

    def test_payload_when_zero_buttons_other_game_mode(self):
        """When 0 buttons (empty or None), 'buttons' key must NOT be present in other game presets."""
        self.mock_rpc.reset_mock()
        self.mgr.selected_game_id = "valorant"
        self.mgr.buttons = []

        self.mgr._send_rpc_update()
        self.assertTrue(self.mock_rpc.update.called)
        _, kwargs = self.mock_rpc.update.call_args
        self.assertNotIn("buttons", kwargs)

    def test_payload_when_two_buttons_oficial_mode(self):
        """When 2 buttons, 'buttons' key must contain a valid 2-item list in oficial mode."""
        valid_buttons = [
            {"label": "OP.GG Profile", "url": "https://op.gg/summoners/lan/Challenger"},
            {"label": "Twitch Stream", "url": "https://twitch.tv/challenger_stream"},
        ]
        self.mgr.mode = "oficial"
        self.mgr.buttons = valid_buttons

        self.mgr._send_rpc_update()
        self.assertTrue(self.mock_rpc.update.called)
        _, kwargs = self.mock_rpc.update.call_args

        self.assertIn("buttons", kwargs)
        buttons_payload = kwargs["buttons"]
        self.assertIsInstance(buttons_payload, list)
        self.assertEqual(len(buttons_payload), 2)
        self.assertEqual(buttons_payload[0]["label"], "OP.GG Profile")
        self.assertEqual(buttons_payload[0]["url"], "https://op.gg/summoners/lan/Challenger")
        self.assertEqual(buttons_payload[1]["label"], "Twitch Stream")
        self.assertEqual(buttons_payload[1]["url"], "https://twitch.tv/challenger_stream")

    def test_payload_when_two_buttons_detallado_mode(self):
        """When 2 buttons, 'buttons' key must contain a valid 2-item list in detallado mode."""
        valid_buttons = [
            {"label": "Leaderboard", "url": "http://leaderboard.com"}, # http will be upgraded to https
            {"label": "Discord Server", "url": "discord.gg/invite"},   # scheme will be added
        ]
        self.mgr.mode = "detallado"
        self.mgr.champion_name = "Zed"
        self.mgr.buttons = valid_buttons

        self.mgr._send_rpc_update()
        self.assertTrue(self.mock_rpc.update.called)
        _, kwargs = self.mock_rpc.update.call_args

        self.assertIn("buttons", kwargs)
        buttons_payload = kwargs["buttons"]
        self.assertEqual(len(buttons_payload), 2)
        self.assertEqual(buttons_payload[0]["url"], "https://leaderboard.com")
        self.assertEqual(buttons_payload[1]["url"], "https://discord.gg/invite")

    def test_payload_when_ten_buttons_provided(self):
        """When 10 buttons provided, payload sent to rpc.update is strictly capped at 2 buttons."""
        ten_buttons = [{"label": f"B{i}", "url": f"https://b{i}.org"} for i in range(10)]
        self.mgr.mode = "oficial"
        self.mgr.buttons = ten_buttons

        self.mgr._send_rpc_update()
        self.assertTrue(self.mock_rpc.update.called)
        _, kwargs = self.mock_rpc.update.call_args

        self.assertIn("buttons", kwargs)
        self.assertEqual(len(kwargs["buttons"]), 2)
        self.assertEqual(kwargs["buttons"][0]["label"], "B0")
        self.assertEqual(kwargs["buttons"][1]["label"], "B1")

    def test_update_presence_config_queue_processes_buttons(self):
        """Verifies buttons are updated via thread-safe _process_command queue."""
        new_buttons = [{"label": "Queued Btn", "url": "https://queued.com"}]
        self.mgr._process_command("CONFIG_CHANGE", {"buttons": new_buttons})
        self.assertEqual(self.mgr.buttons, new_buttons)

    def test_send_rpc_update_catches_pypresence_exceptions_gracefully(self):
        """If rpc.update raises an exception, manager handles it without re-raising."""
        self.mock_rpc.update.side_effect = BrokenPipeError("Discord socket closed")
        self.mgr.mode = "oficial"
        self.mgr.buttons = [{"label": "Crash Test", "url": "https://crash.com"}]

        # Must not raise
        try:
            self.mgr._send_rpc_update()
        except Exception as e:
            self.fail(f"_send_rpc_update raised unexpected exception: {e}")

        # Manager should have called safe close and notified state
        self.assertIsNone(self.mgr._rpc)


if __name__ == "__main__":
    unittest.main()
