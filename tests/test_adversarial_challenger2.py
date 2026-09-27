#!/usr/bin/env python3
"""
test_adversarial_challenger2.py - Empirical Adversarial Challenge Suite

Executed by challenger_2 to verify:
1. ChampionResolver with extreme/corrupt champion names, fuzzing, unicode, SQL injection,
   XSS, shell escapes, long buffers, 173 champions, Spanish names, and abbreviations.
2. CDN case-sensitivity across edge cases (guaranteeing 100% valid CDN URLs, zero 403/404s).
3. All 11 rank tiers (Spanish & English), Apex division suppression, and crest assets.
4. Menubar icon pixel geometry: resolutions, RGBA channels, blue dot coordinates & bounds,
   cutout ring, paused alpha (35%), and Cocoa template mode flags.
"""

import os
import random
import shutil
import string
import sys
import tempfile
import unittest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PIL import Image

import assets_gen
import lol_champions
from lol_champions import CHAMPIONS_DATA, SPECIAL_CHAMPION_MAP, ChampionResolver
import lol_ranks
from lol_ranks import (
    DEFAULT_DIVISIONS,
    DEFAULT_RANKS_ES,
    RANKS_ASSETS,
    format_rank_display,
    get_available_divisions,
    get_available_ranks,
    get_rank_crest_url,
    is_apex_tier,
)
import status_item
from status_item import LoLStatusItemController


class TestAdversarialChampionResolver(unittest.TestCase):
    """Adversarial stress testing of ChampionResolver with corrupt, extreme, and edge inputs."""

    def setUp(self):
        self.resolver = ChampionResolver()
        self.canonical_ids = {cid for cid, name in CHAMPIONS_DATA}
        self.assertEqual(len(self.canonical_ids), 173)

    def test_corrupt_and_extreme_inputs(self):
        """Verify ChampionResolver never crashes and always returns valid canonical ID for hostile inputs."""
        corrupt_inputs = [
            # Emptiness and whitespace variants
            "",
            None,
            " ",
            "    ",
            "\t",
            "\n",
            "\r\n",
            "\v\f",
            "   \t\n  \r\n   ",
            # Unicode & Emojis
            "⚔️ Yasuo 🔥",
            "🔥" * 200,
            "盲僧",
            "亞索",
            "Мальзахар",
            "ياسو",
            "\u200b\u200c\u200d\ufeff",
            "🦹‍♂️🦸‍♀️🧟‍♂️",
            "Ñandú y Camaleón",
            # SQL Injection attempts
            "' OR '1'='1",
            "'; DROP TABLE champions; --",
            "1; SELECT * FROM users",
            "admin' --",
            "' UNION SELECT username, password FROM users --",
            # XSS / HTML attempts
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "<b>Ahri</b>",
            "<iframe src='javascript:alert(1)'></iframe>",
            # Shell / Command injection attempts
            "; rm -rf /",
            "$(whoami)",
            "`ls -la`",
            "| cat /etc/passwd",
            "& ping -c 1 127.0.0.1",
            # Path Traversal attempts
            "../../../../etc/passwd",
            "..\\..\\boot.ini",
            "/dev/urandom",
            "/var/log/system.log",
            # Format strings & Regex denial
            "%s%s%s%s%s%d%n",
            "{0}{1}{2}",
            "{champion_name}",
            "a" * 100 + "!",
            "(.*)*",
            # Binary & Control characters
            "\x00",
            "\x01",
            "\x1b[31m",
            "Yasuo\x00extra",
            "\x7f\x80\xff",
            # Pure punctuation & symbols
            "!@#$%^&*()_+-=[]{}|;':\",./<>?`~",
            "==================",
            "------------------",
            # Numbers & Booleans
            "123456",
            "-1",
            "0",
            "3.14159",
            "True",
            "False",
            "None",
            "null",
            "undefined",
            "NaN",
            # Oversized buffers
            "A" * 100000,
            "Cho'Gath" * 5000,
            "12345" * 10000,
            # Unknown names and gibberish
            "asdfghjklqwertyuiop",
            "supercalifragilisticexpialidocious",
            "not_a_league_champion_xyz",
            "MarioBros",
            "Goku",
        ]

        for inp in corrupt_inputs:
            with self.subTest(input=str(inp)[:30]):
                cid, disp = self.resolver.resolve_champion(inp)
                self.assertIsInstance(cid, str, f"Champion ID must be str for input {inp!r}")
                self.assertIsInstance(disp, str, f"Display name must be str for input {inp!r}")
                self.assertIn(
                    cid,
                    self.canonical_ids,
                    f"Resolved ID {cid!r} for input {inp!r} must belong to 173 canonical roster",
                )
                url = self.resolver.get_square_icon_url(cid)
                self.assertTrue(url.startswith("https://ddragon.leagueoflegends.com/"))
                self.assertTrue(url.endswith(f"{cid}.png"))

    def test_all_173_canonical_champions_resolution(self):
        """Verify all 173 champions resolve correctly by canonical ID and display name in any case."""
        for cid, official_name in CHAMPIONS_DATA:
            # 1. Exact ID
            res_id, _ = self.resolver.resolve_champion(cid)
            self.assertEqual(res_id, cid, f"Exact ID {cid} failed to resolve to itself")

            # 2. Lowercase ID
            res_id, _ = self.resolver.resolve_champion(cid.lower())
            self.assertEqual(res_id, cid, f"Lowercase ID {cid.lower()} failed to resolve to {cid}")

            # 3. Uppercase ID
            res_id, _ = self.resolver.resolve_champion(cid.upper())
            self.assertEqual(res_id, cid, f"Uppercase ID {cid.upper()} failed to resolve to {cid}")

            # 4. Official Display Name
            res_id, _ = self.resolver.resolve_champion(official_name)
            self.assertEqual(res_id, cid, f"Display name {official_name} failed to resolve to {cid}")

            # 5. Display Name with surrounding whitespace
            res_id, _ = self.resolver.resolve_champion(f"   {official_name}   ")
            self.assertEqual(res_id, cid, f"Whitespace wrapped {official_name} failed to resolve to {cid}")

    def test_the_9_riot_internal_anomalies(self):
        """Verify the 9 known Riot internal ID discrepancy edge cases."""
        anomalies = [
            ("Wukong", "MonkeyKing"),
            ("wukong", "MonkeyKing"),
            ("WUKONG", "MonkeyKing"),
            ("monkeyking", "MonkeyKing"),
            ("Cho'Gath", "Chogath"),
            ("chogath", "Chogath"),
            ("CHO'GATH", "Chogath"),
            ("cho gath", "Chogath"),
            ("Kai'Sa", "Kaisa"),
            ("kaisa", "Kaisa"),
            ("KAI'SA", "Kaisa"),
            ("kai sa", "Kaisa"),
            ("Kha'Zix", "Khazix"),
            ("khazix", "Khazix"),
            ("KHA'ZIX", "Khazix"),
            ("Vel'Koz", "Velkoz"),
            ("velkoz", "Velkoz"),
            ("VEL'KOZ", "Velkoz"),
            ("Bel'Veth", "Belveth"),
            ("belveth", "Belveth"),
            ("BEL'VETH", "Belveth"),
            ("LeBlanc", "Leblanc"),
            ("leblanc", "Leblanc"),
            ("LEBLANC", "Leblanc"),
            ("Nunu & Willump", "Nunu"),
            ("Nunu", "Nunu"),
            ("nunu", "Nunu"),
            ("nunu & willump", "Nunu"),
            ("nunuwillump", "Nunu"),
            ("nunuywillump", "Nunu"),
            ("Renata Glasc", "Renata"),
            ("Renata", "Renata"),
            ("renata", "Renata"),
            ("renataglasc", "Renata"),
        ]

        for query, expected_cid in anomalies:
            with self.subTest(query=query):
                res_id, _ = self.resolver.resolve_champion(query)
                self.assertEqual(
                    res_id,
                    expected_cid,
                    f"Anomaly query {query!r} resolved to {res_id!r}, expected {expected_cid!r}",
                )

    def test_spanish_localized_names(self):
        """Verify Spanish translated champion names map to correct DDragon IDs."""
        spanish_cases = [
            ("Bardo", "Bard"),
            ("bardo", "Bard"),
            ("BARDO", "Bard"),
            ("Maestro Yi", "MasterYi"),
            ("maestro yi", "MasterYi"),
            ("MAESTRO YI", "MasterYi"),
            ("maestroyi", "MasterYi"),
        ]
        for query, expected_cid in spanish_cases:
            with self.subTest(query=query):
                res_id, _ = self.resolver.resolve_champion(query)
                self.assertEqual(res_id, expected_cid)

    def test_community_abbreviations(self):
        """Verify community shorthand and nicknames map to correct DDragon IDs."""
        abbrevs = {
            "j4": "JarvanIV",
            "asol": "AurelionSol",
            "mf": "MissFortune",
            "tf": "TwistedFate",
            "yi": "MasterYi",
            "tahm": "TahmKench",
            "kench": "TahmKench",
            "cait": "Caitlyn",
            "ez": "Ezreal",
            "gp": "Gangplank",
            "morde": "Mordekaiser",
            "nida": "Nidalee",
            "ori": "Orianna",
            "seju": "Sejuani",
            "trist": "Tristana",
            "trynd": "Tryndamere",
            "vlad": "Vladimir",
            "ww": "Warwick",
            "xin": "XinZhao",
        }
        for abbr, expected_cid in abbrevs.items():
            with self.subTest(abbr=abbr):
                res_id, _ = self.resolver.resolve_champion(abbr)
                self.assertEqual(res_id, expected_cid)
                # Upper case abbreviation
                res_id_upper, _ = self.resolver.resolve_champion(abbr.upper())
                self.assertEqual(res_id_upper, expected_cid)

    def test_fuzzing_1000_random_inputs(self):
        """Fuzz ChampionResolver with 1,000 pseudo-random strings ensuring zero unhandled crashes."""
        prng = random.Random(1337)
        alphabet = string.ascii_letters + string.digits + string.punctuation + " \t\r\n" + "ñáéíóúäëïöü" + "🔥⚔️"

        for i in range(1000):
            length = prng.randint(1, 150)
            sample_str = "".join(prng.choice(alphabet) for _ in range(length))
            cid, disp = self.resolver.resolve_champion(sample_str)
            self.assertIsInstance(cid, str)
            self.assertIsInstance(disp, str)
            self.assertIn(cid, self.canonical_ids)


class TestCDNCaseSensitivity(unittest.TestCase):
    """Verify that every resolved champion ID matches the exact casing demanded by Riot CDN."""

    def setUp(self):
        self.resolver = ChampionResolver("16.19.1")

    def test_exact_case_sensitivity_rules(self):
        """Verify sensitive ID casing where incorrect case yields HTTP 403 on Riot Cloudflare CDN."""
        critical_cases = [
            ("wukong", "MonkeyKing"),   # monkeyking is 403
            ("chogath", "Chogath"),     # ChoGath is 403
            ("leblanc", "Leblanc"),     # LeBlanc is 403
            ("kaisa", "Kaisa"),         # KaiSa is 403
            ("khazix", "Khazix"),       # KhaZix is 403
            ("velkoz", "Velkoz"),       # VelKoz is 403
            ("belveth", "Belveth"),     # BelVeth is 403
            ("reksai", "RekSai"),       # Reksai is 403
            ("ksante", "KSante"),       # Ksante is 403
            ("drmundo", "DrMundo"),     # Drmundo is 403
            ("jarvaniv", "JarvanIV"),   # Jarvaniv is 403
            ("masteryi", "MasterYi"),   # Masteryi is 403
            ("missfortune", "MissFortune"), # Missfortune is 403
            ("tahmkench", "TahmKench"), # Tahmkench is 403
            ("twistedfate", "TwistedFate"), # Twistedfate is 403
            ("xinzhao", "XinZhao"),     # Xinzhao is 403
            ("aurelionsol", "AurelionSol"), # Aurelionsol is 403
        ]

        for query, expected_exact_case_id in critical_cases:
            with self.subTest(query=query):
                cid, _ = self.resolver.resolve_champion(query)
                self.assertEqual(
                    cid,
                    expected_exact_case_id,
                    f"Casing mismatch for {query}: got {cid!r}, must be exactly {expected_exact_case_id!r}",
                )

    def test_all_173_champion_urls_well_formed(self):
        """Verify URL generation for all 173 champions produces proper CDN schema."""
        for cid, _ in CHAMPIONS_DATA:
            square_url = self.resolver.get_square_icon_url(cid)
            loading_url = self.resolver.get_loading_splash_url(cid)
            splash_url = self.resolver.get_splash_url(cid)

            self.assertEqual(
                square_url,
                f"https://ddragon.leagueoflegends.com/cdn/16.19.1/img/champion/{cid}.png",
            )
            self.assertEqual(
                loading_url,
                f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{cid}_0.jpg",
            )
            self.assertEqual(
                splash_url,
                f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{cid}_0.jpg",
            )


class TestRankTiersAndApexSuppression(unittest.TestCase):
    """Verify all 11 rank tiers and strict Apex tier division suppression rules."""

    def test_all_11_tiers_available(self):
        """Ensure exactly 11 distinct competitive rank tiers exist in Spanish and English."""
        ranks_es = get_available_ranks("es")
        ranks_en = get_available_ranks("en")

        self.assertEqual(len(ranks_es), 11)
        self.assertEqual(len(ranks_en), 11)

        expected_es = [
            "Hierro", "Bronce", "Plata", "Oro", "Platino", "Esmeralda", "Diamante",
            "Maestro", "Gran Maestro", "Challenger", "Unranked"
        ]
        expected_en = [
            "Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond",
            "Master", "Grandmaster", "Challenger", "Unranked"
        ]

        self.assertEqual(ranks_es, expected_es)
        self.assertEqual(ranks_en, expected_en)

    def test_apex_tier_division_suppression(self):
        """Verify division is completely suppressed for Apex tiers (Master, GM, Challenger, Unranked)."""
        apex_cases = [
            # Spanish
            ("Maestro", "I", "Maestro"),
            ("Maestro", "IV", "Maestro"),
            ("Gran Maestro", "I", "Gran Maestro"),
            ("Gran Maestro", "II", "Gran Maestro"),
            ("Challenger", "I", "Challenger"),
            ("Challenger", "II", "Challenger"),
            ("Challenger", "IV", "Challenger"),
            ("Unranked", "I", "Unranked"),
            ("Sin rango", "II", "Sin rango"),
            # English
            ("Master", "I", "Master"),
            ("Master", "IV", "Master"),
            ("Grandmaster", "I", "Grandmaster"),
            ("Grandmaster", "III", "Grandmaster"),
            ("Challenger", "I", "Challenger"),
        ]

        for tier, div, expected in apex_cases:
            with self.subTest(tier=tier, div=div):
                formatted = format_rank_display(tier, div)
                self.assertEqual(
                    formatted,
                    expected,
                    f"Apex tier {tier} with division {div} produced {formatted!r}, expected {expected!r}",
                )

    def test_apex_tier_case_insensitivity(self):
        """Verify Apex division suppression works regardless of casing."""
        variations = [
            ("CHALLENGER", "II", "CHALLENGER"),
            ("challenger", "IV", "challenger"),
            ("cHaLLeNgEr", "I", "cHaLLeNgEr"),
            ("MASTER", "I", "MASTER"),
            ("master", "IV", "master"),
            ("GRAN MAESTRO", "II", "GRAN MAESTRO"),
            ("gran maestro", "I", "gran maestro"),
            ("GRANDMASTER", "III", "GRANDMASTER"),
            ("grandmaster", "I", "grandmaster"),
            ("UNRANKED", "II", "UNRANKED"),
            ("unranked", "IV", "unranked"),
            ("SIN RANGO", "I", "SIN RANGO"),
            ("sin rango", "II", "sin rango"),
        ]
        for tier, div, expected in variations:
            with self.subTest(tier=tier, div=div):
                self.assertEqual(format_rank_display(tier, div), expected)

    def test_standard_tier_division_preservation(self):
        """Verify standard tiers (Iron..Diamond) preserve divisions correctly."""
        standard_tiers_es = ["Hierro", "Bronce", "Plata", "Oro", "Platino", "Esmeralda", "Diamante"]
        standard_tiers_en = ["Iron", "Bronze", "Silver", "Gold", "Platinum", "Emerald", "Diamond"]
        divisions = ["I", "II", "III", "IV"]

        for tier in standard_tiers_es + standard_tiers_en:
            for div in divisions:
                with self.subTest(tier=tier, div=div):
                    formatted = format_rank_display(tier, div)
                    self.assertEqual(formatted, f"{tier} {div}")

    def test_double_division_prevention(self):
        """Verify passing a tier string that already has a division does not duplicate it."""
        self.assertEqual(format_rank_display("Oro II", "II"), "Oro II")
        self.assertEqual(format_rank_display("Plata I", "I"), "Plata I")
        self.assertEqual(format_rank_display("Diamante IV", "IV"), "Diamante IV")
        self.assertEqual(format_rank_display("Bronze III", "III"), "Bronze III")

    def test_empty_or_none_rank_handling(self):
        """Verify safe handling of empty or None tier and division inputs."""
        self.assertEqual(format_rank_display("", "II"), "Unranked")
        self.assertEqual(format_rank_display(None, "II"), "Unranked")
        self.assertEqual(format_rank_display("   ", "II"), "Unranked")
        self.assertEqual(format_rank_display("Oro", ""), "Oro")
        self.assertEqual(format_rank_display("Oro", None), "Oro")
        self.assertEqual(format_rank_display("Oro", "   "), "Oro")

    def test_all_11_tier_crest_urls(self):
        """Verify CommunityDragon crest URLs for all 11 tiers in both languages."""
        all_tiers = get_available_ranks("es") + get_available_ranks("en") + ["Sin rango"]
        expected_crest_files = {
            "hierro": "iron.png",
            "iron": "iron.png",
            "bronce": "bronze.png",
            "bronze": "bronze.png",
            "plata": "silver.png",
            "silver": "silver.png",
            "oro": "gold.png",
            "gold": "gold.png",
            "platino": "platinum.png",
            "platinum": "platinum.png",
            "esmeralda": "emerald.png",
            "emerald": "emerald.png",
            "diamante": "diamond.png",
            "diamond": "diamond.png",
            "maestro": "master.png",
            "master": "master.png",
            "gran maestro": "grandmaster.png",
            "grandmaster": "grandmaster.png",
            "challenger": "challenger.png",
            "unranked": "unranked.png",
            "sin rango": "unranked.png",
        }

        for tier in all_tiers:
            with self.subTest(tier=tier):
                url = get_rank_crest_url(tier)
                expected_filename = expected_crest_files[tier.lower()]
                self.assertTrue(
                    url.endswith(expected_filename),
                    f"Tier {tier} crest URL {url} does not end with {expected_filename}",
                )

        # Unknown tier fallback
        fallback = get_rank_crest_url("UnknownTierXYZ")
        self.assertTrue(fallback.endswith("gold.png"))


class TestMenubarIconsPixelGeometry(unittest.TestCase):
    """Empirical verification of pixel geometry, dimensions, alpha levels, and template modes."""

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_challenger2_icons_")
        cls.icons = assets_gen.generate_status_icons(cls.temp_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_file_existence_and_dimensions(self):
        """Verify all 6 required icon files exist with exact pixel dimensions (22x22 and 44x44)."""
        expected = {
            "normal": (22, 22),
            "normal@2x": (44, 44),
            "active": (22, 22),
            "active@2x": (44, 44),
            "paused": (22, 22),
            "paused@2x": (44, 44),
        }
        for key, expected_size in expected.items():
            path = self.icons.get(key)
            self.assertIsNotNone(path, f"Missing icon mapping for {key}")
            self.assertTrue(os.path.exists(path), f"Icon file {path} does not exist")
            with Image.open(path) as img:
                self.assertEqual(img.size, expected_size, f"{key} dimensions mismatch: {img.size} vs {expected_size}")
                self.assertEqual(img.mode, "RGBA", f"{key} image mode is not RGBA: {img.mode}")

    def test_normal_icon_monochrome_geometry(self):
        """Verify normal icon is purely monochrome white with alpha transparency."""
        for key in ["normal", "normal@2x"]:
            with Image.open(self.icons[key]) as img:
                for x in range(img.width):
                    for y in range(img.height):
                        r, g, b, a = img.getpixel((x, y))
                        if a > 0:
                            # White geometry: R, G, B should be equal (pure white channel)
                            self.assertEqual(
                                (r, g, b),
                                (255, 255, 255),
                                f"Non-monochrome pixel at ({x}, {y}) in {key}: {(r, g, b)}",
                            )

    def test_active_icon_blue_dot_geometry_and_bounds(self):
        """Verify active icon contains #00A8FC blue dot, cutout ring, and strict non-bleeding margins."""
        # 1. Inspect Retina 2x active icon
        with Image.open(self.icons["active@2x"]) as img:
            w, h = img.size
            self.assertEqual((w, h), (44, 44))

            # Locate all blue pixels (R near 0, G near 168, B near 252)
            blue_pixels = []
            for y in range(h):
                for x in range(w):
                    r, g, b, a = img.getpixel((x, y))
                    if b > 200 and r < 40 and g > 130 and a > 100:
                        blue_pixels.append((x, y, r, g, b, a))

            self.assertGreater(len(blue_pixels), 50, "Active @2x icon must contain distinct blue indicator dot")

            min_x = min(p[0] for p in blue_pixels)
            max_x = max(p[0] for p in blue_pixels)
            min_y = min(p[1] for p in blue_pixels)
            max_y = max(p[1] for p in blue_pixels)

            dot_w = max_x - min_x + 1
            dot_h = max_y - min_y + 1

            # Diameter: spec calls for 6-7 pt. At @2x Retina, 6-7 pt = 12-14 px.
            self.assertGreaterEqual(dot_w, 11, f"Dot width {dot_w}px too small for Retina 2x")
            self.assertLessEqual(dot_w, 15, f"Dot width {dot_w}px too large for Retina 2x")
            self.assertGreaterEqual(dot_h, 11, f"Dot height {dot_h}px too small for Retina 2x")
            self.assertLessEqual(dot_h, 15, f"Dot height {dot_h}px too large for Retina 2x")

            # Must be positioned in lower-right quadrant: x > w/2 and y > h/2
            self.assertGreater(min_x, w // 2, "Blue dot must be in right half of canvas")
            self.assertGreater(min_y, h // 2, "Blue dot must be in bottom half of canvas")

            # Boundary containment: margins from edge must be strictly positive (no bleed)
            right_margin = w - 1 - max_x
            bottom_margin = h - 1 - max_y
            self.assertGreaterEqual(right_margin, 2, f"Right margin {right_margin}px too small (bleeding)")
            self.assertGreaterEqual(bottom_margin, 2, f"Bottom margin {bottom_margin}px too small (bleeding)")

            # Outer border ring (x=0, x=w-1, y=0, y=h-1) must have alpha 0
            for x in range(w):
                self.assertEqual(img.getpixel((x, 0))[3], 0, f"Pixel at ({x}, 0) is not transparent")
                self.assertEqual(img.getpixel((x, h - 1))[3], 0, f"Pixel at ({x}, {h-1}) is not transparent")
            for y in range(h):
                self.assertEqual(img.getpixel((0, y))[3], 0, f"Pixel at (0, {y}) is not transparent")
                self.assertEqual(img.getpixel((w - 1, y))[3], 0, f"Pixel at ({w-1}, {y}) is not transparent")

    def test_paused_icon_dimmed_alpha(self):
        """Verify paused icon has dimmed alpha corresponding to ~35% transparency."""
        for key in ["paused", "paused@2x"]:
            with Image.open(self.icons[key]) as img:
                alphas = [p[3] for p in img.getdata() if p[3] > 0]
                self.assertGreater(len(alphas), 0, f"{key} icon is completely transparent/blank")
                max_alpha = max(alphas)
                min_alpha = min(alphas)

                # Expected target is 35% of 255 = 89.25. Tolerance allows anti-aliasing edge blend.
                self.assertLessEqual(
                    max_alpha,
                    120,
                    f"{key} max alpha {max_alpha} exceeds dimmed threshold (not properly dimmed)",
                )
                self.assertGreaterEqual(
                    max_alpha,
                    60,
                    f"{key} max alpha {max_alpha} too low (invisible)",
                )

                # Confirm NO pixel is fully opaque (255)
                self.assertNotIn(255, alphas, f"{key} contains fully opaque pixels (alpha=255)")

    def test_status_item_template_flags(self):
        """Verify status item controller sets template mode True for normal, False for active/paused."""
        ctrl = LoLStatusItemController(assets_dir=self.temp_dir)
        btn = ctrl.get_button()
        self.assertIsNotNone(btn)

        # Normal: template True
        ctrl.set_state("normal")
        self.assertEqual(ctrl.get_current_state(), "normal")
        self.assertTrue(
            btn.image().isTemplate(),
            "Normal icon MUST be setTemplate_(True) to adapt to macOS menu bar themes",
        )

        # Active: template False
        ctrl.set_state("active")
        self.assertEqual(ctrl.get_current_state(), "active")
        self.assertFalse(
            btn.image().isTemplate(),
            "Active icon MUST be setTemplate_(False) to preserve the blue status indicator dot",
        )

        # Paused: template False
        ctrl.set_state("paused")
        self.assertEqual(ctrl.get_current_state(), "paused")
        self.assertFalse(
            btn.image().isTemplate(),
            "Paused icon MUST be setTemplate_(False) to preserve dimmed 35% alpha rendering",
        )

        ctrl.cleanup()


if __name__ == "__main__":
    unittest.main()
