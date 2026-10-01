"""
liquid_html.py - Liquid Glass HTML/CSS Interface Generator for macOS NSPopover

Produces pixel-perfect Figma-grade Liquid Glass UI matching design mockup 123.png:
  - Deep dark frosted glass with specular highlight and multi-layer backdrop-filter
  - High-DPI Discord Clyde vector logo
  - Mode selection cards with electric blue gradient, cyan glow, and radial blur dot
  - Modern iOS liquid toggle switches with spring transitions
  - Interactive Action button with state-responsive blurple / slate styles
  - Real-time searchable champion selector with 173 Riot Data Dragon avatars
  - Canonical League of Legends game modes dropdown with custom mode support
  - Competitive rank crests & division controls
"""

import json
from typing import Any, Dict, List, Optional, Tuple

try:
    from lol_champions import CHAMPIONS_DATA, FALLBACK_VERSION
except ImportError:
    FALLBACK_VERSION = "16.19.1"
    CHAMPIONS_DATA = [
        ("Aatrox", "Aatrox"), ("Ahri", "Ahri"), ("Akali", "Akali"), ("Akshan", "Akshan"),
        ("Alistar", "Alistar"), ("Amumu", "Amumu"), ("Anivia", "Anivia"), ("Annie", "Annie"),
        ("Aphelios", "Aphelios"), ("Ashe", "Ashe"), ("AurelionSol", "Aurelion Sol"),
        ("Aurora", "Aurora"), ("Azir", "Azir"), ("Bard", "Bard"), ("Belveth", "Bel'Veth"),
        ("Blitzcrank", "Blitzcrank"), ("Brand", "Brand"), ("Braum", "Braum"), ("Briar", "Briar"),
        ("Caitlyn", "Caitlyn"), ("Camille", "Camille"), ("Cassiopeia", "Cassiopeia"),
        ("Chogath", "Cho'Gath"), ("Corki", "Corki"), ("Darius", "Darius"), ("Diana", "Diana"),
        ("DrMundo", "Dr. Mundo"), ("Draven", "Draven"), ("Ekko", "Ekko"), ("Elise", "Elise"),
        ("Evelynn", "Evelynn"), ("Ezreal", "Ezreal"), ("Fiddlesticks", "Fiddlesticks"),
        ("Fiora", "Fiora"), ("Fizz", "Fizz"), ("Galio", "Galio"), ("Gangplank", "Gangplank"),
        ("Garen", "Garen"), ("Gnar", "Gnar"), ("Gragas", "Gragas"), ("Graves", "Graves"),
        ("Gwen", "Gwen"), ("Hecarim", "Hecarim"), ("Heimerdinger", "Heimerdinger"),
        ("Hwei", "Hwei"), ("Illaoi", "Illaoi"), ("Irelia", "Irelia"), ("Ivern", "Ivern"),
        ("Janna", "Janna"), ("JarvanIV", "Jarvan IV"), ("Jax", "Jax"), ("Jayce", "Jayce"),
        ("Jhin", "Jhin"), ("Jinx", "Jinx"), ("Kaisa", "Kai'Sa"), ("Kalista", "Kalista"),
        ("Karma", "Karma"), ("Karthus", "Karthus"), ("Kassadin", "Kassadin"), ("Katarina", "Katarina"),
        ("Kayle", "Kayle"), ("Kayn", "Kayn"), ("Kennen", "Kennen"), ("Khazix", "Kha'Zix"),
        ("Kindred", "Kindred"), ("Kled", "Kled"), ("KogMaw", "Kog'Maw"), ("KSante", "K'Sante"),
        ("Leblanc", "LeBlanc"), ("LeeSin", "Lee Sin"), ("Leona", "Leona"), ("Lillia", "Lillia"),
        ("Lissandra", "Lissandra"), ("Lucian", "Lucian"), ("Lulu", "Lulu"), ("Lux", "Lux"),
        ("Malphite", "Malphite"), ("Malzahar", "Malzahar"), ("Maokai", "Maokai"),
        ("MasterYi", "Master Yi"), ("Milio", "Milio"), ("MissFortune", "Miss Fortune"),
        ("Mordekaiser", "Mordekaiser"), ("Morgana", "Morgana"), ("Naafiri", "Naafiri"),
        ("Nami", "Nami"), ("Nasus", "Nasus"), ("Nautilus", "Nautilus"), ("Neeko", "Neeko"),
        ("Nidalee", "Nidalee"), ("Nilah", "Nilah"), ("Nocturne", "Nocturne"), ("Nunu", "Nunu y Willump"),
        ("Olaf", "Olaf"), ("Orianna", "Orianna"), ("Ornn", "Ornn"), ("Pantheon", "Pantheon"),
        ("Poppy", "Poppy"), ("Pyke", "Pyke"), ("Qiyana", "Qiyana"), ("Quinn", "Quinn"),
        ("Rakan", "Rakan"), ("Rammus", "Rammus"), ("RekSai", "Rek'Sai"), ("Rell", "Rell"),
        ("Renata", "Renata Glasc"), ("Renekton", "Renekton"), ("Rengar", "Rengar"),
        ("Riven", "Riven"), ("Rumble", "Rumble"), ("Ryze", "Ryze"), ("Samira", "Samira"),
        ("Sejuani", "Sejuani"), ("Senna", "Senna"), ("Seraphine", "Seraphine"), ("Sett", "Sett"),
        ("Shaco", "Shaco"), ("Shen", "Shen"), ("Shyvana", "Shyvana"), ("Singed", "Singed"),
        ("Sion", "Sion"), ("Sivir", "Sivir"), ("Skarner", "Skarner"), ("Smolder", "Smolder"),
        ("Sona", "Sona"), ("Soraka", "Soraka"), ("Swain", "Swain"), ("Sylas", "Sylas"),
        ("Syndra", "Syndra"), ("TahmKench", "Tahm Kench"), ("Taliyah", "Taliyah"),
        ("Talon", "Talon"), ("Taric", "Taric"), ("Teemo", "Teemo"), ("Thresh", "Thresh"),
        ("Tristana", "Tristana"), ("Trundle", "Trundle"), ("Tryndamere", "Tryndamere"),
        ("TwistedFate", "Twisted Fate"), ("Twitch", "Twitch"), ("Udyr", "Udyr"),
        ("Urgot", "Urgot"), ("Varus", "Varus"), ("Vayne", "Vayne"), ("Veigar", "Veigar"),
        ("Velkoz", "Vel'Koz"), ("Vex", "Vex"), ("Vi", "Vi"), ("Viego", "Viego"),
        ("Viktor", "Viktor"), ("Vladimir", "Vladimir"), ("Volibear", "Volibear"),
        ("Warwick", "Warwick"), ("MonkeyKing", "Wukong"), ("Xayah", "Xayah"),
        ("Xerath", "Xerath"), ("XinZhao", "Xin Zhao"), ("Yasuo", "Yasuo"), ("Yone", "Yone"),
        ("Yorick", "Yorick"), ("Yuumi", "Yuumi"), ("Zac", "Zac"), ("Zed", "Zed"),
        ("Zeri", "Zeri"), ("Ziggs", "Ziggs"), ("Zilean", "Zilean"), ("Zoe", "Zoe"),
        ("Zyra", "Zyra"),
    ]

# Construct 173 champions catalog with CDN URLs
CHAMPIONS_CATALOG: List[Dict[str, str]] = [
    {
        "id": cid,
        "name": name,
        "icon": f"https://ddragon.leagueoflegends.com/cdn/{FALLBACK_VERSION}/img/champion/{cid}.png",
    }
    for cid, name in CHAMPIONS_DATA
]

# Canonical League of Legends Game Modes
GAME_MODES: List[str] = [
    "Grieta del Invocador (Clasificatoria Solo/Duo)",
    "Grieta del Invocador (Clasificatoria Flexible)",
    "Grieta del Invocador (Normal / Partida Rápida)",
    "Grieta del Invocador (Reclutamiento / Draft)",
    "ARAM (El Abismo de los Lamentos)",
    "Arena (2v2v2v2)",
    "Teamfight Tactics (TFT)",
    "URF (Fuego Rápido Ultra)",
    "Partida Personalizada",
    "Herramienta de Práctica",
]

DISCORD_SVG = """<svg class="discord-logo" viewBox="0 0 127.14 96.36">
  <path fill="#FFFFFF" d="M107.7,8.07A105.15,105.15,0,0,0,81.47,0a72.06,72.06,0,0,0-3.36,6.83A97.68,97.68,0,0,0,49,6.83,72.37,72.37,0,0,0,45.64,0,105.89,105.89,0,0,0,19.39,8.09C2.79,32.65-1.71,56.6.54,80.21h0A105.73,105.73,0,0,0,32.71,96.36,77.7,77.7,0,0,0,39.6,85.25a68.42,68.42,0,0,1-10.85-5.18c.91-.66,1.8-1.34,2.66-2a75.57,75.57,0,0,0,64.32,0c.87.71,1.76,1.39,2.66,2a68.68,68.68,0,0,1-10.87,5.19,77,77,0,0,0,6.89,11.1A105.25,105.25,0,0,0,126.6,80.22h0C129.24,52.84,122.09,29.11,107.7,8.07ZM42.45,65.69C36.18,65.69,31,60,31,53s5-12.74,11.43-12.74S54,45.91,53.89,53,48.84,65.69,42.45,65.69Zm42.24,0C78.41,65.69,73.25,60,73.25,53s5-12.74,11.44-12.74S96.23,45.91,96.12,53,91.08,65.69,84.69,65.69Z"/>
</svg>"""

GEAR_SVG = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="3"></circle>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
</svg>"""

SYNC_SVG = """<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="23 4 23 10 17 10"></polyline>
  <polyline points="1 20 1 14 7 14"></polyline>
  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
</svg>"""

LAPTOP_SVG = """<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
  <line x1="1" y1="20" x2="23" y2="20"></line>
</svg>"""

SEARCH_SVG = """<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="11" cy="11" r="8"></circle>
  <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
</svg>"""


def generate_liquid_html(initial_state: dict) -> str:
    """Generates the full self-contained HTML page with liquid glass styling."""
    champions_json_str = json.dumps(CHAMPIONS_CATALOG)
    game_modes_options_html = "\n".join(
        f'<option value="{gm}">{gm}</option>' for gm in GAME_MODES
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  :root {{
    --bg-glass: radial-gradient(130% 110% at 50% -10%, rgba(36, 50, 78, 0.92) 0%, rgba(15, 20, 32, 0.98) 100%);
    --card-active-bg: linear-gradient(135deg, rgba(56, 140, 248, 0.22) 0%, rgba(20, 30, 52, 0.55) 100%);
    --card-active-border: rgba(56, 189, 248, 0.7);
    --card-active-glow: 0 0 24px rgba(56, 189, 248, 0.25);
    --card-normal-bg: rgba(255, 255, 255, 0.04);
    --card-normal-border: rgba(255, 255, 255, 0.08);
    --text-primary: #FFFFFF;
    --text-secondary: #94A3B8;
    --blue-accent: #38BDF8;
    --blue-glow: 0 0 12px rgba(56, 189, 248, 0.6);
    --discord-blurple: #5865F2;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
    -webkit-user-select: none;
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
  }}

  html, body {{
    background: transparent;
    overflow-x: hidden;
    overflow-y: hidden;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 0;
  }}

  /* Custom subtle dark scrollbar */
  ::-webkit-scrollbar {{
    display: none;
  }}

  /* Main Popover Container */
  .liquid-container {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 100%;
    box-sizing: border-box;
    padding: 14px 16px 14px;
    background: var(--bg-glass);
    backdrop-filter: blur(50px) saturate(210%);
    -webkit-backdrop-filter: blur(50px) saturate(210%);
    border-radius: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}

  /* Specular top-edge light reflection disabled to avoid slicing under arrow */
  .liquid-container::before {{
    display: none;
  }}

  /* Header */
  .header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 2px;
  }}
  .header-left {{
    display: flex;
    align-items: center;
    gap: 11px;
  }}
  .discord-logo {{
    width: 32px;
    height: 32px;
    filter: drop-shadow(0 2px 8px rgba(88, 101, 242, 0.45));
  }}
  .header-text h1 {{
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.2px;
    line-height: 1.2;
  }}
  .header-text p {{
    font-size: 11.5px;
    color: var(--text-secondary);
    font-weight: 500;
    line-height: 1.2;
    margin-top: 1px;
  }}
  .gear-btn {{
    width: 28px;
    height: 28px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #94A3B8;
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  }}
  .gear-btn:hover {{
    background: rgba(255, 255, 255, 0.12);
    color: #FFFFFF;
    transform: rotate(30deg);
  }}

  /* Cards */
  .mode-cards {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .mode-card {{
    display: flex;
    align-items: center;
    padding: 10px 12px;
    border-radius: 13px;
    background: var(--card-normal-bg);
    border: 1px solid var(--card-normal-border);
    gap: 12px;
    cursor: pointer;
    transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  }}
  .mode-card:hover {{
    background: rgba(255, 255, 255, 0.07);
    border-color: rgba(255, 255, 255, 0.15);
  }}
  .mode-card.active {{
    background: var(--card-active-bg);
    border: 1.5px solid var(--card-active-border);
    box-shadow: var(--card-active-glow), inset 0 1px 0 rgba(255, 255, 255, 0.2);
  }}
  
  /* Radio Indicator */
  .radio-indicator {{
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1.5px solid rgba(255, 255, 255, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.25s ease;
    flex-shrink: 0;
  }}
  .mode-card.active .radio-indicator {{
    border-color: var(--blue-accent);
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.5);
  }}
  .radio-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--blue-accent);
    opacity: 0;
    transform: scale(0.4);
    transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
    box-shadow: var(--blue-glow);
  }}
  .mode-card.active .radio-dot {{
    opacity: 1;
    transform: scale(1);
  }}

  .card-content {{
    flex: 1;
  }}
  .card-title {{
    font-size: 13.5px;
    font-weight: 600;
    color: #FFFFFF;
    line-height: 1.2;
  }}
  .card-subtitle {{
    font-size: 11.5px;
    color: var(--text-secondary);
    margin-top: 2px;
    line-height: 1.2;
  }}

  /* Switches Section */
  .switches-section {{
    display: flex;
    flex-direction: column;
    gap: 9px;
    padding-top: 4px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }}
  .switch-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}
  .switch-left {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .switch-icon-box {{
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #38BDF8;
    flex-shrink: 0;
  }}
  .switch-label-title {{
    font-size: 12.5px;
    font-weight: 600;
    color: #FFFFFF;
    line-height: 1.2;
  }}
  .switch-label-subtitle {{
    font-size: 10.5px;
    color: var(--text-secondary);
    line-height: 1.2;
    margin-top: 2px;
  }}

  /* iOS Style Liquid Toggle */
  .ios-switch {{
    width: 42px;
    height: 24px;
    border-radius: 12px;
    background: rgba(255, 255, 255, 0.18);
    position: relative;
    cursor: pointer;
    transition: background 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease;
    flex-shrink: 0;
  }}
  .ios-switch.on {{
    background: #3B82F6;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.6);
  }}
  .ios-thumb {{
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #FFFFFF;
    position: absolute;
    top: 2px;
    left: 2px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.35);
    transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  }}
  .ios-switch.on .ios-thumb {{
    transform: translateX(18px);
  }}

  /* Action Button */
  .action-btn {{
    width: 100%;
    height: 38px;
    border-radius: 11px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #FFFFFF;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.25);
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    margin-top: auto;
    -webkit-appearance: none;
    appearance: none;
    outline: none;
  }}
  .action-btn:hover {{
    background: rgba(255, 255, 255, 0.15);
    border-color: rgba(255, 255, 255, 0.25);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
  }}
  .action-btn:active {{
    transform: scale(0.98);
  }}
  .action-btn.stopped {{
    background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%);
    border-color: rgba(59, 130, 246, 0.7);
    box-shadow: 0 0 16px rgba(59, 130, 246, 0.4);
  }}

  /* Settings Expandable Panel (Detailed Mode) */
  .settings-panel {{
    display: none;
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(0, 0, 0, 0.38);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 13px;
    animation: fadeIn 0.25s ease;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
  }}
  .settings-panel.open {{
    display: flex;
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(-6px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  .field-row {{
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: relative;
  }}
  .field-label {{
    font-size: 11px;
    font-weight: 600;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .field-input, .field-select {{
    width: 100%;
    height: 32px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 8px;
    padding: 0 10px;
    color: #FFFFFF;
    font-size: 12.5px;
    outline: none;
    transition: all 0.2s ease;
  }}
  .field-input:focus, .field-select:focus {{
    border-color: var(--blue-accent);
    background: rgba(255, 255, 255, 0.13);
    box-shadow: 0 0 10px rgba(56, 189, 248, 0.35);
  }}
  .field-select option {{
    background: #131722;
    color: #FFFFFF;
    padding: 6px;
  }}

  /* Champion Searcher Container */
  .champ-picker-wrap {{
    display: flex;
    align-items: center;
    gap: 10px;
    position: relative;
  }}
  .champ-avatar-box {{
    position: relative;
    flex-shrink: 0;
  }}
  .champ-avatar {{
    width: 36px;
    height: 36px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.1);
    border: 1.5px solid rgba(56, 189, 248, 0.5);
    object-fit: cover;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    transition: transform 0.2s ease;
  }}
  .champ-avatar:hover {{
    transform: scale(1.05);
  }}
  .champ-search-box {{
    position: relative;
    flex: 1;
  }}
  .champ-search-input {{
    padding-left: 28px !important;
  }}
  .champ-search-icon {{
    position: absolute;
    left: 9px;
    top: 9px;
    color: #94A3B8;
    pointer-events: none;
  }}

  /* Champion Autocomplete Dropdown */
  .champ-dropdown {{
    position: absolute;
    top: calc(100% + 6px);
    left: 0;
    right: 0;
    max-height: 180px;
    overflow-y: auto;
    background: rgba(14, 18, 28, 0.97);
    border: 1px solid rgba(56, 189, 248, 0.4);
    border-radius: 10px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.8), 0 0 16px rgba(56, 189, 248, 0.2);
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    z-index: 9999;
    display: none;
    flex-direction: column;
    padding: 4px;
  }}
  .champ-dropdown.open {{
    display: flex;
  }}
  .champ-dropdown-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .champ-dropdown-item:hover, .champ-dropdown-item.active {{
    background: rgba(56, 189, 248, 0.2);
    border-left: 3px solid #38BDF8;
  }}
  .champ-item-icon {{
    width: 26px;
    height: 26px;
    border-radius: 5px;
    object-fit: cover;
    background: rgba(255, 255, 255, 0.05);
    flex-shrink: 0;
  }}
  .champ-item-name {{
    font-size: 12px;
    font-weight: 500;
    color: #FFFFFF;
  }}
  .champ-no-results {{
    padding: 10px;
    font-size: 11.5px;
    color: #94A3B8;
    text-align: center;
    font-style: italic;
  }}

  .rank-row {{
    display: flex;
    gap: 8px;
  }}
  .custom-gamemode-box {{
    margin-top: 4px;
    display: none;
  }}
  .custom-gamemode-box.open {{
    display: block;
  }}

  /* View panels for Main vs Config views */
  .view-panel {{
    display: none;
    flex-direction: column;
    flex: 1;
    width: 100%;
  }}
  .view-panel.active {{
    display: flex;
  }}
  .view-panel#view-config {{
    overflow-y: auto;
    max-height: 520px;
    padding-right: 4px;
  }}
  #view-config::-webkit-scrollbar {{
    display: block;
    width: 4px;
  }}
  #view-config::-webkit-scrollbar-track {{
    background: transparent;
  }}
  #view-config::-webkit-scrollbar-thumb {{
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
  }}
  .buttons-config-group {{
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 2px;
  }}
  .btn-config-card {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 9px;
    padding: 9px 10px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    transition: border-color 0.2s ease, background 0.2s ease;
  }}
  .btn-config-card:hover {{
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.14);
  }}
  .btn-config-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10.5px;
    font-weight: 600;
    color: #94A3B8;
  }}
  .btn-fields-grid {{
    display: flex;
    flex-direction: column;
    gap: 6px;
  }}

  /* Dedicated Config Screen */
  .config-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }}
  .back-btn {{
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #38BDF8;
    font-size: 11.5px;
    font-weight: 600;
    padding: 6px 10px;
    cursor: pointer;
    transition: all 0.2s ease;
  }}
  .back-btn:hover {{
    background: rgba(56, 189, 248, 0.15);
    border-color: rgba(56, 189, 248, 0.4);
    transform: translateX(-2px);
  }}
  .config-title-box {{
    text-align: right;
  }}
  .config-title {{
    font-size: 13px;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: -0.2px;
  }}
  .config-subtitle {{
    font-size: 10px;
    color: #94A3B8;
  }}
  .config-section {{
    display: flex;
    flex-direction: column;
    gap: 11px;
  }}
  .field-label-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }}
  .reset-link {{
    font-size: 10.5px;
    color: #38BDF8;
    cursor: pointer;
    text-decoration: underline;
    opacity: 0.85;
    transition: opacity 0.2s;
  }}
  .reset-link:hover {{
    opacity: 1;
  }}
  .monospace-input {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.3px;
  }}
  .config-feedback {{
    min-height: 18px;
    font-size: 11px;
    font-weight: 500;
    color: #38BDF8;
    text-align: center;
    padding: 2px 0;
    transition: all 0.2s ease;
  }}
  .save-config-btn {{
    width: 100%;
    height: 38px;
    background: linear-gradient(135deg, #5865F2 0%, #4752C4 100%);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 9px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(88, 101, 242, 0.4);
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 4px;
  }}
  .save-config-btn:hover {{
    filter: brightness(1.1);
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(88, 101, 242, 0.6);
  }}
  .save-config-btn:active {{
    transform: translateY(1px);
  }}
  .preset-badge {{
    display: inline-block;
    padding: 2px 6px;
    background: rgba(56, 189, 248, 0.15);
    border-radius: 4px;
    color: #38BDF8;
    font-size: 9.5px;
    font-weight: 600;
    margin-left: 6px;
  }}

  /* Quit Button Styles */
  .quit-row {{
    display: flex;
    justify-content: center;
    align-items: center;
    margin-top: 10px;
    padding-bottom: 2px;
  }}
  .quit-btn {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: transparent;
    border: none;
    color: #94A3B8;
    font-size: 11.5px;
    font-weight: 500;
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 6px;
    transition: all 0.2s ease;
  }}
  .quit-btn:hover {{
    color: #EF4444;
    background: rgba(239, 68, 68, 0.1);
  }}
  .quit-btn svg {{
    transition: transform 0.2s ease;
  }}
  .quit-btn:hover svg {{
    transform: scale(1.1);
  }}
  .quit-app-btn {{
    width: 100%;
    height: 36px;
    background: rgba(239, 68, 68, 0.12);
    border: 1px solid rgba(239, 68, 68, 0.35);
    border-radius: 9px;
    color: #F87171;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
    cursor: pointer;
    transition: all 0.2s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 10px;
  }}
  .quit-app-btn:hover {{
    background: rgba(239, 68, 68, 0.25);
    border-color: rgba(239, 68, 68, 0.6);
    color: #EF4444;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(239, 68, 68, 0.25);
  }}
  .quit-app-btn:active {{
    transform: translateY(1px);
  }}
  .action-btn *,
  .quit-btn *,
  .quit-app-btn *,
  .mode-card *,
  .ios-switch *,
  .gear-btn *,
  .back-btn *,
  .save-config-btn * {{
    pointer-events: none;
  }}
  .quit-btn, .quit-app-btn {{
    -webkit-appearance: none;
    appearance: none;
  }}

  /* Toast Notification Container & Items */
  .toast-container {{
    position: fixed;
    top: 12px;
    left: 12px;
    right: 12px;
    z-index: 99999;
    pointer-events: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .toast {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 11.5px;
    font-weight: 500;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    opacity: 0;
    transform: translateY(-8px);
    transition: opacity 0.3s ease, transform 0.3s ease;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
    pointer-events: auto;
  }}
  .toast.show {{
    opacity: 1;
    transform: translateY(0);
  }}
  .toast-error {{
    background: rgba(45, 15, 15, 0.92);
    border: 1px solid rgba(239, 68, 68, 0.5);
    color: #FCA5A5;
  }}
  .toast-warning {{
    background: rgba(45, 30, 10, 0.92);
    border: 1px solid rgba(245, 158, 11, 0.5);
    color: #FCD34D;
  }}
  .toast-info {{
    background: rgba(15, 25, 45, 0.92);
    border: 1px solid rgba(59, 130, 246, 0.5);
    color: #93C5FD;
  }}
  .toast-icon {{
    flex-shrink: 0;
    font-size: 13px;
  }}
  .toast-msg {{
    flex: 1;
    word-break: break-word;
    line-height: 1.35;
  }}
</style>
</head>
<body>
  <div class="liquid-container">
    <!-- In-App Error & Notification Toast Container -->
    <div id="toast-container" class="toast-container"></div>

    <!-- VIEW 1: MAIN PRESENCE SCREEN -->
    <div id="view-main" class="view-panel active">
      <!-- Header -->
      <div class="header">
        <div class="header-left">
          {DISCORD_SVG}
          <div class="header-text">
            <h1>Discord RPC</h1>
            <p id="main-subtitle">League of Legends</p>
          </div>
        </div>
        <div class="gear-btn" onclick="openConfigView()" title="Configuración de Juegos y Client ID">
          {GEAR_SVG}
        </div>
      </div>

      <!-- Mode Cards -->
      <div class="mode-cards">
        <!-- Card 1: Modo Oficial -->
        <div class="mode-card active" id="card-oficial" onclick="sendAction('select_mode', {{mode: 'oficial'}})">
          <div class="radio-indicator">
            <div class="radio-dot"></div>
          </div>
          <div class="card-content">
            <div class="card-title">Modo Oficial</div>
            <div class="card-subtitle">Solo Juego + Tiempo</div>
          </div>
        </div>

        <!-- Card 2: Modo Detallado -->
        <div class="mode-card" id="card-detallado" onclick="sendAction('select_mode', {{mode: 'detallado'}})">
          <div class="radio-indicator">
            <div class="radio-dot"></div>
          </div>
          <div class="card-content">
            <div class="card-title">Modo Detallado</div>
            <div class="card-subtitle">Campeón, Rango y Modo</div>
          </div>
        </div>
      </div>

      <!-- Settings Panel (Expandable for detailed mode) -->
      <div class="settings-panel" id="panel-settings">
        <!-- Champion Searcher with Live Avatars -->
        <div class="field-row">
          <label class="field-label">
            <span>Campeón</span>
            <span style="font-size: 9.5px; color: #38BDF8; font-weight: 500;">173 disponibles</span>
          </label>
          <div class="champ-picker-wrap">
            <div class="champ-avatar-box">
              <img id="champ-avatar" class="champ-avatar" src="" alt="Avatar" onerror="this.src='https://ddragon.leagueoflegends.com/cdn/{FALLBACK_VERSION}/img/champion/Malzahar.png'">
            </div>
            <div class="champ-search-box">
              <div class="champ-search-icon">
                {SEARCH_SVG}
              </div>
              <input type="text" id="champ-input" class="field-input champ-search-input" placeholder="Buscar campeón (ej. Yasuo, Jinx, Ahri)..." autocomplete="off" onfocus="openChampDropdown()" oninput="filterChampions(this.value)" onchange="sendAction('change_champion', {{ name: this.value.trim() }})">
              <!-- Autocomplete Dropdown -->
              <div id="champ-dropdown" class="champ-dropdown"></div>
            </div>
          </div>
        </div>

        <!-- Rank & Division Selection -->
        <div class="rank-row">
          <div class="field-row" style="flex: 2;">
            <label class="field-label">Rango</label>
            <select id="rank-select" class="field-select" onchange="sendAction('change_rank', {{rank: this.value}})">
              <option value="Hierro">Hierro</option>
              <option value="Bronce">Bronce</option>
              <option value="Plata">Plata</option>
              <option value="Oro">Oro</option>
              <option value="Platino">Platino</option>
              <option value="Esmeralda">Esmeralda</option>
              <option value="Diamante">Diamante</option>
              <option value="Maestro">Maestro</option>
              <option value="Gran Maestro">Gran Maestro</option>
              <option value="Challenger">Challenger</option>
              <option value="Unranked">Unranked</option>
            </select>
          </div>

          <div class="field-row" id="division-container" style="flex: 1;">
            <label class="field-label">División</label>
            <select id="division-select" class="field-select" onchange="sendAction('change_division', {{division: this.value}})">
              <option value="I">I</option>
              <option value="II">II</option>
              <option value="III">III</option>
              <option value="IV">IV</option>
            </select>
          </div>
        </div>

        <!-- Game Mode Selection (Dropdown + Custom Text fallback) -->
        <div class="field-row">
          <label class="field-label">Modo de Juego</label>
          <select id="gamemode-select" class="field-select" onchange="onGameModeSelect(this.value)">
            {game_modes_options_html}
            <option value="__custom__">✏️ Personalizado (Escribir texto libre)...</option>
          </select>
          <div id="custom-gamemode-wrap" class="custom-gamemode-box">
            <input type="text" id="gamemode-input" class="field-input" placeholder="Escribe el modo de juego..." onchange="sendAction('change_game_mode', {{game_mode: this.value}})">
          </div>
        </div>
      </div>

      <!-- Switches Section -->
      <div class="switches-section">
        <!-- Switch 1: Auto-reset -->
        <div class="switch-row">
          <div class="switch-left">
            <div class="switch-icon-box">
              {SYNC_SVG}
            </div>
            <div>
              <div class="switch-label-title">Reiniciar partida</div>
              <div class="switch-label-subtitle">automáticamente cada 20–30 min</div>
            </div>
          </div>
          <div class="ios-switch on" id="switch-autoreset" onclick="toggleSwitch('autoreset')">
            <div class="ios-thumb"></div>
          </div>
        </div>

        <!-- Switch 2: Auto-run -->
        <div class="switch-row">
          <div class="switch-left">
            <div class="switch-icon-box">
              {LAPTOP_SVG}
            </div>
            <div>
              <div class="switch-label-title">Iniciar automáticamente</div>
              <div class="switch-label-subtitle">con macOS (Auto-run)</div>
            </div>
          </div>
          <div class="ios-switch" id="switch-autorun" onclick="toggleSwitch('autorun')">
            <div class="ios-thumb"></div>
          </div>
        </div>
      </div>

      <!-- Action Button -->
      <button type="button" class="action-btn" id="btn-action" onclick="sendAction('action_button')">
        <span id="btn-icon">■</span>
        <span id="btn-text">DETENER EN DISCORD</span>
      </button>

      <!-- Quit Application Control -->
      <div class="quit-row">
        <button class="quit-btn" onclick="sendAction('quit_app')" title="Salir de Discord RPC">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
            <line x1="12" y1="2" x2="12" y2="12"></line>
          </svg>
          <span>Salir de la aplicación</span>
        </button>
      </div>
    </div>

    <!-- VIEW 2: DEDICATED CONFIGURATION & PRESETS SCREEN -->
    <div id="view-config" class="view-panel">
      <!-- Config Header -->
      <div class="config-header">
        <button class="back-btn" onclick="closeConfigView()">
          <span>← Volver</span>
        </button>
        <div class="config-title-box">
          <div class="config-title">Configuración & Juegos</div>
          <div class="config-subtitle">Top 10 Presets & Client ID</div>
        </div>
      </div>

      <div class="config-section">
        <!-- Game Preset Dropdown -->
        <div class="field-row">
          <div class="field-label-row">
            <label class="field-label" style="margin-bottom: 0;">Juego (Top 10 Más Jugados)</label>
            <span class="preset-badge" id="badge-game-status">Oficial</span>
          </div>
          <select id="config-game-select" class="field-select" onchange="onGamePresetChange(this.value)">
            <option value="lol">🏆 League of Legends (Riot Games)</option>
            <option value="valorant">🎯 VALORANT (Riot Games)</option>
            <option value="cs2">🔫 Counter-Strike 2 (Valve)</option>
            <option value="minecraft">⛏️ Minecraft (Mojang)</option>
            <option value="fortnite">🪂 Fortnite (Epic Games)</option>
            <option value="gtav">🚗 Grand Theft Auto V (Rockstar)</option>
            <option value="apex">⚡ Apex Legends (Respawn / EA)</option>
            <option value="overwatch2">🛡️ Overwatch 2 (Blizzard)</option>
            <option value="dota2">⚔️ Dota 2 (Valve)</option>
            <option value="rocketleague">🚀 Rocket League (Psyonix)</option>
            <option value="custom">✏️ Personalizado (Client ID propio)...</option>
          </select>
        </div>

        <!-- Discord Client ID -->
        <div class="field-row">
          <div class="field-label-row">
            <label class="field-label" style="margin-bottom: 0;">Discord Application Client ID</label>
            <span class="reset-link" onclick="restoreDefaultClientId()">Restaurar Oficial</span>
          </div>
          <input type="text" id="config-client-id" class="field-input monospace-input" placeholder="Client ID de Discord..." oninput="onClientIdInput()">
        </div>

        <!-- Status Details -->
        <div class="field-row">
          <label class="field-label">Estado de la Presencia (Details)</label>
          <input type="text" id="config-details" class="field-input" placeholder="Ej: En partida, Competitivo...">
        </div>

        <!-- Match Duration -->
        <div class="field-row">
          <label class="field-label">Duración Estimada de Partida</label>
          <select id="config-duration" class="field-select">
            <option value="15">15 minutos (Partidas cortas)</option>
            <option value="20">20 minutos (Fortnite / ARAM)</option>
            <option value="25">25 minutos (Recomendado LoL)</option>
            <option value="30">30 minutos (CS2 / Shooter)</option>
            <option value="35">35 minutos (VALORANT / Competitivo)</option>
            <option value="45">45 minutos (Minecraft / Dota 2)</option>
            <option value="60">60 minutos (GTA V / Sesión libre)</option>
          </select>
        </div>

        <!-- Interactive Discord Profile Buttons (Requirement R2) -->
        <div class="field-row">
          <div class="field-label-row">
            <label class="field-label" style="margin-bottom: 0;">Botones Interactivos de Discord</label>
            <span style="font-size: 9.5px; color: #94A3B8;">Máx. 2 botones (HTTPS)</span>
          </div>
          <div class="buttons-config-group">
            <!-- Button 1 Card -->
            <div class="btn-config-card">
              <div class="btn-config-header">
                <span>Botón 1</span>
                <span style="font-size: 9px; color: #64748B;">Perfil / Stream / Web</span>
              </div>
              <div class="btn-fields-grid">
                <input type="text" id="config-btn1-label" class="field-input" maxlength="32" placeholder="Texto del botón (ej. Ver OP.GG, Twitch)...">
                <input type="text" id="config-btn1-url" class="field-input monospace-input" maxlength="512" placeholder="URL (ej. https://op.gg/summoners/...)">
              </div>
            </div>

            <!-- Button 2 Card -->
            <div class="btn-config-card">
              <div class="btn-config-header">
                <span>Botón 2</span>
                <span style="font-size: 9px; color: #64748B;">Comunidad / Discord</span>
              </div>
              <div class="btn-fields-grid">
                <input type="text" id="config-btn2-label" class="field-input" maxlength="32" placeholder="Texto del botón (ej. Servidor de Discord)...">
                <input type="text" id="config-btn2-url" class="field-input monospace-input" maxlength="512" placeholder="URL (ej. https://discord.gg/...)">
              </div>
            </div>
          </div>
        </div>

        <!-- Feedback message -->
        <div id="config-feedback" class="config-feedback"></div>

        <!-- Save Button -->
        <button class="save-config-btn" onclick="saveConfig()">
          <span>💾 GUARDAR Y RECONECTAR</span>
        </button>

        <!-- Quit Application Danger Button -->
        <button class="quit-app-btn" onclick="sendAction('quit_app')" title="Salir completamente de la aplicación">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
            <polyline points="16 17 21 12 16 7"></polyline>
            <line x1="21" y1="12" x2="9" y2="12"></line>
          </svg>
          <span>Salir de la aplicación</span>
        </button>
      </div>
    </div>
  </div>

  <script>
    const ALL_CHAMPIONS = {champions_json_str};
    let currentState = {json.dumps(initial_state)};
    let highlightedIndex = -1;

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }}

    window.showToast = function(message, type, duration) {{
      type = type || 'error';
      duration = duration || 3500;
      const container = document.getElementById('toast-container');
      if (!container) return;
      const toast = document.createElement('div');
      toast.className = 'toast toast-' + type;
      const icon = type === 'error' ? '⚠️' : (type === 'warning' ? '⚡' : 'ℹ️');
      toast.innerHTML = '<span class="toast-icon">' + icon + '</span><span class="toast-msg">' + escapeHtml(message) + '</span>';
      container.appendChild(toast);
      requestAnimationFrame(function() {{
        toast.classList.add('show');
      }});
      setTimeout(function() {{
        toast.classList.remove('show');
        setTimeout(function() {{
          if (toast.parentNode) toast.parentNode.removeChild(toast);
        }}, 350);
      }}, duration);
    }};

    window.addEventListener('error', function(e) {{
      window.showToast((e && e.message) || "Error en interfaz gráfica", "error");
    }});
    window.addEventListener('unhandledrejection', function(e) {{
      const reason = (e && e.reason && e.reason.message) || (e && e.reason) || "Error en operación asíncrona";
      window.showToast(String(reason), "error");
    }});

    function sendAction(action, data) {{
      try {{
        console.log("sendAction dispatched:", action, data);
        const payload = Object.assign({{ action: action }}, data || {{}});
        if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.lolrpc) {{
          window.webkit.messageHandlers.lolrpc.postMessage(payload);
        }} else {{
          console.warn("lolrpc handler missing on window.webkit for action:", action);
        }}
      }} catch (e) {{
        console.error("sendAction error:", e);
      }}
    }}

    function toggleSwitch(name) {{
      if (name === 'autoreset') {{
        const next = !currentState.autoreset;
        currentState.autoreset = next;
        document.getElementById('switch-autoreset').classList.toggle('on', next);
        sendAction('toggle_autoreset', {{ value: next }});
      }} else if (name === 'autorun') {{
        const next = !currentState.autorun;
        currentState.autorun = next;
        document.getElementById('switch-autorun').classList.toggle('on', next);
        sendAction('toggle_autorun', {{ value: next }});
      }}
    }}

    /* =========================================================================
       Champion Searcher & Dropdown Logic
       ========================================================================= */
    const champInput = document.getElementById('champ-input');
    const champDropdown = document.getElementById('champ-dropdown');
    const champAvatar = document.getElementById('champ-avatar');

    function openChampDropdown() {{
      filterChampions(champInput.value);
      champDropdown.classList.add('open');
    }}

    function closeChampDropdown() {{
      champDropdown.classList.remove('open');
      highlightedIndex = -1;
    }}

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
      highlightedIndex = -1;
      const q = (query || '').toLowerCase().trim();
      champDropdown.innerHTML = '';
      const aliasTarget = ALIAS_MAP[q] ? ALIAS_MAP[q].toLowerCase() : '';

      const filtered = ALL_CHAMPIONS.filter(c => {{
        if (!q) return true;
        const nameClean = c.name.toLowerCase().replace(/[^a-z0-9]/g, '');
        const idClean = c.id.toLowerCase();
        const qClean = q.replace(/[^a-z0-9]/g, '');
        return c.name.toLowerCase().includes(q) || nameClean.includes(qClean) || idClean.includes(qClean) || (aliasTarget && c.name.toLowerCase().includes(aliasTarget));
      }});

      if (filtered.length === 0) {{
        const noRes = document.createElement('div');
        noRes.className = 'champ-no-results';
        noRes.textContent = 'No se encontró ningún campeón';
        champDropdown.appendChild(noRes);
      }} else {{
        filtered.slice(0, 35).forEach((champ, idx) => {{
          const item = document.createElement('div');
          item.className = 'champ-dropdown-item';
          item.innerHTML = `
            <img src="${{champ.icon}}" class="champ-item-icon" loading="lazy" onerror="this.style.opacity='0.4'">
            <span class="champ-item-name">${{champ.name}}</span>
          `;
          item.onmousedown = (e) => {{
            e.preventDefault();
            selectChampion(champ);
          }};
          champDropdown.appendChild(item);
        }});
      }}
      champDropdown.classList.add('open');
    }}

    function selectChampion(champ) {{
      champInput.value = champ.name;
      champAvatar.src = champ.icon;
      closeChampDropdown();
      sendAction('change_champion', {{ name: champ.name }});
    }}

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {{
      if (!e.target.closest('.champ-search-box')) {{
        closeChampDropdown();
      }}
    }});

    // Keyboard navigation in search input
    champInput.addEventListener('keydown', (e) => {{
      const items = champDropdown.querySelectorAll('.champ-dropdown-item');
      if (e.key === 'ArrowDown') {{
        e.preventDefault();
        highlightedIndex = Math.min(highlightedIndex + 1, items.length - 1);
        updateHighlight(items);
      }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        updateHighlight(items);
      }} else if (e.key === 'Enter') {{
        e.preventDefault();
        if (highlightedIndex >= 0 && items[highlightedIndex]) {{
          items[highlightedIndex].onmousedown(e);
        }} else if (champInput.value.trim()) {{
          sendAction('change_champion', {{ name: champInput.value.trim() }});
          closeChampDropdown();
        }}
      }} else if (e.key === 'Escape') {{
        closeChampDropdown();
      }}
    }});

    function updateHighlight(items) {{
      items.forEach((it, i) => {{
        it.classList.toggle('active', i === highlightedIndex);
        if (i === highlightedIndex) {{
          it.scrollIntoView({{ block: 'nearest' }});
        }}
      }});
    }}

    /* =========================================================================
       Game Mode Logic
       ========================================================================= */
    function onGameModeSelect(val) {{
      const customWrap = document.getElementById('custom-gamemode-wrap');
      const customInput = document.getElementById('gamemode-input');
      if (val === '__custom__') {{
        customWrap.classList.add('open');
        customInput.focus();
      }} else {{
        customWrap.classList.remove('open');
        customInput.value = val;
        sendAction('change_game_mode', {{ game_mode: val }});
      }}
    }}

    /* =========================================================================
       Top 10 Games Presets & Configuration Screen Logic
       ========================================================================= */
    const PRESETS = {{
      "lol": {{
        name: "League of Legends",
        client_id: "1402418696126992445",
        details: "En partida",
        duration: "25"
      }},
      "valorant": {{
        name: "VALORANT",
        client_id: "700142994017648710",
        details: "Competitivo",
        duration: "35"
      }},
      "cs2": {{
        name: "Counter-Strike 2",
        client_id: "1157771746215391302",
        details: "Premier Competitivo",
        duration: "30"
      }},
      "minecraft": {{
        name: "Minecraft",
        client_id: "698942205566877706",
        details: "Modo Supervivencia",
        duration: "45"
      }},
      "fortnite": {{
        name: "Fortnite",
        client_id: "432980957394370572",
        details: "Battle Royale",
        duration: "20"
      }},
      "gtav": {{
        name: "Grand Theft Auto V",
        client_id: "650800318536646696",
        details: "GTA Online / FiveM",
        duration: "60"
      }},
      "apex": {{
        name: "Apex Legends",
        client_id: "543884846435401729",
        details: "Tríos Clasificatorios",
        duration: "20"
      }},
      "overwatch2": {{
        name: "Overwatch 2",
        client_id: "446342898783453185",
        details: "Competitivo",
        duration: "20"
      }},
      "dota2": {{
        name: "Dota 2",
        client_id: "378854498308620288",
        details: "All Pick Clasificatoria",
        duration: "40"
      }},
      "rocketleague": {{
        name: "Rocket League",
        client_id: "379286088717369344",
        details: "Competitivo 3v3",
        duration: "15"
      }},
      "custom": {{
        name: "Personalizado",
        client_id: "",
        details: "Jugando",
        duration: "30"
      }}
    }};

    function openConfigView() {{
      sendAction('toggle_settings');
    }}

    function closeConfigView() {{
      sendAction('close_settings');
    }}

    function onGamePresetChange(gameId) {{
      const preset = PRESETS[gameId] || PRESETS['custom'];
      const clientIdInput = document.getElementById('config-client-id');
      const detailsInput = document.getElementById('config-details');
      const durationSelect = document.getElementById('config-duration');
      const badge = document.getElementById('badge-game-status');

      if (gameId === 'custom') {{
        if (badge) badge.textContent = 'Personalizado';
        clientIdInput.placeholder = 'Ingresa tu Discord Client ID...';
        clientIdInput.focus();
      }} else {{
        if (badge) badge.textContent = 'Oficial';
        clientIdInput.value = preset.client_id;
        detailsInput.value = preset.details;
        durationSelect.value = preset.duration;
      }}
    }}

    function restoreDefaultClientId() {{
      const gameSelect = document.getElementById('config-game-select');
      const gameId = gameSelect ? gameSelect.value : 'lol';
      const preset = PRESETS[gameId] || PRESETS['lol'];
      document.getElementById('config-client-id').value = preset.client_id;
      document.getElementById('config-details').value = preset.details;
      document.getElementById('config-duration').value = preset.duration;
      const fb = document.getElementById('config-feedback');
      if (fb) {{
        fb.textContent = '✓ Valores oficiales restaurados';
        setTimeout(() => {{ if (fb.textContent.includes('restaurados')) fb.textContent = ''; }}, 2500);
      }}
    }}

    function sanitizeBtn(labelRaw, urlRaw) {{
      let label = (labelRaw || '').trim();
      let url = (urlRaw || '').trim();
      if (!label || !url) return null;
      if (label.length > 32) label = label.substring(0, 32);
      if (url.startsWith('http://')) {{
        url = 'https://' + url.substring(7);
      }} else if (!url.startsWith('https://')) {{
        url = 'https://' + url;
      }}
      if (url.length > 512) url = url.substring(0, 512);
      return {{ label: label, url: url }};
    }}

    function saveConfig() {{
      const gameId = document.getElementById('config-game-select').value;
      const clientId = document.getElementById('config-client-id').value.trim();
      const details = document.getElementById('config-details').value.trim();
      const durationMin = parseInt(document.getElementById('config-duration').value, 10) || 25;

      const b1Label = document.getElementById('config-btn1-label') ? document.getElementById('config-btn1-label').value : '';
      const b1Url = document.getElementById('config-btn1-url') ? document.getElementById('config-btn1-url').value : '';
      const b2Label = document.getElementById('config-btn2-label') ? document.getElementById('config-btn2-label').value : '';
      const b2Url = document.getElementById('config-btn2-url') ? document.getElementById('config-btn2-url').value : '';

      const buttons = [];
      const btn1 = sanitizeBtn(b1Label, b1Url);
      if (btn1) buttons.push(btn1);
      const btn2 = sanitizeBtn(b2Label, b2Url);
      if (btn2) buttons.push(btn2);

      const fb = document.getElementById('config-feedback');
      if (fb) fb.textContent = '✓ Guardando y reconectando a Discord...';

      sendAction('save_config', {{
        game_id: gameId,
        client_id: clientId,
        details: details,
        duration_min: durationMin,
        buttons: buttons
      }});

      setTimeout(() => {{
        closeConfigView();
      }}, 500);
    }}

    /* =========================================================================
       State Synchronization from Cocoa / WebKit
       ========================================================================= */
    window.updateLiquidUI = function(state) {{
      if (!state) return;
      currentState = Object.assign(currentState, state);

      // View switching between #view-main and #view-config
      const viewMain = document.getElementById('view-main');
      const viewConfig = document.getElementById('view-config');
      if (viewMain && viewConfig) {{
        if (currentState.settings_expanded) {{
          viewMain.classList.remove('active');
          viewConfig.classList.add('active');
        }} else {{
          viewConfig.classList.remove('active');
          viewMain.classList.add('active');
        }}
      }}

      // Populate config fields
      if (currentState.selected_game_id) {{
        const gSelect = document.getElementById('config-game-select');
        if (gSelect) gSelect.value = currentState.selected_game_id;
        const badge = document.getElementById('badge-game-status');
        if (badge) {{
          badge.textContent = currentState.selected_game_id === 'custom' ? 'Personalizado' : 'Oficial';
        }}
      }}
      const cidInput = document.getElementById('config-client-id');
      if (cidInput && currentState.client_id && document.activeElement !== cidInput) {{
        cidInput.value = currentState.client_id;
      }}
      const detInput = document.getElementById('config-details');
      if (detInput && currentState.custom_details && document.activeElement !== detInput) {{
        detInput.value = currentState.custom_details;
      }}
      const durSelect = document.getElementById('config-duration');
      if (durSelect && currentState.match_duration_min) {{
        durSelect.value = String(currentState.match_duration_min);
      }}

      // Populate button inputs
      if (Array.isArray(currentState.buttons)) {{
        const b1 = currentState.buttons[0] || {{}};
        const b2 = currentState.buttons[1] || {{}};
        const b1LabelInput = document.getElementById('config-btn1-label');
        const b1UrlInput = document.getElementById('config-btn1-url');
        const b2LabelInput = document.getElementById('config-btn2-label');
        const b2UrlInput = document.getElementById('config-btn2-url');

        if (b1LabelInput && document.activeElement !== b1LabelInput) {{
          b1LabelInput.value = b1.label || '';
        }}
        if (b1UrlInput && document.activeElement !== b1UrlInput) {{
          b1UrlInput.value = b1.url || '';
        }}
        if (b2LabelInput && document.activeElement !== b2LabelInput) {{
          b2LabelInput.value = b2.label || '';
        }}
        if (b2UrlInput && document.activeElement !== b2UrlInput) {{
          b2UrlInput.value = b2.url || '';
        }}
      }}

      // Subtitle
      const sub = document.getElementById('main-subtitle');
      if (sub && currentState.selected_game_id) {{
        const p = PRESETS[currentState.selected_game_id];
        sub.textContent = p ? p.name : 'League of Legends';
      }}

      // Mode cards
      const isOfficial = currentState.mode === 'oficial';
      document.getElementById('card-oficial').classList.toggle('active', isOfficial);
      document.getElementById('card-detallado').classList.toggle('active', !isOfficial);

      // Switches
      document.getElementById('switch-autoreset').classList.toggle('on', !!currentState.autoreset);
      document.getElementById('switch-autorun').classList.toggle('on', !!currentState.autorun);

      // Action button
      const btn = document.getElementById('btn-action');
      const btnIcon = document.getElementById('btn-icon');
      const btnText = document.getElementById('btn-text');
      if (currentState.presence_active) {{
        btn.classList.remove('stopped');
        btnIcon.textContent = '■';
        btnText.textContent = 'DETENER EN DISCORD';
      }} else {{
        btn.classList.add('stopped');
        btnIcon.textContent = '▶';
        btnText.textContent = 'INICIAR PRESENCIA';
      }}

      // Settings panel expansion
      const panel = document.getElementById('panel-settings');
      panel.classList.toggle('open', !isOfficial);

      // Champion
      if (currentState.champion) {{
        if (document.activeElement !== champInput) {{
          champInput.value = currentState.champion;
        }}
      }}
      if (currentState.champ_url) {{
        champAvatar.src = currentState.champ_url;
      }}

      // Rank & Division
      if (currentState.rank) {{
        document.getElementById('rank-select').value = currentState.rank;
      }}
      if (currentState.division) {{
        document.getElementById('division-select').value = currentState.division;
      }}

      // Game Mode
      if (currentState.game_mode) {{
        const select = document.getElementById('gamemode-select');
        const customWrap = document.getElementById('custom-gamemode-wrap');
        const customInput = document.getElementById('gamemode-input');
        
        let found = false;
        for (let i = 0; i < select.options.length; i++) {{
          if (select.options[i].value === currentState.game_mode) {{
            select.selectedIndex = i;
            found = true;
            break;
          }}
        }}

        if (!found) {{
          select.value = '__custom__';
          customWrap.classList.add('open');
          customInput.value = currentState.game_mode;
        }} else {{
          customWrap.classList.remove('open');
          customInput.value = currentState.game_mode;
        }}
      }}

      // Division visibility for apex tiers
      const divContainer = document.getElementById('division-container');
      if (divContainer) {{
        divContainer.style.display = currentState.is_apex ? 'none' : 'flex';
      }}
    }};

    // Initialize with current state
    window.updateLiquidUI(currentState);
  </script>
</body>
</html>
"""


# Compatibility alias
def render_app_html(initial_state: Optional[Dict[str, Any]] = None) -> str:
    """Renders application HTML with optional initial state."""
    if initial_state is None:
        initial_state = {}
    return generate_liquid_html(initial_state)
