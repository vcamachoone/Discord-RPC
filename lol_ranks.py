"""
lol_ranks.py - LoL Rank Crest Assets and Division Formatter

Maps competitive tiers to CommunityDragon crest assets and formats rank strings
for Discord Rich Presence, suppressing division numbers for Apex tiers (Master,
Grandmaster, Challenger) and Unranked according to Riot League of Legends standards.
"""

from typing import Dict, List, Optional, Set

COMMUNITY_DRAGON_BASE = (
    "https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-shared-components/global/default"
)

# Standard Spanish rank list for UI menus and settings
DEFAULT_RANKS_ES: List[str] = [
    "Hierro",
    "Bronce",
    "Plata",
    "Oro",
    "Platino",
    "Esmeralda",
    "Diamante",
    "Maestro",
    "Gran Maestro",
    "Challenger",
    "Unranked",
]

DEFAULT_DIVISIONS: List[str] = ["I", "II", "III", "IV"]

# Complete CommunityDragon crest assets for Spanish and English tier names
RANKS_ASSETS: Dict[str, str] = {
    # Spanish
    "Hierro": f"{COMMUNITY_DRAGON_BASE}/iron.png",
    "Bronce": f"{COMMUNITY_DRAGON_BASE}/bronze.png",
    "Plata": f"{COMMUNITY_DRAGON_BASE}/silver.png",
    "Oro": f"{COMMUNITY_DRAGON_BASE}/gold.png",
    "Platino": f"{COMMUNITY_DRAGON_BASE}/platinum.png",
    "Esmeralda": f"{COMMUNITY_DRAGON_BASE}/emerald.png",
    "Diamante": f"{COMMUNITY_DRAGON_BASE}/diamond.png",
    "Maestro": f"{COMMUNITY_DRAGON_BASE}/master.png",
    "Gran Maestro": f"{COMMUNITY_DRAGON_BASE}/grandmaster.png",
    "Challenger": f"{COMMUNITY_DRAGON_BASE}/challenger.png",
    "Unranked": f"{COMMUNITY_DRAGON_BASE}/unranked.png",
    "Sin rango": f"{COMMUNITY_DRAGON_BASE}/unranked.png",
    # English equivalents
    "Iron": f"{COMMUNITY_DRAGON_BASE}/iron.png",
    "Bronze": f"{COMMUNITY_DRAGON_BASE}/bronze.png",
    "Silver": f"{COMMUNITY_DRAGON_BASE}/silver.png",
    "Gold": f"{COMMUNITY_DRAGON_BASE}/gold.png",
    "Platinum": f"{COMMUNITY_DRAGON_BASE}/platinum.png",
    "Emerald": f"{COMMUNITY_DRAGON_BASE}/emerald.png",
    "Diamond": f"{COMMUNITY_DRAGON_BASE}/diamond.png",
    "Master": f"{COMMUNITY_DRAGON_BASE}/master.png",
    "Grandmaster": f"{COMMUNITY_DRAGON_BASE}/grandmaster.png",
}

# Apex tiers (plus Unranked) that do NOT have divisions (e.g. Challenger, never Challenger II)
APEX_TIERS: Set[str] = {
    "maestro",
    "master",
    "gran maestro",
    "grandmaster",
    "challenger",
    "unranked",
    "sin rango",
}


def is_apex_tier(tier: str) -> bool:
    """Returns True if the given tier suppresses division numbers."""
    if not tier:
        return False
    return tier.strip().lower() in APEX_TIERS


def format_rank_display(tier: str, division: str = "II") -> str:
    """
    Formats the rank string for Discord RPC (e.g. small_text).
    Standard tiers format as "{Tier} {Division}" (e.g. "Oro II", "Diamante IV").
    Apex tiers (Master, Grandmaster, Challenger, Unranked) suppress the division,
    returning strictly "{Tier}" (e.g. "Challenger", "Gran Maestro").
    """
    if not tier or not tier.strip():
        return "Unranked"

    tier_clean = tier.strip()

    # Apex tier division suppression
    if is_apex_tier(tier_clean):
        return tier_clean

    div_clean = division.strip() if division else ""
    if not div_clean:
        return tier_clean

    # Prevent accidental double-division strings if tier already ended with division
    tokens = tier_clean.split()
    if len(tokens) > 1 and tokens[-1].upper() in DEFAULT_DIVISIONS:
        return tier_clean

    return f"{tier_clean} {div_clean}".strip()


def get_rank_crest_url(tier: str) -> str:
    """
    Returns the CommunityDragon URL for the tier crest icon.
    Falls back to 'Oro' crest if tier is unknown.
    """
    if not tier or not tier.strip():
        return RANKS_ASSETS["Oro"]

    tier_clean = tier.strip()
    if tier_clean in RANKS_ASSETS:
        return RANKS_ASSETS[tier_clean]

    # Case-insensitive lookup
    tier_lower = tier_clean.lower()
    for k, v in RANKS_ASSETS.items():
        if k.lower() == tier_lower:
            return v

    return RANKS_ASSETS["Oro"]


def get_available_ranks(lang: str = "es") -> List[str]:
    """Returns the ordered list of competitive rank tier names."""
    if lang.lower() == "en":
        return [
            "Iron",
            "Bronze",
            "Silver",
            "Gold",
            "Platinum",
            "Emerald",
            "Diamond",
            "Master",
            "Grandmaster",
            "Challenger",
            "Unranked",
        ]
    return list(DEFAULT_RANKS_ES)


def get_available_divisions() -> List[str]:
    """Returns the standard division list [I, II, III, IV]."""
    return list(DEFAULT_DIVISIONS)
