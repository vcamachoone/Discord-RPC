"""
test_tier3_interactions.py - Tier 3: Pairwise Cross-Feature Interactions Suite

Verifies integration and communication between paired subsystems:
- T3.01 (F8 + F9): ChampionResolver + RankFormatter into Discord presence payload
- T3.02 (F4 + F7): Mode selector switching toggling Detailed settings visibility
- T3.03 (F4 + F10): Mode selector dispatching updated mode config to RPC manager
- T3.04 (F5 + F11): Autoreset switch controlling RPC manager match timer
- T3.05 (F6 + F1 + F10): Action button toggle syncing RPC state and status item icon
- T3.06 (F2 + F3): Status item button click driving NSPopover visibility
- T3.07 (F7 + F8 + F10): Champion settings resolving DDragon icon in RPC payload
- T3.08 (F7 + F9 + F10): Rank settings formatting division & crest in RPC payload
- T3.09 (F1 + F10): RPC connection state transitions driving menubar icon states
- T3.10 (F11 + F10): Auto-restart timer renewing presence start time in manager
- T3.11 (F12 + F1): App bundle packaging including generated status icon assets
- T3.12 (F6 + F5 + F10): Stopping presence pausing match reset timer
- T3.13 (F8 + F10): Unknown champion fallback resolving in RPC presence payload
- T3.14 (F9 + F10): Apex tier division suppression in RPC presence small_text
"""

import os
import queue
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.mocks import MockPresence, MockNSStatusItem, MockNSPopover

# Implemented modules
import lol_champions
from lol_champions import ChampionResolver

import lol_ranks
from lol_ranks import format_rank_display, get_rank_crest_url

import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState

# Optional modules for progressive testability
try:
    import assets_gen

    HAS_ASSETS_GEN = True
except ImportError:
    assets_gen = None
    HAS_ASSETS_GEN = False

try:
    import status_item

    HAS_STATUS_ITEM = True
except ImportError:
    status_item = None
    HAS_STATUS_ITEM = False

try:
    import popover_ui

    HAS_POPOVER_UI = True
except ImportError:
    popover_ui = None
    HAS_POPOVER_UI = False

try:
    import sync_bundle

    HAS_SYNC_BUNDLE = True
except ImportError:
    sync_bundle = None
    HAS_SYNC_BUNDLE = False


class TestTier3Interactions(unittest.TestCase):
    """Pairwise cross-feature interaction test cases."""

    def test_t3_01_f8_f9_payload_assembly(self):
        """T3.01 (F8 + F9): Assemble ChampionResolver and RankFormatter outputs into presence."""
        resolver = ChampionResolver()
        cid, display_name = resolver.resolve_champion("wukong")
        champ_icon_url = resolver.get_square_icon_url(cid)

        rank_text = format_rank_display("Challenger", "I")
        rank_crest_url = get_rank_crest_url("Challenger")

        presence_payload = {
            "details": f"Jugando {display_name}",
            "state": "En partida",
            "large_image": champ_icon_url,
            "large_text": display_name,
            "small_image": rank_crest_url,
            "small_text": rank_text,
        }

        self.assertEqual(cid, "MonkeyKing")
        self.assertIn("MonkeyKing.png", presence_payload["large_image"])
        self.assertEqual(presence_payload["small_text"], "Challenger")
        self.assertIn("challenger.png", presence_payload["small_image"])

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_t3_02_f4_f7_mode_switch_settings_visibility(self):
        """T3.02 (F4 + F7): Switching to Modo Detallado reveals settings view controls."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("oficial")
        self.assertFalse(controller.is_settings_panel_visible())
        controller.select_mode("detallado")
        self.assertTrue(controller.is_settings_panel_visible())

    def test_t3_03_f4_f10_mode_switch_pushes_rpc_config(self):
        """T3.03 (F4 + F10): Mode switch dispatches updated mode to DiscordRPCManager queue."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.update_presence_config(mode="detallado")
        cmd, payload = mgr._cmd_queue.get_nowait()
        self.assertEqual(cmd, "CONFIG_CHANGE")
        self.assertEqual(payload.get("mode"), "detallado")

    def test_t3_04_f5_f11_autoreset_switch_toggles_rpc_timer(self):
        """T3.04 (F5 + F11): Toggling autoreset switch updates autoreset in DiscordRPCManager."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.update_presence_config(autoreset=False)
        # Process command
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)
        self.assertFalse(mgr.autoreset)

        mgr.update_presence_config(autoreset=True)
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)
        self.assertTrue(mgr.autoreset)

    @unittest.skipUnless(
        HAS_POPOVER_UI and HAS_STATUS_ITEM, "popover_ui or status_item pending"
    )
    def test_t3_05_f6_f1_f10_action_button_toggles_status_icon(self):
        """T3.05 (F6 + F1 + F10): Action button toggle updates RPC manager and status icon."""
        status_ctrl = status_item.LoLStatusItemController()

        def on_state(state, msg):
            status_ctrl.set_state(
                "active"
                if state == "connected"
                else "paused"
                if state == "paused"
                else "normal"
            )

        mgr = DiscordRPCManager(on_state_change=on_state, auto_start=False)
        # Simulate active state
        mgr._notify_state(RPCState.CONNECTED, "Activo")
        self.assertEqual(status_ctrl.get_current_state(), "active")

        # Simulate paused state
        mgr.set_active(False)
        mgr._notify_state(RPCState.PAUSED, "Pausado")
        self.assertEqual(status_ctrl.get_current_state(), "paused")

    @unittest.skipUnless(
        HAS_POPOVER_UI and HAS_STATUS_ITEM, "popover_ui or status_item pending"
    )
    def test_t3_06_f2_f3_status_item_toggles_popover(self):
        """T3.06 (F2 + F3): Clicking status item button toggles popover visibility."""
        pop_ctrl = popover_ui.LoLPopoverController()
        status_ctrl = status_item.LoLStatusItemController(
            on_toggle_popover=lambda btn: pop_ctrl.toggle(btn)
        )
        btn = status_ctrl.get_button()
        status_ctrl.handle_click(btn)
        self.assertTrue(pop_ctrl.is_shown())
        status_ctrl.handle_click(btn)
        self.assertFalse(pop_ctrl.is_shown())

    def test_t3_07_f7_f8_f10_settings_champion_updates_rpc_presence(self):
        """T3.07 (F7 + F8 + F10): Selected champion resolves DDragon URL in RPC manager."""
        resolver = ChampionResolver()
        cid, name = resolver.resolve_champion("kaisa")
        icon_url = resolver.get_square_icon_url(cid)

        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mgr._rpc = mock_p

        mgr.update_presence_config(
            mode="detallado",
            champion_name=name,
            champion_image_url=icon_url,
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertEqual(mgr.champion_name, "Kai'Sa")
        self.assertIn("Kaisa.png", mgr.champion_image_url)

    def test_t3_08_f7_f9_f10_settings_rank_updates_rpc_crest(self):
        """T3.08 (F7 + F9 + F10): Selected rank formats division and crest in RPC manager."""
        rank_str = format_rank_display("Diamante", "I")
        crest_url = get_rank_crest_url("Diamante")

        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mgr._rpc = mock_p

        mgr.update_presence_config(
            mode="detallado",
            rank_text=rank_str,
            rank_image_url=crest_url,
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertEqual(mgr.rank_text, "Diamante I")
        self.assertIn("diamond.png", mgr.rank_image_url)

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_t3_09_f1_f10_rpc_state_updates_menubar_icon(self):
        """T3.09 (F1 + F10): RPC state changes drive menubar icon transitions."""
        status_ctrl = status_item.LoLStatusItemController()

        def state_listener(s, m):
            if s == RPCState.CONNECTED:
                status_ctrl.set_state("active")
            elif s == RPCState.PAUSED:
                status_ctrl.set_state("paused")
            else:
                status_ctrl.set_state("normal")

        mgr = DiscordRPCManager(on_state_change=state_listener, auto_start=False)
        mgr._notify_state(RPCState.CONNECTED, "Conectado")
        self.assertEqual(status_ctrl.get_current_state(), "active")
        mgr._notify_state(RPCState.PAUSED, "Pausado")
        self.assertEqual(status_ctrl.get_current_state(), "paused")
        mgr._notify_state(RPCState.DISCONNECTED, "Desconectado")
        self.assertEqual(status_ctrl.get_current_state(), "normal")

    def test_t3_10_f11_f10_match_reset_renews_presence_start_time(self):
        """T3.10 (F11 + F10): Match reset event renews start_time and calls on_match_reset."""
        resets = []
        mgr = DiscordRPCManager(
            on_match_reset=lambda t: resets.append(t),
            auto_start=False,
        )
        mock_p = MockPresence("123")
        mgr._rpc = mock_p

        old_start = mgr.start_time
        mgr.restart_match()
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertEqual(len(resets), 1)
        self.assertGreaterEqual(mgr.start_time, old_start)
        self.assertIsNotNone(mock_p.last_payload)
        self.assertEqual(mock_p.last_payload.get("start"), mgr.start_time)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_t3_11_f12_f1_bundle_contains_generated_status_icons(self):
        """T3.11 (F12 + F1): Verify generated status icons can be placed in bundle resources."""
        bundle_res = "/Applications/League of Legends RPC.app/Contents/Resources"
        self.assertTrue(os.path.isdir(bundle_res))
        # Test generation into a test bundle directory
        test_res = tempfile.mkdtemp(prefix="test_bundle_res_")
        try:
            icons = assets_gen.generate_status_icons(test_res)
            for state in ("normal", "active", "paused"):
                self.assertTrue(os.path.exists(icons[state]))
        finally:
            shutil.rmtree(test_res, ignore_errors=True)

    def test_t3_12_f6_f5_f10_stopping_presence_halts_timer(self):
        """T3.12 (F6 + F5 + F10): Stopping presence halts active match presence and clears socket."""
        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mock_p.connected = True
        mgr._rpc = mock_p

        mgr.set_active(False)
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertFalse(mgr.is_active)
        self.assertEqual(mock_p.clear_count, 1)
        self.assertEqual(mgr.state, RPCState.PAUSED)

    def test_t3_13_f8_f10_unknown_champion_fallback_in_presence(self):
        """T3.13 (F8 + F10): Unknown champion gracefully resolves to fallback in presence payload."""
        resolver = ChampionResolver()
        cid, name = resolver.resolve_champion("RandomChampionThatDoesNotExist")
        self.assertEqual(cid, "Malzahar")

        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mgr._rpc = mock_p

        mgr.update_presence_config(
            mode="detallado",
            champion_name=name,
            champion_image_url=resolver.get_square_icon_url(cid),
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertIn("Malzahar.png", mock_p.last_payload["large_image"])

    def test_t3_14_f9_f10_apex_tier_suppression_in_presence_payload(self):
        """T3.14 (F9 + F10): Challenger or Master suppresses division in presence small_text."""
        rank_str = format_rank_display("Gran Maestro", "IV")
        self.assertEqual(rank_str, "Gran Maestro")

        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mgr._rpc = mock_p

        mgr.update_presence_config(
            mode="detallado",
            rank_text=rank_str,
            rank_image_url=get_rank_crest_url("Gran Maestro"),
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertEqual(mock_p.last_payload["small_text"], "Gran Maestro")
        self.assertNotIn("IV", mock_p.last_payload["small_text"])


if __name__ == "__main__":
    unittest.main()
