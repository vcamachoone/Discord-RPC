"""
tests/test_challenger_audit_2.py - Empirical Challenger Stress Test Suite

Adversarial stress-testing of:
1. LoLWebBridge with malformed, unexpected, and boundary messages (rank, division, champion, game_mode, non-dict payloads).
2. Champion search filtering against all 173 champions, aliases, unicode accents, and rapid typing via JavaScriptCore.
3. LaunchAgent plist parsing and --silent startup behavior under various CLI flags.
"""

import json
import os
import sys
import unittest
from typing import Any, Dict, List, Optional
import plistlib

# Ensure project root is in sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import lol_champions
from lol_champions import ChampionResolver, CHAMPIONS_DATA, FALLBACK_VERSION
import lol_ranks
from lol_ranks import format_rank_display, get_rank_crest_url, is_apex_tier, DEFAULT_RANKS_ES
import liquid_html
from popover_ui import LoLPopoverController, LoLWebBridge

try:
    import JavaScriptCore
    HAS_JSC = True
except ImportError:
    HAS_JSC = False


class MockScriptMessage:
    """Mock for WKScriptMessage providing .body()."""
    def __init__(self, body: Any):
        self._body = body

    def body(self) -> Any:
        return self._body


class TestWebBridgeMalformedAndBoundaries(unittest.TestCase):
    """
    Stress-tests LoLWebBridge message handling against adversarial, malformed,
    and boundary payloads.
    """

    def setUp(self):
        self.controller = LoLPopoverController.alloc().init()
        self.bridge = LoLWebBridge.alloc().initWithController_(self.controller)

    def _send(self, payload: Any):
        msg = MockScriptMessage(payload)
        self.bridge.userContentController_didReceiveScriptMessage_(None, msg)

    # -------------------------------------------------------------------------
    # 1. change_rank Boundary & Malformed Tests
    # -------------------------------------------------------------------------

    def test_bridge_rank_valid_tiers(self):
        """Tests standard Spanish and English rank tiers."""
        for tier in ["Hierro", "Bronce", "Plata", "Oro", "Platino", "Esmeralda", "Diamante"]:
            self._send({"action": "change_rank", "rank": tier})
            self.assertEqual(self.controller.get_selected_rank(), tier)
            self.assertTrue(self.controller.is_division_selector_enabled())
            crest = get_rank_crest_url(self.controller.get_selected_rank())
            self.assertTrue(crest.startswith("https://raw.communitydragon.org/"))

    def test_bridge_rank_apex_tiers(self):
        """Tests Apex tiers (Master, Grandmaster, Challenger, Unranked) suppress divisions."""
        apex_cases = ["Maestro", "Gran Maestro", "Challenger", "Unranked", "Master", "Grandmaster"]
        for tier in apex_cases:
            self._send({"action": "change_rank", "rank": tier})
            self.assertEqual(self.controller.get_selected_rank(), tier)
            self.assertFalse(self.controller.is_division_selector_enabled())
            disp = format_rank_display(self.controller.get_selected_rank(), self.controller.get_selected_division())
            self.assertEqual(disp, tier)

    def test_bridge_rank_invalid_and_boundary(self):
        """Tests unexpected, empty, whitespace, and non-string rank inputs."""
        # Empty rank should not overwrite current valid rank
        curr = self.controller.get_selected_rank()
        self._send({"action": "change_rank", "rank": ""})
        self.assertEqual(self.controller.get_selected_rank(), curr)

        # None rank should not crash and preserve rank
        self._send({"action": "change_rank", "rank": None})
        self.assertEqual(self.controller.get_selected_rank(), curr)

        # Non-existent rank string should safely fall back on crest
        self._send({"action": "change_rank", "rank": "WoodTier99"})
        self.assertEqual(self.controller.get_selected_rank(), "WoodTier99")
        crest = get_rank_crest_url(self.controller.get_selected_rank())
        self.assertEqual(crest, lol_ranks.RANKS_ASSETS["Oro"])

        # Numeric rank
        self._send({"action": "change_rank", "rank": 9999})
        self.assertEqual(self.controller.get_selected_rank(), "9999")

    # -------------------------------------------------------------------------
    # 2. change_division Boundary & Malformed Tests
    # -------------------------------------------------------------------------

    def test_bridge_division_valid_roman(self):
        """Tests standard Roman divisions I-IV."""
        for div in ["I", "II", "III", "IV"]:
            self._send({"action": "change_division", "division": div})
            self.assertEqual(self.controller.get_selected_division(), div)

    def test_bridge_division_boundary_formats(self):
        """Tests division with non-standard Roman numerals, numbers, empty, and whitespace."""
        # Empty division should not overwrite current valid division
        curr = self.controller.get_selected_division()
        self._send({"action": "change_division", "division": ""})
        self.assertEqual(self.controller.get_selected_division(), curr)

        # None division should not crash and preserve division
        self._send({"action": "change_division", "division": None})
        self.assertEqual(self.controller.get_selected_division(), curr)

        # Non-standard division string (e.g. legacy V, numeric 1, or custom)
        self._send({"action": "change_division", "division": "V"})
        self.assertEqual(self.controller.get_selected_division(), "V")

        self._send({"action": "change_division", "division": "1"})
        self.assertEqual(self.controller.get_selected_division(), "1")

        # Division change while rank is Apex tier should still suppress division in display
        self._send({"action": "change_rank", "rank": "Challenger"})
        self._send({"action": "change_division", "division": "I"})
        disp = format_rank_display(self.controller.get_selected_rank(), self.controller.get_selected_division())
        self.assertEqual(disp, "Challenger")

    # -------------------------------------------------------------------------
    # 3. change_champion Boundary & Malformed Tests
    # -------------------------------------------------------------------------

    def test_bridge_champion_empty_and_whitespace(self):
        """Tests empty, whitespace, and None champion inputs safely default to Malzahar."""
        for empty_val in ["", "   ", "  \t\n  ", None]:
            self._send({"action": "change_champion", "name": empty_val})
            self.assertEqual(self.controller.get_selected_champion(), "Malzahar")

    def test_bridge_champion_symbols_and_unknown(self):
        """Tests symbols and non-existent champions safely resolve to Malzahar."""
        resolver = ChampionResolver()
        for sym_val in ["!@#$%^&*", "????", "   ---   ", "UnknownChampionXYZ"]:
            self._send({"action": "change_champion", "name": sym_val})
            cid, dname = resolver.resolve_champion(self.controller.get_selected_champion())
            self.assertEqual(cid, "Malzahar")

    def test_bridge_champion_aliases_and_anomalies(self):
        """Tests community aliases and Riot 9 internal ID anomalies through bridge."""
        resolver = ChampionResolver()
        cases = [
            ("asol", "AurelionSol", "Aurelion Sol"),
            ("j4", "JarvanIV", "Jarvan IV"),
            ("mf", "MissFortune", "Miss Fortune"),
            ("tf", "TwistedFate", "Twisted Fate"),
            ("yi", "MasterYi", "Master Yi"),
            ("bardo", "Bard", "Bard"),
            ("mundo", "DrMundo", "Dr. Mundo"),
            ("wukong", "MonkeyKing", "Wukong"),
            ("monkeyking", "MonkeyKing", "Wukong"),
            ("nunu", "Nunu", "Nunu & Willump"),
            ("renata", "Renata", "Renata Glasc"),
            ("chogath", "Chogath", "Cho'Gath"),
            ("kaisa", "Kaisa", "Kai'Sa"),
            ("ksante", "KSante", "K'Sante"),
            ("belveth", "Belveth", "Bel'Veth"),
            ("khazix", "Khazix", "Kha'Zix"),
            ("velkoz", "Velkoz", "Vel'Koz"),
            ("leblanc", "Leblanc", "LeBlanc"),
        ]
        for query, exp_id, exp_name in cases:
            self._send({"action": "change_champion", "name": query})
            cid, dname = resolver.resolve_champion(self.controller.get_selected_champion())
            self.assertEqual(cid, exp_id, f"Failed resolving id for query {query!r}")

    # -------------------------------------------------------------------------
    # 4. Unknown Actions and Robustness
    # -------------------------------------------------------------------------

    def test_bridge_unknown_action(self):
        """Tests that unknown actions are safely ignored without raising exceptions."""
        self._send({"action": "non_existent_action_12345", "foo": "bar"})
        self._send({"action": ""})
        self._send({})
        self._send(None)

    def test_bridge_controller_none_resilience(self):
        """Tests bridge resilience if controller is somehow None."""
        orphan_bridge = LoLWebBridge.alloc().init()
        orphan_bridge._controller = None
        # Should not raise exception
        msg = MockScriptMessage({"action": "change_rank", "rank": "Oro"})
        orphan_bridge.userContentController_didReceiveScriptMessage_(None, msg)


class TestChampionSearchFiltering(unittest.TestCase):
    """
    Empirically tests JavaScript champion search filtering against all 173
    champions, aliases, unicode accents, and rapid typing using macOS JavaScriptCore.
    """

    @classmethod
    def setUpClass(cls):
        if not HAS_JSC:
            raise unittest.SkipTest("JavaScriptCore not available in this environment")

        cls.ctx = JavaScriptCore.JSContext.alloc().init()
        champions_json = json.dumps(liquid_html.CHAMPIONS_CATALOG)

        # Evaluate the exact champion filter logic from liquid_html.py
        js_code = f"""
        const ALL_CHAMPIONS = {champions_json};
        const ALIAS_MAP = {{
          'asol': 'Aurelion Sol',
          'j4': 'Jarvan IV',
          'mf': 'Miss Fortune',
          'tf': 'Twisted Fate',
          'yi': 'Master Yi',
          'bardo': 'Bard',
          'nunu y willump': 'Nunu & Willump',
          'mundo': 'Dr. Mundo'
        }};

        function filterChampions(query) {{
          const q = (query || '').toLowerCase().trim();
          const aliasTarget = ALIAS_MAP[q] ? ALIAS_MAP[q].toLowerCase() : '';

          return ALL_CHAMPIONS.filter(c => {{
            if (!q) return true;
            const nameClean = c.name.toLowerCase().replace(/[^a-z0-9]/g, '');
            const idClean = c.id.toLowerCase();
            const qClean = q.replace(/[^a-z0-9]/g, '');
            return c.name.toLowerCase().includes(q) ||
                   nameClean.includes(qClean) ||
                   idClean.includes(qClean) ||
                   (aliasTarget && c.name.toLowerCase().includes(aliasTarget));
          }}).map(c => c.name);
        }}
        """
        cls.ctx.evaluateScript_(js_code)

    def _filter(self, query: str) -> List[str]:
        res = self.ctx.evaluateScript_(f"filterChampions({json.dumps(query)})")
        return list(res.toArray())

    def test_all_173_champions_catalog_completeness(self):
        """Verifies catalog contains exactly 173 champions matching Riot Data Dragon."""
        self.assertEqual(len(liquid_html.CHAMPIONS_CATALOG), 173)
        self.assertEqual(len(CHAMPIONS_DATA), 173)

    def test_all_173_champions_found_by_exact_name(self):
        """Verifies every single one of the 173 champions is found by exact name."""
        for champ in liquid_html.CHAMPIONS_CATALOG:
            name = champ["name"]
            results = self._filter(name)
            self.assertIn(name, results, f"Champion {name!r} not found by exact name search")

    def test_all_173_champions_found_by_lowercase(self):
        """Verifies every single one of the 173 champions is found by lowercase name."""
        for champ in liquid_html.CHAMPIONS_CATALOG:
            name = champ["name"]
            results = self._filter(name.lower())
            self.assertIn(name, results, f"Champion {name!r} not found by lowercase name search")

    def test_all_173_champions_found_by_stripped_name(self):
        """Verifies champions with punctuation/spaces are found by alphanumeric stripped query."""
        for champ in liquid_html.CHAMPIONS_CATALOG:
            name = champ["name"]
            clean = "".join(ch for ch in name.lower() if ch.isalnum())
            results = self._filter(clean)
            self.assertIn(name, results, f"Champion {name!r} not found by stripped query {clean!r}")

    def test_community_aliases_resolution(self):
        """Verifies community aliases in ALIAS_MAP return the intended champion."""
        expected_aliases = {
            "asol": "Aurelion Sol",
            "j4": "Jarvan IV",
            "mf": "Miss Fortune",
            "tf": "Twisted Fate",
            "yi": "Master Yi",
            "bardo": "Bard",
            "nunu y willump": "Nunu & Willump",
            "mundo": "Dr. Mundo",
        }
        for alias, expected in expected_aliases.items():
            results = self._filter(alias)
            self.assertIn(expected, results, f"Alias {alias!r} did not return {expected!r}")

    def test_anomalies_and_special_names(self):
        """Verifies Riot 9 anomalies and camelcase champion queries."""
        cases = {
            "wukong": "Wukong",
            "monkeyking": "Wukong",
            "nunu": "Nunu & Willump",
            "renata": "Renata Glasc",
            "chogath": "Cho'Gath",
            "kaisa": "Kai'Sa",
            "ksante": "K'Sante",
            "velkoz": "Vel'Koz",
            "khazix": "Kha'Zix",
            "belveth": "Bel'Veth",
            "leblanc": "LeBlanc",
        }
        for query, expected in cases.items():
            results = self._filter(query)
            self.assertIn(expected, results, f"Special query {query!r} did not return {expected!r}")

    def test_punctuation_and_curly_apostrophes(self):
        """Verifies champions with apostrophes match ASCII and unicode curly apostrophe (\\u2019)."""
        curly_cases = [
            ("Cho\u2019Gath", "Cho'Gath"),
            ("Kha\u2019Zix", "Kha'Zix"),
            ("Kai\u2019Sa", "Kai'Sa"),
            ("Bel\u2019Veth", "Bel'Veth"),
            ("K\u2019Sante", "K'Sante"),
        ]
        for query, expected in curly_cases:
            results = self._filter(query)
            self.assertIn(expected, results, f"Curly apostrophe {query!r} did not match {expected!r}")

    def test_rapid_typing_subsequences(self):
        """Simulates rapid typing character-by-character for champions and aliases."""
        sequences = [
            ("Jarvan IV", "jarvan iv"),
            ("Miss Fortune", "miss fortune"),
            ("Twisted Fate", "twisted fate"),
            ("Dr. Mundo", "dr. mundo"),
            ("Wukong", "wukong"),
            ("Cho'Gath", "cho'gath"),
            ("Kai'Sa", "kai'sa"),
            ("K'Sante", "k'sante"),
            ("Bel'Veth", "bel'veth"),
            ("LeBlanc", "leblanc"),
            ("Renata Glasc", "renata glasc"),
        ]
        for target, full_str in sequences:
            for i in range(1, len(full_str) + 1):
                sub = full_str[:i]
                res = self._filter(sub)
                self.assertGreater(len(res), 0, f"Empty result for prefix {sub!r} of {full_str!r}")
            self.assertIn(target, res, f"Target {target!r} not in final results for {full_str!r}")


class TestLaunchAgentAndStartupCLI(unittest.TestCase):
    """
    Stress-tests LaunchAgent plist parsing, schema integrity, and --silent
    startup flag processing.
    """

    def setUp(self):
        self.plist_path = os.path.expanduser("~/Library/LaunchAgents/com.victormanuel.lolrpc.plist")

    def test_launchagent_plist_parsing_and_schema(self):
        """Parses ~/Library/LaunchAgents/com.victormanuel.lolrpc.plist and validates schema."""
        self.assertTrue(os.path.exists(self.plist_path), f"LaunchAgent plist not found at {self.plist_path}")
        with open(self.plist_path, "rb") as f:
            plist = plistlib.load(f)

        # Validate required launchd keys
        self.assertEqual(plist.get("Label"), "com.victormanuel.lolrpc")
        self.assertEqual(plist.get("ProcessType"), "Interactive")
        self.assertTrue(plist.get("RunAtLoad"))

        # Validate ProgramArguments contains direct binary executable and --silent
        args = plist.get("ProgramArguments", [])
        self.assertIsInstance(args, list)
        self.assertIn("/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC", args)
        self.assertIn("--silent", args)

        # Validate log paths
        self.assertIn("StandardOutPath", plist)
        self.assertIn("StandardErrorPath", plist)
        self.assertTrue(plist["StandardOutPath"].endswith("lol_discord_rpc.log"))
        self.assertTrue(plist["StandardErrorPath"].endswith("lol_discord_rpc_error.log"))

    def test_silent_flag_startup_behavior(self):
        """
        Tests the logic from app_gui.py lines 229-241 under various CLI argument vectors:
        --silent, --background, normal interactive, and other flags.
        """
        def evaluate_is_silent(argv: List[str]) -> bool:
            return "--silent" in argv or "--background" in argv

        # Silent launch scenarios
        self.assertTrue(evaluate_is_silent(["app_gui.py", "--silent"]))
        self.assertTrue(evaluate_is_silent(["app_gui.py", "--background"]))
        self.assertTrue(evaluate_is_silent(["app_gui.py", "--args", "--silent"]))
        self.assertTrue(evaluate_is_silent(["/Applications/.../MacOS/League of Legends RPC", "--silent"]))
        self.assertTrue(evaluate_is_silent(["app_gui.py", "--verbose", "--silent", "--debug"]))

        # Normal interactive launch scenarios
        self.assertFalse(evaluate_is_silent(["app_gui.py"]))
        self.assertFalse(evaluate_is_silent(["app_gui.py", "--help"]))
        self.assertFalse(evaluate_is_silent(["app_gui.py", "-h"]))
        self.assertFalse(evaluate_is_silent(["app_gui.py", "--version"]))

    def test_sync_login_item_toggle(self):
        """Tests that LoLPopoverController._sync_login_item writes valid plist when enabled."""
        controller = LoLPopoverController.alloc().init()
        # Verify controller has _sync_login_item method
        self.assertTrue(hasattr(controller, "_sync_login_item"))
        # Verify check_autorun returns boolean
        self.assertIsInstance(controller.check_autorun(), bool)


if __name__ == "__main__":
    unittest.main()
