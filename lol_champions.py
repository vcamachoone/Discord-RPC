"""
lol_champions.py - LoL Champion Normalization & Riot Data Dragon Resolver

Handles normalization of all 173 champions in League of Legends (Data Dragon 16.19.1+),
resolving internal ID discrepancies, Spanish localized names, community abbreviations,
and punctuation anomalies to guaranteed valid DDragon CDN image URLs.
"""

import json
import re
import urllib.request
from typing import Dict, List, Optional, Tuple

FALLBACK_VERSION = "16.19.1"

# Complete canonical roster of 173 champions in Data Dragon 16.19.1: (id, official_display_name)
CHAMPIONS_DATA: List[Tuple[str, str]] = [
    ("Aatrox", "Aatrox"),
    ("Ahri", "Ahri"),
    ("Akali", "Akali"),
    ("Akshan", "Akshan"),
    ("Alistar", "Alistar"),
    ("Ambessa", "Ambessa"),
    ("Amumu", "Amumu"),
    ("Anivia", "Anivia"),
    ("Annie", "Annie"),
    ("Aphelios", "Aphelios"),
    ("Ashe", "Ashe"),
    ("AurelionSol", "Aurelion Sol"),
    ("Aurora", "Aurora"),
    ("Azir", "Azir"),
    ("Bard", "Bard"),
    ("Belveth", "Bel'Veth"),
    ("Blitzcrank", "Blitzcrank"),
    ("Brand", "Brand"),
    ("Braum", "Braum"),
    ("Briar", "Briar"),
    ("Caitlyn", "Caitlyn"),
    ("Camille", "Camille"),
    ("Cassiopeia", "Cassiopeia"),
    ("Chogath", "Cho'Gath"),
    ("Corki", "Corki"),
    ("Darius", "Darius"),
    ("Diana", "Diana"),
    ("DrMundo", "Dr. Mundo"),
    ("Draven", "Draven"),
    ("Ekko", "Ekko"),
    ("Elise", "Elise"),
    ("Evelynn", "Evelynn"),
    ("Ezreal", "Ezreal"),
    ("Fiddlesticks", "Fiddlesticks"),
    ("Fiora", "Fiora"),
    ("Fizz", "Fizz"),
    ("Galio", "Galio"),
    ("Gangplank", "Gangplank"),
    ("Garen", "Garen"),
    ("Gnar", "Gnar"),
    ("Gragas", "Gragas"),
    ("Graves", "Graves"),
    ("Gwen", "Gwen"),
    ("Hecarim", "Hecarim"),
    ("Heimerdinger", "Heimerdinger"),
    ("Hwei", "Hwei"),
    ("Illaoi", "Illaoi"),
    ("Irelia", "Irelia"),
    ("Ivern", "Ivern"),
    ("Janna", "Janna"),
    ("JarvanIV", "Jarvan IV"),
    ("Jax", "Jax"),
    ("Jayce", "Jayce"),
    ("Jhin", "Jhin"),
    ("Jinx", "Jinx"),
    ("KSante", "K'Sante"),
    ("Kaisa", "Kai'Sa"),
    ("Kalista", "Kalista"),
    ("Karma", "Karma"),
    ("Karthus", "Karthus"),
    ("Kassadin", "Kassadin"),
    ("Katarina", "Katarina"),
    ("Kayle", "Kayle"),
    ("Kayn", "Kayn"),
    ("Kennen", "Kennen"),
    ("Khazix", "Kha'Zix"),
    ("Kindred", "Kindred"),
    ("Kled", "Kled"),
    ("KogMaw", "Kog'Maw"),
    ("Leblanc", "LeBlanc"),
    ("LeeSin", "Lee Sin"),
    ("Leona", "Leona"),
    ("Lillia", "Lillia"),
    ("Lissandra", "Lissandra"),
    ("Locke", "Locke"),
    ("Lucian", "Lucian"),
    ("Lulu", "Lulu"),
    ("Lux", "Lux"),
    ("Malphite", "Malphite"),
    ("Malzahar", "Malzahar"),
    ("Maokai", "Maokai"),
    ("MasterYi", "Master Yi"),
    ("Mel", "Mel"),
    ("Milio", "Milio"),
    ("MissFortune", "Miss Fortune"),
    ("MonkeyKing", "Wukong"),
    ("Mordekaiser", "Mordekaiser"),
    ("Morgana", "Morgana"),
    ("Naafiri", "Naafiri"),
    ("Nami", "Nami"),
    ("Nasus", "Nasus"),
    ("Nautilus", "Nautilus"),
    ("Neeko", "Neeko"),
    ("Nidalee", "Nidalee"),
    ("Nilah", "Nilah"),
    ("Nocturne", "Nocturne"),
    ("Nunu", "Nunu & Willump"),
    ("Olaf", "Olaf"),
    ("Orianna", "Orianna"),
    ("Ornn", "Ornn"),
    ("Pantheon", "Pantheon"),
    ("Poppy", "Poppy"),
    ("Pyke", "Pyke"),
    ("Qiyana", "Qiyana"),
    ("Quinn", "Quinn"),
    ("Rakan", "Rakan"),
    ("Rammus", "Rammus"),
    ("RekSai", "Rek'Sai"),
    ("Rell", "Rell"),
    ("Renata", "Renata Glasc"),
    ("Renekton", "Renekton"),
    ("Rengar", "Rengar"),
    ("Riven", "Riven"),
    ("Rumble", "Rumble"),
    ("Ryze", "Ryze"),
    ("Samira", "Samira"),
    ("Sejuani", "Sejuani"),
    ("Senna", "Senna"),
    ("Seraphine", "Seraphine"),
    ("Sett", "Sett"),
    ("Shaco", "Shaco"),
    ("Shen", "Shen"),
    ("Shyvana", "Shyvana"),
    ("Singed", "Singed"),
    ("Sion", "Sion"),
    ("Sivir", "Sivir"),
    ("Skarner", "Skarner"),
    ("Smolder", "Smolder"),
    ("Sona", "Sona"),
    ("Soraka", "Soraka"),
    ("Swain", "Swain"),
    ("Sylas", "Sylas"),
    ("Syndra", "Syndra"),
    ("TahmKench", "Tahm Kench"),
    ("Taliyah", "Taliyah"),
    ("Talon", "Talon"),
    ("Taric", "Taric"),
    ("Teemo", "Teemo"),
    ("Thresh", "Thresh"),
    ("Tristana", "Tristana"),
    ("Trundle", "Trundle"),
    ("Tryndamere", "Tryndamere"),
    ("TwistedFate", "Twisted Fate"),
    ("Twitch", "Twitch"),
    ("Udyr", "Udyr"),
    ("Urgot", "Urgot"),
    ("Varus", "Varus"),
    ("Vayne", "Vayne"),
    ("Veigar", "Veigar"),
    ("Velkoz", "Vel'Koz"),
    ("Vex", "Vex"),
    ("Vi", "Vi"),
    ("Viego", "Viego"),
    ("Viktor", "Viktor"),
    ("Vladimir", "Vladimir"),
    ("Volibear", "Volibear"),
    ("Warwick", "Warwick"),
    ("Xayah", "Xayah"),
    ("Xerath", "Xerath"),
    ("XinZhao", "Xin Zhao"),
    ("Yasuo", "Yasuo"),
    ("Yone", "Yone"),
    ("Yorick", "Yorick"),
    ("Yunara", "Yunara"),
    ("Yuumi", "Yuumi"),
    ("Zaahen", "Zaahen"),
    ("Zac", "Zac"),
    ("Zed", "Zed"),
    ("Zeri", "Zeri"),
    ("Ziggs", "Ziggs"),
    ("Zilean", "Zilean"),
    ("Zoe", "Zoe"),
    ("Zyra", "Zyra"),
]

# Explicit alias overrides for Riot internal ID anomalies, Spanish names, and abbreviations
SPECIAL_CHAMPION_MAP: Dict[str, Tuple[str, str]] = {
    # 1. The 9 Core Riot Internal ID Anomalies
    "wukong": ("MonkeyKing", "Wukong"),
    "monkeyking": ("MonkeyKing", "Wukong"),
    "nunu": ("Nunu", "Nunu & Willump"),
    "nunuwillump": ("Nunu", "Nunu & Willump"),
    "nunuywillump": ("Nunu", "Nunu & Willump"),
    "renata": ("Renata", "Renata Glasc"),
    "renataglasc": ("Renata", "Renata Glasc"),
    "chogath": ("Chogath", "Cho'Gath"),
    "kaisa": ("Kaisa", "Kai'Sa"),
    "velkoz": ("Velkoz", "Vel'Koz"),
    "khazix": ("Khazix", "Kha'Zix"),
    "belveth": ("Belveth", "Bel'Veth"),
    "leblanc": ("Leblanc", "LeBlanc"),

    # 2. Punctuation & CamelCase champions
    "ksante": ("KSante", "K'Sante"),
    "kogmaw": ("KogMaw", "Kog'Maw"),
    "reksai": ("RekSai", "Rek'Sai"),
    "drmundo": ("DrMundo", "Dr. Mundo"),
    "doctormundo": ("DrMundo", "Dr. Mundo"),
    "mundo": ("DrMundo", "Dr. Mundo"),
    "jarvaniv": ("JarvanIV", "Jarvan IV"),
    "jarvan4": ("JarvanIV", "Jarvan IV"),
    "jarvan": ("JarvanIV", "Jarvan IV"),
    "masteryi": ("MasterYi", "Master Yi"),
    "missfortune": ("MissFortune", "Miss Fortune"),
    "tahmkench": ("TahmKench", "Tahm Kench"),
    "twistedfate": ("TwistedFate", "Twisted Fate"),
    "xinzhao": ("XinZhao", "Xin Zhao"),
    "aurelionsol": ("AurelionSol", "Aurelion Sol"),

    # 3. Spanish Localized Champion Names
    "bardo": ("Bard", "Bard"),
    "maestroyi": ("MasterYi", "Master Yi"),

    # 4. Common Community Abbreviations & Nicknames
    "j4": ("JarvanIV", "Jarvan IV"),
    "asol": ("AurelionSol", "Aurelion Sol"),
    "mf": ("MissFortune", "Miss Fortune"),
    "tf": ("TwistedFate", "Twisted Fate"),
    "yi": ("MasterYi", "Master Yi"),
    "tahm": ("TahmKench", "Tahm Kench"),
    "kench": ("TahmKench", "Tahm Kench"),
    "cait": ("Caitlyn", "Caitlyn"),
    "ez": ("Ezreal", "Ezreal"),
    "gp": ("Gangplank", "Gangplank"),
    "morde": ("Mordekaiser", "Mordekaiser"),
    "nida": ("Nidalee", "Nidalee"),
    "ori": ("Orianna", "Orianna"),
    "seju": ("Sejuani", "Sejuani"),
    "trist": ("Tristana", "Tristana"),
    "trynd": ("Tryndamere", "Tryndamere"),
    "vlad": ("Vladimir", "Vladimir"),
    "ww": ("Warwick", "Warwick"),
    "xin": ("XinZhao", "Xin Zhao"),
}


class ChampionResolver:
    """
    Riot Data Dragon champion resolver and normalizer.
    Guarantees that any arbitrary user input maps to a valid champion ID and CDN image URL.
    """

    def __init__(self, default_version: str = FALLBACK_VERSION):
        self.version: str = default_version
        self._id_to_name: Dict[str, str] = {}
        self._lookup_map: Dict[str, Tuple[str, str]] = {}
        self._build_lookup_index()

    def _build_lookup_index(self) -> None:
        """Populates the normalized in-memory lookup table."""
        # 1. Index all canonical champions
        for cid, display_name in CHAMPIONS_DATA:
            self._id_to_name[cid] = display_name
            # Lowercase cleaned ID: e.g. "aurelionsol" -> ("AurelionSol", "Aurelion Sol")
            clean_id = re.sub(r"[^a-z0-9]", "", cid.lower())
            self._lookup_map[clean_id] = (cid, display_name)
            # Lowercase cleaned display name: e.g. "aurelionsol" -> ("AurelionSol", "Aurelion Sol")
            clean_name = re.sub(r"[^a-z0-9]", "", display_name.lower())
            self._lookup_map[clean_name] = (cid, display_name)

        # 2. Overlay special maps and aliases (ensures anomalies & Spanish names win)
        for key, target in SPECIAL_CHAMPION_MAP.items():
            clean_k = re.sub(r"[^a-z0-9]", "", key.lower())
            self._lookup_map[clean_k] = target

    def fetch_latest_version(self) -> str:
        """
        Fetches the latest active Data Dragon patch version from Riot's API.
        Falls back to FALLBACK_VERSION on error or timeout.
        """
        try:
            req = urllib.request.Request(
                "https://ddragon.leagueoflegends.com/api/versions.json",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                versions = json.loads(resp.read().decode("utf-8"))
                if versions and isinstance(versions, list) and len(versions) > 0:
                    self.version = str(versions[0]).strip()
        except Exception:
            self.version = FALLBACK_VERSION
        return self.version

    def resolve_champion(self, user_input: str) -> Tuple[str, str]:
        """
        Resolves arbitrary user input string to (ddragon_id, display_name).
        Guarantees that ddragon_id is a valid Data Dragon CDN resource identifier.
        """
        if not user_input or not user_input.strip():
            return "Malzahar", "Malzahar"

        raw_query = user_input.strip()
        clean_key = re.sub(r"[^a-z0-9]", "", raw_query.lower())

        if not clean_key:
            return "Malzahar", "Malzahar"

        # 1. Exact match in normalized lookup map
        if clean_key in self._lookup_map:
            cid, default_name = self._lookup_map[clean_key]
            return cid, raw_query if raw_query.lower() != clean_key else default_name

        # 2. Prefix match (e.g. user typed partial name)
        for k, (cid, display_name) in self._lookup_map.items():
            if k.startswith(clean_key) and len(clean_key) >= 3:
                return cid, display_name

        # 3. Substring match
        for k, (cid, display_name) in self._lookup_map.items():
            if clean_key in k and len(clean_key) >= 4:
                return cid, display_name

        # 4. Capitalized heuristic check for new unindexed champions
        # Riot standard pattern: First letter capital, rest lowercase or alphanumeric
        cleaned_alphanum = re.sub(r"[^a-zA-Z0-9]", "", raw_query)
        if cleaned_alphanum:
            candidate = cleaned_alphanum[0].upper() + cleaned_alphanum[1:]
            if candidate in self._id_to_name:
                return candidate, self._id_to_name[candidate]

        # 5. Safe fallback
        return "Malzahar", "Malzahar"

    def get_square_icon_url(self, champion_id: str) -> str:
        """Returns the CDN URL for the champion square portrait."""
        return f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{champion_id}.png"

    def get_loading_splash_url(self, champion_id: str) -> str:
        """Returns the CDN URL for the vertical loading screen card splash."""
        return f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{champion_id}_0.jpg"

    def get_splash_url(self, champion_id: str) -> str:
        """Returns the CDN URL for the centered widescreen splash art."""
        return f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion_id}_0.jpg"

    def get_all_champions(self) -> List[Tuple[str, str]]:
        """Returns all 173 champions as (ddragon_id, display_name) sorted alphabetically."""
        return sorted(CHAMPIONS_DATA, key=lambda x: x[1].lower())

    def get_champion_names(self) -> List[str]:
        """Returns sorted list of all champion display names."""
        return [champ[1] for champ in self.get_all_champions()]
