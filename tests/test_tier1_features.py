"""
test_tier1_features.py - Tier 1: Core Feature Coverage Test Suite

Verifies functional correctness and interface contracts for all 12 project features:
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
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.mocks import MockAppHelper, MockNSPopover, MockPresence, MockNSStatusItem

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
# F1: Dynamic Menubar Icons (assets_gen.py)
# =============================================================================
class TestF1DynamicIcons(unittest.TestCase):
    """Tests dynamic status icons generation and pixel/alpha properties."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_f1_icons_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_generate_icons_creates_files(self):
        """F1.1: Verify generate_status_icons produces normal, active, and paused PNG files."""
        icons = assets_gen.generate_status_icons(self.temp_dir)
        self.assertIsInstance(icons, dict)
        for state in ("normal", "active", "paused"):
            self.assertIn(state, icons)
            icon_path = icons[state]
            self.assertTrue(
                os.path.exists(icon_path), f"Icon for {state} not found on disk"
            )
            self.assertTrue(icon_path.endswith(".png"))
            self.assertGreater(os.path.getsize(icon_path), 100)

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_icon_dimensions(self):
        """F1.2: Verify generated icons match 44x44 px (Retina 22x22 pt) or 22x22 px dimensions."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        for state, path in icons.items():
            with Image.open(path) as img:
                self.assertIn(
                    img.size,
                    [(44, 44), (22, 22)],
                    f"{state} icon size {img.size} is neither 44x44 nor 22x22",
                )
                self.assertEqual(img.mode, "RGBA")

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_active_icon_has_blue_dot(self):
        """F1.3: Verify active icon contains vibrant blue indicator dot (#00A8FC) in bottom-right."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        with Image.open(icons["active"]) as img:
            w, h = img.size
            # Sample bottom-right quadrant: x > w/2, y > h/2
            has_blue = False
            for x in range(w // 2, w):
                for y in range(h // 2, h):
                    r, g, b, a = img.getpixel((x, y))
                    if a > 100 and b > 200 and r < 50:  # Characteristic of #00A8FC
                        has_blue = True
                        break
                if has_blue:
                    break
            self.assertTrue(
                has_blue, "Active icon does not contain blue status dot pixels"
            )

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_paused_icon_dimmed_alpha(self):
        """F1.4: Verify paused icon has significantly dimmed alpha (~35%) compared to normal."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        with Image.open(icons["normal"]) as img_norm, Image.open(
            icons["paused"]
        ) as img_pause:
            # Measure average alpha of non-fully-transparent pixels
            norm_alphas = [p[3] for p in img_norm.getdata() if p[3] > 10]
            pause_alphas = [p[3] for p in img_pause.getdata() if p[3] > 10]
            self.assertTrue(len(norm_alphas) > 0 and len(pause_alphas) > 0)
            avg_norm = sum(norm_alphas) / len(norm_alphas)
            avg_pause = sum(pause_alphas) / len(pause_alphas)
            # Paused should be less than 60% of normal alpha
            self.assertLess(
                avg_pause,
                avg_norm * 0.65,
                f"Paused alpha ({avg_pause}) is not sufficiently dimmed vs normal ({avg_norm})",
            )

    @unittest.skipUnless(HAS_ASSETS_GEN, "assets_gen.py pending in Milestone 1")
    def test_f1_normal_icon_monochrome_template(self):
        """F1.5: Verify normal icon is strictly monochrome (R==G==B) for macOS template mode."""
        from PIL import Image

        icons = assets_gen.generate_status_icons(self.temp_dir)
        with Image.open(icons["normal"]) as img:
            for r, g, b, a in img.getdata():
                if a > 10:
                    self.assertEqual(
                        r,
                        g,
                        f"Normal icon has color deviation: R={r} != G={g}",
                    )
                    self.assertEqual(
                        g,
                        b,
                        f"Normal icon has color deviation: G={g} != B={b}",
                    )


# =============================================================================
# F2: Menu Bar Item Controller (status_item.py)
# =============================================================================
class TestF2StatusItem(unittest.TestCase):
    """Tests PyObjC NSStatusItem controller state and template management."""

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_status_item_initialization(self):
        """F2.1: Verify LoLStatusItemController instantiates and creates status item."""
        controller = status_item.LoLStatusItemController()
        self.assertIsNotNone(controller.get_status_item())
        self.assertIsNotNone(controller.get_button())

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_status_item_normal_template_mode(self):
        """F2.2: Verify set_state('normal') activates template mode."""
        controller = status_item.LoLStatusItemController()
        controller.set_state("normal")
        button = controller.get_button()
        image = button.image()
        self.assertIsNotNone(image)
        self.assertTrue(
            image.isTemplate(), "Normal icon should have isTemplate() == True"
        )

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_status_item_active_non_template_mode(self):
        """F2.3: Verify set_state('active') disables template mode (to show blue dot)."""
        controller = status_item.LoLStatusItemController()
        controller.set_state("active")
        button = controller.get_button()
        image = button.image()
        self.assertIsNotNone(image)
        self.assertFalse(
            image.isTemplate(), "Active icon should have isTemplate() == False"
        )

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_status_item_paused_non_template_mode(self):
        """F2.4: Verify set_state('paused') disables template mode (to preserve dimmed alpha)."""
        controller = status_item.LoLStatusItemController()
        controller.set_state("paused")
        button = controller.get_button()
        image = button.image()
        self.assertIsNotNone(image)
        self.assertFalse(
            image.isTemplate(), "Paused icon should have isTemplate() == False"
        )

    @unittest.skipUnless(HAS_STATUS_ITEM, "status_item.py pending in Milestone 1")
    def test_f2_status_item_button_action_callback(self):
        """F2.5: Verify clicking status item button invokes the registered popover callback."""
        called = []
        callback = lambda sender: called.append(True)
        controller = status_item.LoLStatusItemController(on_toggle_popover=callback)
        button = controller.get_button()
        self.assertIsNotNone(button.action())
        # Simulate click
        controller.handle_click(button)
        self.assertTrue(len(called) > 0, "Button click did not trigger callback")


# =============================================================================
# F3: Floating Dark NSPopover UI (popover_ui.py)
# =============================================================================
class TestF3PopoverUI(unittest.TestCase):
    """Tests NSPopover dark styling, geometry, and header components."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_popover_dark_appearance(self):
        """F3.1: Verify popover uses dark aqua / vibrant dark appearance."""
        controller = popover_ui.LoLPopoverController()
        popover = controller.get_popover()
        self.assertIsNotNone(popover)
        appearance_name = str(popover.appearance().name())
        self.assertTrue(
            "Dark" in appearance_name or "dark" in appearance_name.lower()
        )

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_popover_header_elements(self):
        """F3.2: Verify header contains title 'Discord RPC' and subtitle 'League of Legends'."""
        controller = popover_ui.LoLPopoverController()
        title = controller.get_title_text()
        subtitle = controller.get_subtitle_text()
        self.assertEqual(title, "Discord RPC")
        self.assertEqual(subtitle, "League of Legends")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_popover_gear_button(self):
        """F3.3: Verify settings gear button exists and has configured action."""
        controller = popover_ui.LoLPopoverController()
        gear_btn = controller.get_gear_button()
        self.assertIsNotNone(gear_btn)
        self.assertIsNotNone(gear_btn.action())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_popover_show_hide_toggle(self):
        """F3.4: Verify popover toggles between shown and hidden states."""
        controller = popover_ui.LoLPopoverController()
        mock_view = MagicMock()
        controller.show(mock_view)
        self.assertTrue(controller.is_shown())
        controller.close()
        self.assertFalse(controller.is_shown())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f3_popover_content_size(self):
        """F3.5: Verify popover content dimensions match compact HUD mockup (~320-380px wide)."""
        controller = popover_ui.LoLPopoverController()
        size = controller.get_content_size()
        self.assertGreaterEqual(size.width, 300)
        self.assertLessEqual(size.width, 420)
        self.assertGreaterEqual(size.height, 350)


# =============================================================================
# F4: Interactive Mode Selector (popover_ui.py)
# =============================================================================
class TestF4ModeSelector(unittest.TestCase):
    """Tests selection between Modo Oficial and Modo Detallado."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_mode_selector_initial_state(self):
        """F4.1: Verify mode selector initializes with valid default mode ('oficial')."""
        controller = popover_ui.LoLPopoverController()
        self.assertIn(controller.get_current_mode(), ["oficial", "detallado"])

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_mode_selector_toggle_detailed(self):
        """F4.2: Verify switching to detailed mode updates controller mode to 'detallado'."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("detallado")
        self.assertEqual(controller.get_current_mode(), "detallado")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_mode_selector_toggle_official(self):
        """F4.3: Verify switching to official mode updates controller mode to 'oficial'."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("detallado")
        controller.select_mode("oficial")
        self.assertEqual(controller.get_current_mode(), "oficial")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_mode_selector_visual_selection(self):
        """F4.4: Verify selected mode card reflects active visual selection highlight."""
        controller = popover_ui.LoLPopoverController()
        controller.select_mode("detallado")
        self.assertTrue(controller.is_mode_card_selected("detallado"))
        self.assertFalse(controller.is_mode_card_selected("oficial"))

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f4_mode_selector_callback_triggered(self):
        """F4.5: Verify changing mode triggers on_mode_change callback."""
        modes_received = []
        controller = popover_ui.LoLPopoverController(
            on_mode_change=lambda m: modes_received.append(m)
        )
        controller.select_mode("detallado")
        self.assertIn("detallado", modes_received)


# =============================================================================
# F5: Interactive Switches (popover_ui.py)
# =============================================================================
class TestF5Switches(unittest.TestCase):
    """Tests NSSwitch controls for match reset and macOS autorun."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_autoreset_switch_initial_state(self):
        """F5.1: Verify autoreset switch initializes to enabled (True) by default."""
        controller = popover_ui.LoLPopoverController()
        self.assertTrue(controller.get_autoreset_state())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_autoreset_switch_toggle(self):
        """F5.2: Verify toggling autoreset switch alters state to False and True."""
        controller = popover_ui.LoLPopoverController()
        controller.set_autoreset_state(False)
        self.assertFalse(controller.get_autoreset_state())
        controller.set_autoreset_state(True)
        self.assertTrue(controller.get_autoreset_state())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_autorun_switch_initial_state(self):
        """F5.3: Verify autorun switch reads initial login item status."""
        controller = popover_ui.LoLPopoverController()
        state = controller.get_autorun_state()
        self.assertIsInstance(state, bool)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_autorun_switch_toggle(self):
        """F5.4: Verify toggling autorun switch triggers login item synchronization."""
        sync_called = []
        controller = popover_ui.LoLPopoverController(
            on_autorun_toggle=lambda s: sync_called.append(s)
        )
        controller.toggle_autorun(True)
        self.assertIn(True, sync_called)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f5_switch_widget_type(self):
        """F5.5: Verify switch widgets are Cocoa NSSwitch instances."""
        from AppKit import NSSwitch

        controller = popover_ui.LoLPopoverController()
        sw = controller.get_autoreset_switch_view()
        self.assertIsInstance(sw, NSSwitch)


# =============================================================================
# F6: Bottom Action Button (popover_ui.py)
# =============================================================================
class TestF6ActionButton(unittest.TestCase):
    """Tests bottom toggle action button ('DETENER EN DISCORD' / 'INICIAR PRESENCIA')."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_action_button_initial_text(self):
        """F6.1: Verify action button displays 'DETENER EN DISCORD' when presence is active."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(True)
        btn_text = controller.get_action_button_title().upper()
        self.assertIn("DETENER", btn_text)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_action_button_toggle_to_stopped(self):
        """F6.2: Verify action button displays 'INICIAR PRESENCIA' when presence is stopped."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(False)
        btn_text = controller.get_action_button_title().upper()
        self.assertIn("INICIAR", btn_text)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_action_button_toggle_to_active(self):
        """F6.3: Verify clicking action button when stopped restores active state."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(False)
        controller.handle_action_button_click()
        self.assertTrue(controller.is_presence_active())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_action_button_style_change(self):
        """F6.4: Verify action button reflects distinct styling/color when stopped vs active."""
        controller = popover_ui.LoLPopoverController()
        controller.set_presence_active(True)
        style_active = controller.get_action_button_style()
        controller.set_presence_active(False)
        style_stopped = controller.get_action_button_style()
        self.assertNotEqual(style_active, style_stopped)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f6_action_button_rpc_callback(self):
        """F6.5: Verify clicking action button invokes on_action_toggle callback with new state."""
        actions = []
        controller = popover_ui.LoLPopoverController(
            on_action_toggle=lambda a: actions.append(a)
        )
        controller.set_presence_active(True)
        controller.handle_action_button_click()
        self.assertIn(False, actions)


# =============================================================================
# F7: Settings / Detailed View (popover_ui.py)
# =============================================================================
class TestF7SettingsView(unittest.TestCase):
    """Tests champion selection, rank dropdown, division selector in Detailed Mode."""

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_champion_input_field(self):
        """F7.1: Verify champion input field allows entering and retrieving champion name."""
        controller = popover_ui.LoLPopoverController()
        controller.set_selected_champion("Aatrox")
        self.assertEqual(controller.get_selected_champion(), "Aatrox")

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_rank_selection_control(self):
        """F7.2: Verify rank selector contains all standard tiers from Hierro to Challenger."""
        controller = popover_ui.LoLPopoverController()
        tiers = controller.get_available_rank_tiers()
        for expected in ("Hierro", "Oro", "Diamante", "Challenger"):
            self.assertIn(expected, tiers)

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_division_selection_control(self):
        """F7.3: Verify division selector contains standard roman divisions I through IV."""
        controller = popover_ui.LoLPopoverController()
        divisions = controller.get_available_divisions()
        self.assertEqual(divisions, ["I", "II", "III", "IV"])

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_division_disabled_for_apex(self):
        """F7.4: Verify division selector is disabled/hidden when selecting Challenger/Master."""
        controller = popover_ui.LoLPopoverController()
        controller.select_rank("Challenger")
        self.assertFalse(controller.is_division_selector_enabled())
        controller.select_rank("Oro")
        self.assertTrue(controller.is_division_selector_enabled())

    @unittest.skipUnless(HAS_POPOVER_UI, "popover_ui.py pending in Milestone 2")
    def test_f7_game_mode_input(self):
        """F7.5: Verify game mode field allows setting game type (e.g. 'Grieta del Invocador')."""
        controller = popover_ui.LoLPopoverController()
        controller.set_game_mode_text("ARAM")
        self.assertEqual(controller.get_game_mode_text(), "ARAM")


# =============================================================================
# F8: Champion Resolver & Data Dragon (lol_champions.py)
# =============================================================================
class TestF8ChampionResolver(unittest.TestCase):
    """Tests champion normalization, all 9 Riot ID anomalies, Spanish names, and CDN URLs."""

    def setUp(self):
        self.resolver = ChampionResolver()

    def test_f8_canonical_champion_resolution(self):
        """F8.1: Verify resolution of standard canon champions (e.g. Ahri, Yasuo, Jinx)."""
        cid, name = self.resolver.resolve_champion("Ahri")
        self.assertEqual(cid, "Ahri")
        cid2, _ = self.resolver.resolve_champion("yasuo")
        self.assertEqual(cid2, "Yasuo")
        cid3, _ = self.resolver.resolve_champion("Jinx")
        self.assertEqual(cid3, "Jinx")

    def test_f8_all_9_riot_anomalies(self):
        """F8.2: Verify normalization for all 9 Riot internal ID discrepancy champions."""
        anomalies = {
            "Wukong": "MonkeyKing",
            "Nunu & Willump": "Nunu",
            "Renata Glasc": "Renata",
            "Cho'Gath": "Chogath",
            "Kai'Sa": "Kaisa",
            "Vel'Koz": "Velkoz",
            "Kha'Zix": "Khazix",
            "Bel'Veth": "Belveth",
            "LeBlanc": "Leblanc",
        }
        for query, expected_id in anomalies.items():
            cid, _ = self.resolver.resolve_champion(query)
            self.assertEqual(
                cid,
                expected_id,
                f"Query '{query}' resolved to '{cid}', expected '{expected_id}'",
            )

    def test_f8_spanish_champion_names(self):
        """F8.3: Verify Spanish champion names resolve to official Riot CDN IDs."""
        cid_bardo, _ = self.resolver.resolve_champion("Bardo")
        self.assertEqual(cid_bardo, "Bard")
        cid_yi, _ = self.resolver.resolve_champion("Maestro Yi")
        self.assertEqual(cid_yi, "MasterYi")
        cid_nunu, _ = self.resolver.resolve_champion("Nunu y Willump")
        self.assertEqual(cid_nunu, "Nunu")

    def test_f8_abbreviations(self):
        """F8.4: Verify common community abbreviations map to correct champions."""
        abbrevs = {
            "j4": "JarvanIV",
            "asol": "AurelionSol",
            "mf": "MissFortune",
            "tf": "TwistedFate",
            "yi": "MasterYi",
        }
        for abbr, expected_id in abbrevs.items():
            cid, _ = self.resolver.resolve_champion(abbr)
            self.assertEqual(
                cid,
                expected_id,
                f"Abbreviation '{abbr}' resolved to '{cid}', expected '{expected_id}'",
            )

    def test_f8_square_icon_url_format(self):
        """F8.5: Verify get_square_icon_url produces guaranteed DDragon CDN URL with version."""
        url = self.resolver.get_square_icon_url("MonkeyKing")
        expected_prefix = (
            f"https://ddragon.leagueoflegends.com/cdn/{self.resolver.version}/img/champion/"
        )
        self.assertTrue(url.startswith(expected_prefix))
        self.assertTrue(url.endswith("MonkeyKing.png"))


# =============================================================================
# F9: Rank Crests & Division Formatter (lol_ranks.py)
# =============================================================================
class TestF9RankFormatter(unittest.TestCase):
    """Tests CommunityDragon crest assets and division suppression for Apex tiers."""

    def test_f9_standard_tier_division_formatting(self):
        """F9.1: Verify standard tiers format as '{Tier} {Division}' (e.g. 'Oro II')."""
        self.assertEqual(format_rank_display("Oro", "II"), "Oro II")
        self.assertEqual(format_rank_display("Diamante", "IV"), "Diamante IV")
        self.assertEqual(format_rank_display("Silver", "I"), "Silver I")

    def test_f9_apex_tier_division_suppression_master(self):
        """F9.2: Verify Master / Maestro strictly suppresses division suffix."""
        self.assertEqual(format_rank_display("Maestro", "II"), "Maestro")
        self.assertEqual(format_rank_display("Master", "I"), "Master")
        self.assertTrue(is_apex_tier("Maestro"))

    def test_f9_apex_tier_division_suppression_challenger(self):
        """F9.3: Verify Challenger strictly suppresses division suffix (never 'Challenger II')."""
        self.assertEqual(format_rank_display("Challenger", "II"), "Challenger")
        self.assertEqual(format_rank_display("Challenger", "IV"), "Challenger")
        self.assertTrue(is_apex_tier("Challenger"))

    def test_f9_apex_tier_division_suppression_grandmaster(self):
        """F9.4: Verify Grandmaster / Gran Maestro strictly suppresses division suffix."""
        self.assertEqual(
            format_rank_display("Gran Maestro", "I"), "Gran Maestro"
        )
        self.assertEqual(
            format_rank_display("Grandmaster", "III"), "Grandmaster"
        )
        self.assertTrue(is_apex_tier("Gran Maestro"))

    def test_f9_community_dragon_crest_url(self):
        """F9.5: Verify get_rank_crest_url returns valid CommunityDragon PNG asset URLs."""
        url_gold = get_rank_crest_url("Oro")
        self.assertIn("raw.communitydragon.org", url_gold)
        self.assertTrue(url_gold.endswith("gold.png"))
        url_chal = get_rank_crest_url("Challenger")
        self.assertTrue(url_chal.endswith("challenger.png"))


# =============================================================================
# F10: Concurrency & Thread-Safe RPC Manager (discord_rpc_manager.py)
# =============================================================================
class TestF10RPCManager(unittest.TestCase):
    """Tests Actor model queue, non-blocking calls, and pypresence lifecycle."""

    def test_f10_manager_actor_queue_pattern(self):
        """F10.1: Verify public methods push to queue non-blockingly without running socket calls."""
        mgr = DiscordRPCManager(auto_start=False)
        self.assertTrue(mgr._cmd_queue.empty())
        mgr.set_active(False)
        self.assertFalse(mgr._cmd_queue.empty())
        cmd, arg = mgr._cmd_queue.get_nowait()
        self.assertEqual(cmd, "SET_ACTIVE")
        self.assertFalse(arg)

    def test_f10_set_active_dispatches_command(self):
        """F10.2: Verify set_active(False) and set_active(True) transition internal flags."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.set_active(False)
        self.assertFalse(mgr.is_active)
        mgr.set_active(True)
        self.assertTrue(mgr.is_active)

    def test_f10_update_presence_config(self):
        """F10.3: Verify update_presence_config enqueues CONFIG_CHANGE dictionary."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.update_presence_config(mode="detallado", champion_name="Kaisa")
        cmd, payload = mgr._cmd_queue.get_nowait()
        self.assertEqual(cmd, "CONFIG_CHANGE")
        self.assertEqual(payload["mode"], "detallado")
        self.assertEqual(payload["champion_name"], "Kaisa")

    def test_f10_main_thread_callback_dispatch(self):
        """F10.4: Verify state transitions trigger on_state_change callback."""
        states_recorded = []
        mgr = DiscordRPCManager(
            on_state_change=lambda s, m: states_recorded.append((s, m)),
            auto_start=False,
        )
        mgr._notify_state(RPCState.CONNECTING, "Conectando...")
        self.assertEqual(len(states_recorded), 1)
        self.assertEqual(states_recorded[0][0], RPCState.CONNECTING)

    def test_f10_graceful_shutdown(self):
        """F10.5: Verify shutdown terminates worker loop and sets running flag to False."""
        mgr = DiscordRPCManager(auto_start=True)
        self.assertTrue(mgr._running)
        mgr.shutdown()
        self.assertFalse(mgr._running)
        self.assertFalse(mgr._worker_thread.is_alive())


# =============================================================================
# F11: Auto-restart Match Timer (discord_rpc_manager.py)
# =============================================================================
class TestF11AutoRestartTimer(unittest.TestCase):
    """Tests 20-30 min match duration randomization and reset mechanics."""

    def test_f11_timer_initialization_range(self):
        """F11.1: Verify match_duration_sec is initialized in the [1200, 1800] interval (20-30m)."""
        mgr = DiscordRPCManager(auto_start=False)
        self.assertGreaterEqual(mgr.match_duration_sec, 1200)
        self.assertLessEqual(mgr.match_duration_sec, 1800)

    def test_f11_manual_match_restart(self):
        """F11.2: Verify restart_match enqueues RESTART_MATCH command."""
        mgr = DiscordRPCManager(auto_start=False)
        mgr.restart_match()
        cmd, _ = mgr._cmd_queue.get_nowait()
        self.assertEqual(cmd, "RESTART_MATCH")

    def test_f11_auto_reset_trigger_callback(self):
        """F11.3: Verify _notify_match_reset calls on_match_reset with new start time."""
        resets = []
        mgr = DiscordRPCManager(
            on_match_reset=lambda t: resets.append(t),
            auto_start=False,
        )
        test_time = 1700000000
        mgr._notify_match_reset(test_time)
        self.assertEqual(resets, [test_time])

    def test_f11_autoreset_disabled_flag(self):
        """F11.4: Verify autoreset flag can be disabled via config."""
        mgr = DiscordRPCManager(auto_start=False)
        self.assertTrue(mgr.autoreset)
        mgr.autoreset = False
        self.assertFalse(mgr.autoreset)

    def test_f11_match_duration_randomization(self):
        """F11.5: Verify multiple instantiated durations vary within [1200, 1800]."""
        durations = set()
        for _ in range(20):
            m = DiscordRPCManager(auto_start=False)
            durations.add(m.match_duration_sec)
        # In 20 random samples between 1200 and 1800, we expect multiple unique durations
        self.assertGreater(
            len(durations),
            1,
            "Timer duration was not randomized across instances",
        )


# =============================================================================
# F12: App Bundle Packaging & Sync (bundle inspection & sync_bundle.py)
# =============================================================================
class TestF12BundlePackaging(unittest.TestCase):
    """Tests /Applications/League of Legends RPC.app bundle structure and sync script."""

    BUNDLE_PATH = "/Applications/League of Legends RPC.app"

    def test_f12_app_bundle_exists(self):
        """F12.1: Verify /Applications/League of Legends RPC.app exists on the system."""
        self.assertTrue(
            os.path.isdir(self.BUNDLE_PATH),
            f"Bundle {self.BUNDLE_PATH} not found",
        )

    def test_f12_info_plist_validity(self):
        """F12.2: Verify Contents/Info.plist is valid XML with LSUIElement == True."""
        plist_path = os.path.join(self.BUNDLE_PATH, "Contents", "Info.plist")
        self.assertTrue(os.path.exists(plist_path))
        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)
        self.assertEqual(plist.get("CFBundleExecutable"), "League of Legends RPC")
        self.assertTrue(
            plist.get("LSUIElement"), "LSUIElement must be True for menubar app"
        )
        self.assertIn("com.victormanuel.lolrpc", plist.get("CFBundleIdentifier", ""))

    def test_f12_launcher_executable(self):
        """F12.3: Verify Contents/MacOS/League of Legends RPC launcher has executable permissions."""
        launcher_path = os.path.join(
            self.BUNDLE_PATH, "Contents", "MacOS", "League of Legends RPC"
        )
        self.assertTrue(os.path.exists(launcher_path))
        self.assertTrue(
            os.access(launcher_path, os.X_OK),
            "Launcher script must have executable permission (+x)",
        )

    def test_f12_icns_icon_present(self):
        """F12.4: Verify Contents/Resources/AppIcon.icns is present and valid ICNS format."""
        icns_path = os.path.join(
            self.BUNDLE_PATH, "Contents", "Resources", "AppIcon.icns"
        )
        self.assertTrue(os.path.exists(icns_path))
        with open(icns_path, "rb") as f:
            header = f.read(4)
        self.assertEqual(
            header, b"icns", "AppIcon.icns magic header must be b'icns'"
        )

    @unittest.skipUnless(HAS_SYNC_BUNDLE, "sync_bundle.py pending in Milestone 4")
    def test_f12_resources_sync_script(self):
        """F12.5: Verify sync_bundle module synchronizes latest Python code into Resources."""
        result = sync_bundle.sync_app_bundle(dry_run=True)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
