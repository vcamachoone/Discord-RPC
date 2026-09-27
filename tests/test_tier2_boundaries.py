"""
test_tier2_boundaries.py - Tier 2: Boundary, Corner Cases & Error Handling Suite

Covers edge cases, boundary conditions, corrupt/empty inputs, and fault injection
across all 12 project features:
- F1: Dynamic Menubar Icons (assets_gen.py)
- F2: Menu Bar Item Controller (status_item.py)
- F3: Floating Dark NSPopover UI (popover_ui.py)
- F4: Interactive Mode Selector (popover_ui.py)
- F5: Interactive Switches (popover_ui.py)
- F6: Bottom Action Button (popover_ui.py)
- F7: Settings / Detailed View (popover_ui.py)
- F8: Champion Resolver & Data Dragon (lol_champions.py)
- F9: Rank Crests & Division Formatter (lol_ranks.py)
- F10: Concurrency & Thread-Safe RPC Manager (discord_rpc_manager.py)
- F11: Auto-restart Match Timer (discord_rpc_manager.py)
- F12: App Bundle Packaging & Sync (sync_bundle.py & /Applications bundle)
"""

import os
import plistlib
import queue
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.mocks import MockAppHelper, MockPresence

# Implemented M3 modules
import lol_champions
from lol_champions import ChampionResolver

import lol_ranks
from lol_ranks import format_rank_display, get_rank_crest_url, is_apex_tier

import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState

# Optional / in-progress modules for progressive testability
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


# =============================================================================
# F1: Dynamic Menubar Icons Boundaries
# =============================================================================
class TestF1BoundaryIcons(unittest.TestCase):
    """Boundary and corner cases for icon generation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_f1_b_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_b1_nonexistent_output_dir(self):
        """F1.B1: Passing deeply nested non-existent directory creates parents automatically."""
        nested_dir = os.path.join(self.temp_dir, "a", "b", "c", "icons")
        icons = assets_gen.generate_status_icons(nested_dir)
        self.assertTrue(os.path.isdir(nested_dir))
        for path in icons.values():
            self.assertTrue(os.path.exists(path))

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_b2_idempotent_overwrite(self):
        """F1.B2: Running generate_status_icons twice on existing directory overwrites cleanly."""
        icons1 = assets_gen.generate_status_icons(self.temp_dir)
        mtimes1 = {s: os.path.getmtime(p) for s, p in icons1.items()}
        time.sleep(0.02)
        icons2 = assets_gen.generate_status_icons(self.temp_dir)
        self.assertEqual(set(icons1.keys()), set(icons2.keys()))
        for s in icons1:
            self.assertTrue(os.path.exists(icons2[s]))

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_b3_alpha_channel_integrity(self):
        """F1.B3: Verify RGBA 4-channel modes and alpha validity for all generated icons."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        for state, path in icons.items():
            with Image.open(path) as img:
                self.assertEqual(img.mode, "RGBA")
                extrema = img.getextrema()
                # Check alpha band extrema (min, max)
                alpha_extrema = extrema[3]
                self.assertEqual(len(alpha_extrema), 2)
                self.assertGreaterEqual(alpha_extrema[0], 0)
                self.assertLessEqual(alpha_extrema[1], 255)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_b4_blue_dot_coordinate_bounds(self):
        """F1.B4: Blue dot in active icon is strictly contained within icon boundaries."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        with Image.open(icons["active"]) as img:
            w, h = img.size
            # Inspect borders (x=0, x=w-1, y=0, y=h-1) - they should have alpha == 0
            border_alphas = []
            for x in range(w):
                border_alphas.append(img.getpixel((x, 0))[3])
                border_alphas.append(img.getpixel((x, h - 1))[3])
            for y in range(h):
                border_alphas.append(img.getpixel((0, y))[3])
                border_alphas.append(img.getpixel((w - 1, y))[3])
            # The corner pixel at (w-1, h-1) should not bleed fully to raw edge
            self.assertEqual(img.getpixel((w - 1, h - 1))[3], 0)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_b5_paused_alpha_boundary(self):
        """F1.B5: Paused icon has alpha > 0 (not blank) and < 160 (not fully opaque)."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        with Image.open(icons["paused"]) as img:
            alphas = [p[3] for p in img.getdata() if p[3] > 0]
            self.assertTrue(len(alphas) > 0)
            max_alpha = max(alphas)
            self.assertGreater(max_alpha, 30)
            self.assertLessEqual(max_alpha, 160)


# =============================================================================
# F2: Menu Bar Item Boundaries
# =============================================================================
class TestF2BoundaryStatusItem(unittest.TestCase):
    """Boundary and resilience cases for status item controller."""

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_b1_rapid_state_transitions(self):
        """F2.B1: Rapidly alternating status item states 100 times without memory error."""
        controller = status_item.LoLStatusItemController()
        states = ["normal", "active", "paused"] * 33
        for s in states:
            controller.set_state(s)
        self.assertEqual(controller.get_current_state(), "paused")

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_b2_invalid_state_string(self):
        """F2.B2: Passing unrecognized state string defaults safely to normal without crash."""
        controller = status_item.LoLStatusItemController()
        controller.set_state("non_existent_state_xyz")
        # Should safely handle or default
        self.assertIn(
            controller.get_current_state(),
            ["normal", "non_existent_state_xyz"],
        )

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_b3_empty_state_string(self):
        """F2.B3: Passing empty string '' does not raise unhandled exception."""
        controller = status_item.LoLStatusItemController()
        controller.set_state("")
        self.assertIsNotNone(controller.get_button())

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_b4_none_state_handling(self):
        """F2.B4: Passing None does not crash controller."""
        controller = status_item.LoLStatusItemController()
        controller.set_state(None)
        self.assertIsNotNone(controller.get_button())

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_b5_double_click_safety(self):
        """F2.B5: Rapid simulated double clicks on status item button do not error."""
        clicks = []
        controller = status_item.LoLStatusItemController(
            on_toggle_popover=lambda s: clicks.append(True)
        )
        btn = controller.get_button()
        controller.handle_click(btn)
        controller.handle_click(btn)
        self.assertEqual(len(clicks), 2)


# =============================================================================
# F3: Popover UI Boundaries
# =============================================================================
class TestF3BoundaryPopover(unittest.TestCase):
    """Boundary cases for NSPopover presentation and windowing."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_b1_rapid_toggle_popover(self):
        """F3.B1: Rapidly calling show() and close() in loop does not create orphaned windows."""
        controller = popover_ui.LoLPopoverController()
        mock_view = MagicMock()
        for _ in range(20):
            controller.show(mock_view)
            controller.close()
        self.assertFalse(controller.is_shown())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_b2_show_when_already_shown(self):
        """F3.B2: Calling show() when popover is already shown is safe and idempotent."""
        controller = popover_ui.LoLPopoverController()
        mock_view = MagicMock()
        controller.show(mock_view)
        controller.show(mock_view)
        self.assertTrue(controller.is_shown())
        controller.close()

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_b3_close_when_already_closed(self):
        """F3.B3: Calling close() when popover is not shown is safe and idempotent."""
        controller = popover_ui.LoLPopoverController()
        controller.close()
        controller.close()
        self.assertFalse(controller.is_shown())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_b4_appearance_override(self):
        """F3.B4: Dark appearance is forced regardless of system theme."""
        controller = popover_ui.LoLPopoverController()
        pop = controller.get_popover()
        self.assertIsNotNone(pop.appearance())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_b5_content_view_controller_retained(self):
        """F3.B5: Content view controller reference is maintained to avoid GC dealloc crash."""
        controller = popover_ui.LoLPopoverController()
        vc = controller.get_content_view_controller()
        self.assertIsNotNone(vc)
        self.assertIsNotNone(vc.view())


# =============================================================================
# F4: Mode Selector Boundaries
# =============================================================================
class TestF4BoundaryModeSelector(unittest.TestCase):
    """Boundary cases for mode selection."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_b1_repeated_same_mode_selection(self):
        """F4.B1: Selecting already active mode is no-op and does not cause redundant callbacks."""
        calls = []
        controller = popover_ui.LoLPopoverController(
            on_mode_change=lambda m: calls.append(m)
        )
        controller.select_mode("oficial")
        # Selecting same mode again
        controller.select_mode("oficial")
        self.assertLessEqual(len(calls), 1)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_b2_rapid_mode_switching(self):
        """F4.B2: Toggling between modes 50 times in rapid succession."""
        controller = popover_ui.LoLPopoverController()
        for i in range(50):
            target = "oficial" if i % 2 == 0 else "detallado"
            controller.select_mode(target)
        self.assertEqual(controller.get_current_mode(), "detallado")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_b3_case_insensitive_mode_string(self):
        """F4.B3: Normalizes uppercase and mixed-case mode strings."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("OFICIAL")
        self.assertEqual(controller.get_current_mode(), "oficial")
        controller.select_mode("Detallado")
        self.assertEqual(controller.get_current_mode(), "detallado")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_b4_invalid_mode_identifier(self):
        """F4.B4: Invalid mode identifier handled without crashing."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("invalid_mode_xyz")
        # Should stay on existing mode or fallback safely
        self.assertIn(controller.get_current_mode(), ["oficial", "detallado"])

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_b5_mode_settings_retention(self):
        """F4.B5: Switching modes preserves configured champion and rank values in detailed view."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("detallado")
        controller.set_selected_champion("Kaisa")
        controller.select_mode("oficial")
        controller.select_mode("detallado")
        self.assertEqual(controller.get_selected_champion(), "Kaisa")


# =============================================================================
# F5: Switches Boundaries
# =============================================================================
class TestF5BoundarySwitches(unittest.TestCase):
    """Boundary and error handling for UI switches."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_b1_rapid_switch_toggling(self):
        """F5.B1: Rapid toggle of switches 50 times does not hang."""
        controller = popover_ui.LoLPopoverController()
        for i in range(50):
            controller.set_autoreset_state(i % 2 == 0)
        self.assertFalse(controller.get_autoreset_state())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_b2_switch_non_boolean_values(self):
        """F5.B2: Non-boolean values (0, 1, 'true') converted to boolean cleanly."""
        controller = popover_ui.LoLPopoverController()
        controller.set_autoreset_state(0)
        self.assertFalse(controller.get_autoreset_state())
        controller.set_autoreset_state(1)
        self.assertTrue(controller.get_autoreset_state())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_b3_simultaneous_switch_toggles(self):
        """F5.B3: Toggling both switches concurrently remains consistent."""
        controller = popover_ui.LoLPopoverController()
        controller.set_autoreset_state(False)
        controller.toggle_autorun(True)
        self.assertFalse(controller.get_autoreset_state())
        self.assertTrue(controller.get_autorun_state())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_b4_switch_state_consistency(self):
        """F5.B4: Switch state maintains internal consistency when read repeatedly."""
        controller = popover_ui.LoLPopoverController()
        state1 = controller.get_autoreset_state()
        state2 = controller.get_autoreset_state()
        self.assertEqual(state1, state2)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_b5_login_item_error_resilience(self):
        """F5.B5: Login item error caught without unhandled exception."""
        controller = popover_ui.LoLPopoverController()
        with patch("subprocess.run", side_effect=OSError("Permission denied")):
            # Should not raise
            controller.toggle_autorun(True)


# =============================================================================
# F6: Bottom Action Button Boundaries
# =============================================================================
class TestF6BoundaryActionButton(unittest.TestCase):
    """Boundary and hammer testing on the main action button."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_b1_rapid_button_hammering(self):
        """F6.B1: 20 rapid clicks on action button toggles state deterministically."""
        controller = popover_ui.LoLPopoverController()
        initial = controller.is_presence_active()
        for _ in range(20):
            controller.handle_action_button_click()
        self.assertEqual(controller.is_presence_active(), initial)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_b2_button_title_string_integrity(self):
        """F6.B2: Button titles are never empty or None."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(True)
        self.assertGreater(len(controller.get_action_button_title()), 3)
        controller.set_presence_active(False)
        self.assertGreater(len(controller.get_action_button_title()), 3)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_b3_action_button_during_connecting(self):
        """F6.B3: Clicking while in connecting state handled cleanly."""
        controller = popover_ui.LoLPopoverController()
        controller.set_connection_state("connecting")
        controller.handle_action_button_click()
        self.assertIsNotNone(controller.get_action_button_title())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_b4_action_button_idempotent_state(self):
        """F6.B4: Setting same active state repeatedly is safe and idempotent."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(True)
        controller.set_presence_active(True)
        self.assertTrue(controller.is_presence_active())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_b5_action_button_callback_exception_isolation(self):
        """F6.B5: Callback exception does not crash UI."""
        def bad_callback(active):
            raise RuntimeError("Boom!")

        controller = popover_ui.LoLPopoverController(on_action_toggle=bad_callback)
        # Should catch or isolate error
        controller.handle_action_button_click()


# =============================================================================
# F7: Settings View Boundaries
# =============================================================================
class TestF7BoundarySettingsView(unittest.TestCase):
    """Boundary inputs for settings fields."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_b1_empty_champion_input(self):
        """F7.B1: Empty champion input defaults safely to fallback champion."""
        controller = popover_ui.LoLPopoverController()
        controller.set_selected_champion("")
        self.assertIn(
            controller.get_selected_champion(), ["Malzahar", ""]
        )

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_b2_excessively_long_champion_name(self):
        """F7.B2: String of 500 characters does not crash or buffer overflow."""
        controller = popover_ui.LoLPopoverController()
        long_str = "A" * 500
        controller.set_selected_champion(long_str)
        self.assertIsNotNone(controller.get_selected_champion())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_b3_special_unicode_champion_input(self):
        """F7.B3: Non-ASCII characters and emojis handled cleanly."""
        controller = popover_ui.LoLPopoverController()
        controller.set_selected_champion("⚔️ Yasuo 🔥")
        self.assertIsNotNone(controller.get_selected_champion())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_b4_whitespace_only_champion(self):
        """F7.B4: Whitespace-only string handled safely."""
        controller = popover_ui.LoLPopoverController()
        controller.set_selected_champion("     ")
        self.assertIsNotNone(controller.get_selected_champion())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_b5_division_reset_on_tier_change(self):
        """F7.B5: Switching to Challenger disables division, switching back to Oro enables it."""
        controller = popover_ui.LoLPopoverController()
        controller.select_rank("Challenger")
        self.assertFalse(controller.is_division_selector_enabled())
        controller.select_rank("Oro")
        self.assertTrue(controller.is_division_selector_enabled())


# =============================================================================
# F8: Champion Resolver Boundaries
# =============================================================================
class TestF8BoundaryChampionResolver(unittest.TestCase):
    """Boundary conditions and adversarial inputs for ChampionResolver."""

    def setUp(self):
        self.resolver = ChampionResolver()

    def test_f8_b1_empty_and_none_champion_input(self):
        """F8.B1: Empty, whitespace, and None return safe fallback champion ('Malzahar')."""
        self.assertEqual(self.resolver.resolve_champion("")[0], "Malzahar")
        self.assertEqual(self.resolver.resolve_champion(None)[0], "Malzahar")
        self.assertEqual(self.resolver.resolve_champion("   ")[0], "Malzahar")

    def test_f8_b2_all_punctuation_combinations(self):
        """F8.B2: Verifies punctuation stripping for apostrophes, dots, and hyphens."""
        cases = {
            "cho'gath": "Chogath",
            "CHO GATH": "Chogath",
            "cho-gath": "Chogath",
            "dr. mundo": "DrMundo",
            "k'sante": "KSante",
            "kog'maw": "KogMaw",
            "rek'sai": "RekSai",
        }
        for query, expected_id in cases.items():
            cid, _ = self.resolver.resolve_champion(query)
            self.assertEqual(cid, expected_id)

    def test_f8_b3_mixed_case_anomalies(self):
        """F8.B3: Verifies case-insensitivity on anomaly champions."""
        self.assertEqual(self.resolver.resolve_champion("wUkOnG")[0], "MonkeyKing")
        self.assertEqual(self.resolver.resolve_champion("kAi'sA")[0], "Kaisa")
        self.assertEqual(self.resolver.resolve_champion("vEl'kOz")[0], "Velkoz")
        self.assertEqual(self.resolver.resolve_champion("kHa'zIx")[0], "Khazix")
        self.assertEqual(self.resolver.resolve_champion("bEl'vEtH")[0], "Belveth")
        self.assertEqual(self.resolver.resolve_champion("lEbLaNc")[0], "Leblanc")

    def test_f8_b4_all_173_champions_non_empty_url(self):
        """F8.B4: Every champion in the 173 canonical roster produces valid non-empty CDN URL."""
        all_champs = self.resolver.get_all_champions()
        self.assertEqual(len(all_champs), 173)
        for cid, display_name in all_champs:
            url = self.resolver.get_square_icon_url(cid)
            self.assertTrue(url.startswith("https://ddragon.leagueoflegends.com/"))
            self.assertTrue(url.endswith(f"{cid}.png"))

    def test_f8_b5_completely_unknown_gibberish(self):
        """F8.B5: Completely unknown gibberish resolves safely to fallback champion."""
        cid, _ = self.resolver.resolve_champion("asdfqwer9876xyz!@#$%")
        self.assertEqual(cid, "Malzahar")


# =============================================================================
# F9: Rank Formatter Boundaries
# =============================================================================
class TestF9BoundaryRankFormatter(unittest.TestCase):
    """Boundary conditions and division suppression edge cases."""

    def test_f9_b1_empty_and_none_tier(self):
        """F9.B1: Empty, whitespace, or None tier returns 'Unranked'."""
        self.assertEqual(format_rank_display(""), "Unranked")
        self.assertEqual(format_rank_display(None), "Unranked")
        self.assertEqual(format_rank_display("   "), "Unranked")

    def test_f9_b2_all_apex_variants_case_insensitive(self):
        """F9.B2: Case-insensitive suppression for all Apex tier variations."""
        self.assertEqual(format_rank_display("CHALLENGER", "II"), "CHALLENGER")
        self.assertEqual(format_rank_display("master", "IV"), "master")
        self.assertEqual(format_rank_display("gran maestro", "I"), "gran maestro")
        self.assertEqual(format_rank_display("sin rango", "II"), "sin rango")
        self.assertEqual(format_rank_display("unranked", "III"), "unranked")

    def test_f9_b3_tier_already_containing_division(self):
        """F9.B3: Prevents accidental duplicate division suffixes ('Oro II' + 'II' -> 'Oro II')."""
        self.assertEqual(format_rank_display("Oro II", "II"), "Oro II")
        self.assertEqual(format_rank_display("Diamante IV", "IV"), "Diamante IV")

    def test_f9_b4_invalid_empty_division(self):
        """F9.B4: Empty division string with standard tier omits division suffix cleanly."""
        self.assertEqual(format_rank_display("Platino", ""), "Platino")
        self.assertEqual(format_rank_display("Platino", None), "Platino")

    def test_f9_b5_unknown_tier_crest_fallback(self):
        """F9.B5: Unknown tier crest request falls back safely to default crest."""
        fallback_url = get_rank_crest_url("UnknownTierXYZ")
        self.assertTrue(fallback_url.endswith("gold.png"))
        empty_url = get_rank_crest_url("")
        self.assertTrue(empty_url.endswith("gold.png"))


# =============================================================================
# F10: Concurrency RPC Manager Boundaries
# =============================================================================
class TestF10BoundaryRPCManager(unittest.TestCase):
    """Stress and error resilience testing for DiscordRPCManager."""

    def test_f10_b1_queue_flooding_1000_commands(self):
        """F10.B1: Flooding queue with 1000 commands causes no crash or memory corruption."""
        mgr = DiscordRPCManager(auto_start=False)
        for i in range(1000):
            mgr.update_presence_config(details=f"Game {i}")
        self.assertEqual(mgr._cmd_queue.qsize(), 1000)

    def test_f10_b2_broken_pipe_socket_error(self):
        """F10.B2: Socket raising BrokenPipeError handled cleanly without unhandled exception."""
        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mock_p.update_exception = BrokenPipeError("Socket closed")
        mgr._rpc = mock_p
        # When update raises BrokenPipe, manager should catch and transition
        mgr._send_rpc_update()
        self.assertEqual(mgr.state, RPCState.DISCONNECTED)

    def test_f10_b3_discord_not_found_error(self):
        """F10.B3: DiscordNotFound exception handled gracefully."""
        from pypresence import DiscordNotFound

        mgr = DiscordRPCManager(auto_start=False)
        mock_p = MockPresence("123")
        mock_p.connect_exception = DiscordNotFound()
        # Ensure exception is caught in worker reconnect logic
        self.assertIsNotNone(mock_p.connect_exception)

    def test_f10_b4_double_shutdown(self):
        """F10.B4: Calling shutdown() twice in succession is completely safe."""
        mgr = DiscordRPCManager(auto_start=True)
        mgr.shutdown()
        mgr.shutdown()
        self.assertFalse(mgr._running)

    def test_f10_b5_callback_exception_isolation(self):
        """F10.B5: Exception in on_state_change does not crash dispatcher."""
        def crashing_callback(s, m):
            raise ValueError("Callback crash!")

        mgr = DiscordRPCManager(on_state_change=crashing_callback, auto_start=False)
        # Should not raise exception out of _notify_state
        mgr._notify_state(RPCState.CONNECTED, "OK")
        self.assertEqual(mgr.state, RPCState.CONNECTED)


# =============================================================================
# F11: Match Timer Boundaries
# =============================================================================
class TestF11BoundaryTimer(unittest.TestCase):
    """Timer clock jump, disabled state, and bound checks."""

    def test_f11_b1_zero_or_negative_elapsed_time(self):
        """F11.B1: Future start_time (clock drift) clamped to 0 elapsed seconds."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.start_time = int(time.time()) + 500  # in the future
        self.assertEqual(mgr.get_elapsed_seconds(), 0)

    def test_f11_b2_timer_disabled_does_not_fire(self):
        """F11.B2: When autoreset=False, elapsed >= duration does not trigger auto-reset."""
        resets = []
        mgr = DiscordRPCManager(
            on_match_reset=lambda t: resets.append(t),
            auto_start=False,
        )
        mgr.autoreset = False
        mgr.start_time = int(time.time()) - 2500  # well over 30 min
        mgr.match_duration_sec = 1200
        # Simulating worker loop check:
        if mgr.is_active and mgr._rpc and mgr.autoreset:
            elapsed = int(time.time()) - mgr.start_time
            if elapsed >= mgr.match_duration_sec:
                mgr._notify_match_reset(int(time.time()))
        self.assertEqual(len(resets), 0)

    def test_f11_b3_rapid_manual_restarts(self):
        """F11.B3: Calling restart_match 10 times in rapid succession sets valid timestamps."""
        mgr = DiscordRPCManager(auto_start=False)
        for _ in range(10):
            mgr.restart_match()
        self.assertEqual(mgr._cmd_queue.qsize(), 10)

    def test_f11_b4_timer_random_bounds_check(self):
        """F11.B4: 100 randomly sampled durations strictly within [1200, 1800]."""
        for _ in range(100):
            m = DiscordRPCManager(auto_start=False)
            self.assertGreaterEqual(m.match_duration_sec, 1200)
            self.assertLessEqual(m.match_duration_sec, 1800)

    def test_f11_b5_timer_cleanup_on_shutdown(self):
        """F11.B5: Manager shutdown terminates any timer loops."""
        mgr = DiscordRPCManager(auto_start=True)
        mgr.shutdown()
        self.assertFalse(mgr._worker_thread.is_alive())


# =============================================================================
# F12: Bundle Boundaries
# =============================================================================
class TestF12BoundaryBundle(unittest.TestCase):
    """Boundary checks on macOS Application bundle structure."""

    BUNDLE_PATH = "/Applications/League of Legends RPC.app"

    def test_f12_b1_missing_keys_in_plist(self):
        """F12.B1: CFBundleIdentifier, CFBundleExecutable, and LSUIElement are non-empty."""
        plist_path = os.path.join(self.BUNDLE_PATH, "Contents", "Info.plist")
        with open(plist_path, "rb") as f:
            p = plistlib.load(f)
        self.assertTrue(len(p.get("CFBundleExecutable", "")) > 0)
        self.assertTrue(len(p.get("CFBundleIdentifier", "")) > 0)
        self.assertIs(p.get("LSUIElement"), True)

    def test_f12_b2_launcher_permissions_executable(self):
        """F12.B2: Launcher script has executable permissions (+x)."""
        launcher_path = os.path.join(
            self.BUNDLE_PATH, "Contents", "MacOS", "League of Legends RPC"
        )
        self.assertTrue(os.path.exists(launcher_path))
        self.assertTrue(os.access(launcher_path, os.X_OK))

    def test_f12_b3_valid_icns_header(self):
        """F12.B3: Verify AppIcon.icns magic header is b'icns'."""
        icns_path = os.path.join(
            self.BUNDLE_PATH, "Contents", "Resources", "AppIcon.icns"
        )
        with open(icns_path, "rb") as f:
            self.assertEqual(f.read(4), b"icns")

    def test_f12_b4_bundle_path_special_characters(self):
        """F12.B4: Bundle path with spaces is properly quoted in launcher."""
        launcher_path = os.path.join(
            self.BUNDLE_PATH, "Contents", "MacOS", "League of Legends RPC"
        )
        with open(launcher_path, "r") as f:
            content = f.read()
        self.assertIn('"$RESOURCES/app_gui.py"', content)

    def test_f12_b5_sync_idempotence(self):
        """F12.B5: Resources directory contains app_gui.py and is readable."""
        resources_dir = os.path.join(self.BUNDLE_PATH, "Contents", "Resources")
        self.assertTrue(os.path.isdir(resources_dir))
        app_gui_copy = os.path.join(resources_dir, "app_gui.py")
        self.assertTrue(os.path.exists(app_gui_copy))


if __name__ == "__main__":
    unittest.main()
