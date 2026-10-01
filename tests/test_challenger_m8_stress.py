#!/usr/bin/env python3
"""
tests/test_challenger_m8_stress.py - Empirical Challenger Stress Harness for Milestone M8
Author: challenger_m8_2
Role: Empirical Challenger & Critic

Comprehensive stress tests, edge cases, hostile payloads, and concurrency tests for
Requirement R2: Discord Interactive Profile Buttons & Persistence.
"""

import os
import sys
import json
import time
import shutil
import unittest
import threading
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import discord_rpc_manager
from discord_rpc_manager import (
    ALLOWED_CONFIG_KEYS,
    CONFIG_FILE,
    DiscordRPCManager,
    RPCState,
    load_user_config,
    save_user_config,
    sanitize_buttons,
)
import popover_ui
import liquid_html


class TestSanitizeButtonsAdversarial(unittest.TestCase):
    """Stress tests and boundary condition exploration for sanitize_buttons."""

    def test_null_and_primitive_inputs(self):
        """Passing non-collection primitives returns None cleanly."""
        for bad_input in [None, 0, 1, -1, True, False, 3.14, object(), b"raw bytes"]:
            self.assertIsNone(sanitize_buttons(bad_input), f"Failed for {type(bad_input)}")

    def test_empty_and_whitespace_collections(self):
        """Empty collections or whitespace-only values return None cleanly."""
        self.assertIsNone(sanitize_buttons([]))
        self.assertIsNone(sanitize_buttons(()))
        self.assertIsNone(sanitize_buttons([{}]))
        self.assertIsNone(sanitize_buttons([{"label": "", "url": ""}]))
        self.assertIsNone(sanitize_buttons([{"label": "   ", "url": "   "}]))
        self.assertIsNone(sanitize_buttons([{"label": "\t\n\r", "url": " \n "}]))

    def test_hostile_heterogeneous_elements(self):
        """Lists containing non-dict items are safely processed without raising exceptions."""
        hostile_list = [
            None,
            123,
            "string_item",
            ["nested", "list"],
            {"only_label": "no_url"},
            {"label": None, "url": "https://valid.com"},
            {"label": "Valid 1", "url": None},
            {"label": "Valid Button", "url": "op.gg/valid"},
            {"malformed": True},
        ]
        res = sanitize_buttons(hostile_list)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["label"], "Valid Button")
        self.assertEqual(res[0]["url"], "https://op.gg/valid")

    def test_massive_payload_truncation(self):
        """Massive inputs (100KB strings) are truncated without memory or CPU exhaustion."""
        giant_label = "L" * 100_000
        giant_url = "https://example.com/" + ("u" * 100_000)
        res = sanitize_buttons([{"label": giant_label, "url": giant_url}])
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)
        self.assertEqual(len(res[0]["label"]), 32)
        self.assertEqual(res[0]["label"], "L" * 32)
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertTrue(res[0]["url"].startswith("https://example.com/"))

    def test_unicode_and_emojis(self):
        """UTF-8 unicode, accents, and emojis in button labels and URLs are preserved."""
        raw = [
            {"label": "🎮 Stream En Vivo", "url": "https://twitch.tv/jugador_es"},
            {"label": "🏆 Perfil de Clasificatoria", "url": "https://op.gg/summoners/lan/Águila-LAN"},
        ]
        res = sanitize_buttons(raw)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "🎮 Stream En Vivo")
        self.assertEqual(res[0]["url"], "https://twitch.tv/jugador_es")
        self.assertEqual(res[1]["label"], "🏆 Perfil de Clasificatoria")
        self.assertEqual(res[1]["url"], "https://op.gg/summoners/lan/Águila-LAN")

    def test_scheme_variations(self):
        """Various URL protocols and formats are normalized to HTTPS."""
        # http upgraded to https
        r1 = sanitize_buttons([{"label": "Link", "url": "http://op.gg"}])
        self.assertEqual(r1[0]["url"], "https://op.gg")

        # already https preserved
        r2 = sanitize_buttons([{"label": "Link", "url": "https://op.gg"}])
        self.assertEqual(r2[0]["url"], "https://op.gg")

        # no scheme prefixed
        r3 = sanitize_buttons([{"label": "Link", "url": "discord.gg/invite"}])
        self.assertEqual(r3[0]["url"], "https://discord.gg/invite")

        # non-standard scheme prefixed to prevent protocol smuggling
        r4 = sanitize_buttons([{"label": "Link", "url": "javascript:alert(1)"}])
        self.assertEqual(r4[0]["url"], "https://javascript:alert(1)")

    def test_extra_dictionary_attributes_stripped(self):
        """Extraneous attributes injected into button dicts are strictly stripped."""
        raw = [
            {
                "label": "Button A",
                "url": "https://a.com",
                "malicious_key": "payload",
                "__proto__": "polluted",
            }
        ]
        res = sanitize_buttons(raw)
        self.assertIsNotNone(res)
        self.assertEqual(set(res[0].keys()), {"label", "url"})

    def test_max_two_buttons_with_subsequent_invalids(self):
        """Extracts up to 2 valid buttons even if interspersed with invalid buttons."""
        raw = [
            {"label": "", "url": "https://empty.com"},
            {"label": "First Valid", "url": "https://first.com"},
            {"invalid": "item"},
            {"label": "Second Valid", "url": "https://second.com"},
            {"label": "Third Valid (ignored)", "url": "https://third.com"},
        ]
        res = sanitize_buttons(raw)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "First Valid")
        self.assertEqual(res[1]["label"], "Second Valid")


class TestDiscordRPCManagerStress(unittest.TestCase):
    """Stress and concurrency tests for DiscordRPCManager buttons integration."""

    def test_all_game_presets_include_buttons(self):
        """Verifies buttons are included across official mode, detailed mode, and other game presets."""
        buttons = [
            {"label": "Profile", "url": "https://op.gg"},
            {"label": "Twitch", "url": "https://twitch.tv"},
        ]

        # 1. LoL Official Mode
        mgr = DiscordRPCManager(client_id="test", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.mode = "oficial"
        mgr.buttons = buttons
        mgr._send_rpc_update()
        _, kw_oficial = mock_rpc.update.call_args
        self.assertIn("buttons", kw_oficial)
        self.assertEqual(len(kw_oficial["buttons"]), 2)

        # 2. LoL Detailed Mode
        mock_rpc.reset_mock()
        mgr.mode = "detallado"
        mgr.champion_name = "Zed"
        mgr._send_rpc_update()
        _, kw_detallado = mock_rpc.update.call_args
        self.assertIn("buttons", kw_detallado)
        self.assertEqual(len(kw_detallado["buttons"]), 2)

        # 3. Valorant Preset
        mock_rpc.reset_mock()
        mgr.selected_game_id = "valorant"
        mgr._send_rpc_update()
        _, kw_val = mock_rpc.update.call_args
        self.assertIn("buttons", kw_val)
        self.assertEqual(len(kw_val["buttons"]), 2)

        # 4. Custom Game Preset
        mock_rpc.reset_mock()
        mgr.selected_game_id = "custom"
        mgr.custom_game_name = "Custom Game"
        mgr._send_rpc_update()
        _, kw_custom = mock_rpc.update.call_args
        self.assertIn("buttons", kw_custom)
        self.assertEqual(len(kw_custom["buttons"]), 2)

    def test_empty_buttons_omitted_across_all_presets(self):
        """Verifies 'buttons' key is NEVER passed in kwargs when buttons is empty/invalid."""
        mgr = DiscordRPCManager(client_id="test", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True

        for mode_or_game in [("lol", "oficial"), ("lol", "detallado"), ("valorant", "oficial"), ("custom", "oficial")]:
            mock_rpc.reset_mock()
            mgr.selected_game_id = mode_or_game[0]
            mgr.mode = mode_or_game[1]
            mgr.buttons = []
            mgr._send_rpc_update()
            _, kwargs = mock_rpc.update.call_args
            self.assertNotIn("buttons", kwargs, f"Omission failed for {mode_or_game}")

    def test_concurrent_button_updates_thread_safety(self):
        """Stress-tests concurrent calls to update_presence_config and _send_rpc_update."""
        mgr = DiscordRPCManager(client_id="test", auto_start=False)
        mock_rpc = MagicMock()
        mgr._rpc = mock_rpc
        mgr.is_active = True

        errors = []

        def worker_updater(worker_id: int):
            for i in range(50):
                try:
                    btn_label = f"W{worker_id}_{i}"
                    mgr._process_command(
                        "CONFIG_CHANGE",
                        {"buttons": [{"label": btn_label, "url": f"https://test.com/{worker_id}/{i}"}]},
                    )
                    mgr._send_rpc_update()
                except Exception as ex:
                    errors.append(ex)

        threads = [threading.Thread(target=worker_updater, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Thread concurrency errors: {errors}")
        self.assertTrue(mock_rpc.update.call_count >= 250)


class TestConfigPersistenceRoundtrip(unittest.TestCase):
    """Verifies empirical file persistence, corruption resilience, and roundtrip loading."""

    def setUp(self):
        self.backup_path = CONFIG_FILE + ".bak_stress"
        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, self.backup_path)

    def tearDown(self):
        if os.path.exists(self.backup_path):
            shutil.copy2(self.backup_path, CONFIG_FILE)
            os.remove(self.backup_path)

    def test_empirical_disk_persistence_roundtrip(self):
        """Exact 2-button persistence verification on ~/.config/lol_discord_rpc/config.json."""
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        two_buttons = [
            {"label": "OP.GG Profile", "url": "https://op.gg/summoners/lan/TestPlayer"},
            {"label": "Discord Server", "url": "https://discord.gg/leaguecommunity"},
        ]

        ctrl.apply_config(
            game_id="lol",
            client_id="1234567890",
            details="Ranked Solo/Duo",
            duration_min=25,
            buttons=two_buttons,
        )

        # 1. Direct file check on disk
        self.assertTrue(os.path.exists(CONFIG_FILE))
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            disk_content = json.load(f)

        self.assertIn("buttons", disk_content)
        self.assertEqual(disk_content["buttons"], two_buttons)

        # 2. Fresh LoLPopoverController load
        fresh_ctrl = popover_ui.LoLPopoverController.alloc().init()
        self.assertEqual(fresh_ctrl._buttons, two_buttons)

        # 3. Fresh DiscordRPCManager load
        fresh_mgr = DiscordRPCManager(client_id="default", auto_start=False, load_config=True)
        self.assertEqual(fresh_mgr.buttons, two_buttons)

    def test_corrupted_json_resilience(self):
        """Corrupted JSON on disk does not crash fresh LoLPopoverController or DiscordRPCManager."""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write("{ INVALID JSON SYNTAX >>> }")

        # LoLPopoverController handles corrupted config cleanly
        ctrl = popover_ui.LoLPopoverController.alloc().init()
        self.assertEqual(ctrl._buttons, [])

        # DiscordRPCManager handles corrupted config cleanly
        mgr = DiscordRPCManager(client_id="default", auto_start=False, load_config=True)
        self.assertEqual(mgr.buttons, [])

    def test_non_list_buttons_in_json_resilience(self):
        """Non-list buttons in config.json do not cause unhandled crashes."""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        bad_configs = [
            {"buttons": None},
            {"buttons": "just a string"},
            {"buttons": 99999},
            {"buttons": {"dict": "instead_of_list"}},
        ]

        for bad_cfg in bad_configs:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(bad_cfg, f)

            mgr = DiscordRPCManager(client_id="default", auto_start=False, load_config=True)
            mock_rpc = MagicMock()
            mgr._rpc = mock_rpc
            mgr.is_active = True
            # _send_rpc_update should handle bad buttons gracefully without throwing
            mgr._send_rpc_update()
            _, kwargs = mock_rpc.update.call_args
            self.assertNotIn("buttons", kwargs)


if __name__ == "__main__":
    unittest.main()
