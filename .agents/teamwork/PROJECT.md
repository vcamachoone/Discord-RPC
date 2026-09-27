# Project: Discord RPC League of Legends macOS Redesign

## Architecture
The redesign transitions the application from a textual `rumps` menu to a native macOS `NSPopover` dark interface anchored to an `NSStatusItem`, backed by a thread-safe actor-model Discord Rich Presence engine and Riot Data Dragon integration.

```
┌──────────────────────────────────────────────────────────────┐
│             macOS Status Bar (NSStatusBar)                   │
│                    [ NSStatusItem ]                          │
│             Dynamic Icon: Normal / Active / Paused           │
└──────────────────────────────┬───────────────────────────────┘
                               │ Click
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                 NSPopover (Dark Aqua HUD)                    │
│  - Header: Discord Icon + Title + Subtitle + [⚙ Settings]    │
│  - Mode Cards: Modo Oficial vs Modo Detallado                │
│  - Switches: Reiniciar partida + Iniciar con macOS           │
│  - Action Button: [ ⏹ DETENER EN DISCORD / ▶ INICIAR ]       │
│  - Settings View: Champion Selector + Rank + Division        │
└──────────────────────────────┬───────────────────────────────┘
                               │ State / Command Queue
                               ▼
┌──────────────────────────────────────────────────────────────┐
│               DiscordRPCManager (Actor Model)                │
│  - Background worker thread with asyncio pypresence loop     │
│  - Thread-safe queue.Queue input                             │
│  - Auto-reconnect resilience on Discord restart              │
│  - Randomized 20-30 min match auto-restart timer             │
│  - PyObjCTools.AppHelper.callAfter for main-thread UI updates│
└──────────────────────────────┬───────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌──────────────────────────────┐    ┌──────────────────────────┐
│   lol_champions.py           │    │   lol_ranks.py           │
│   Riot Data Dragon resolver  │    │   CommunityDragon crests │
│   9 Riot internal ID maps    │    │   Apex tier suppression  │
└──────────────────────────────┘    └──────────────────────────┘
```

## Feature Inventory
Every feature identified during the survey phase is mapped to a specific milestone:
| # | Feature | Description | Milestone | Source |
|---|---|---|---|---|
| F1 | Dynamic Menubar Icons | 3 icon states: Normal (monochrome template), Active (with blue status dot #00A8FC non-template), Paused (dimmed 35% alpha) | M1 | ORIGINAL_REQUEST §R2 |
| F2 | Menu Bar Item (NSStatusItem) | PyObjC status item with click handling to toggle NSPopover | M1 | ORIGINAL_REQUEST §R1 |
| F3 | Floating Dark NSPopover UI | Popover window anchored to status item with arrow, dark aqua HUD, header with Discord logo, titles, gear button | M2 | ORIGINAL_REQUEST §R1 |
| F4 | Interactive Mode Selector | Card/radio selection between Modo Oficial and Modo Detallado | M2 | ORIGINAL_REQUEST §R1 |
| F5 | Interactive Switches | NSSwitch for "Reiniciar partida" and "Iniciar con macOS" (login item) | M2 | ORIGINAL_REQUEST §R1 |
| F6 | Bottom Action Button | Prominent toggle button for Active / Stopped Discord presence | M2 | ORIGINAL_REQUEST §R1 |
| F7 | Settings / Detailed View | Panel to configure Champion, Rank, Division, and Game Mode | M2 | ORIGINAL_REQUEST §R3 |
| F8 | Champion Resolver & Data Dragon | Normalizes 173 champions including 9 Riot anomalies and Spanish variants to valid DDragon URLs | M3 | ORIGINAL_REQUEST §R3 |
| F9 | Rank Crests & Division Formatter | CommunityDragon rank crests, division suppression for Apex tiers (avoid "Challenger II") | M3 | ORIGINAL_REQUEST §R3 |
| F10 | Concurrency & Thread-Safe RPC Manager | Single background worker thread, queue.Queue communication, PyObjC AppHelper.callAfter, auto-reconnect, no UI freezing | M3 | ORIGINAL_REQUEST §R4 |
| F11 | Auto-restart Match Timer | Randomized 20-30 min timer resetting match presence and elapsed time | M3 | ORIGINAL_REQUEST §R1 |
| F12 | App Bundle Packaging & Sync | Synchronization to /Applications/League of Legends RPC.app and launcher verification | M4 | ORIGINAL_REQUEST §R4 |
| F13 | End-to-End Test Suite | Comprehensive 5-tier test suite verifying UI, concurrency, DDragon, and bundle | E2E Track | PROJECT Pattern |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| E2E | E2E Testing Track | Requirement-driven opaque-box test suite (Tiers 1-4) producing TEST_READY.md | none | DONE |
| M1 | Dynamic Icons & Status Item | Asset generator (`assets_gen.py`) and status item controller (`status_item.py`) | none | DONE |
| M2 | Native Dark NSPopover UI | PyObjC Popover controller, dark visual effect view, mode cards, switches, buttons, and settings view (`popover_ui.py`) | M1 | DONE |
| M3 | Concurrency Manager & LoL Engine | Champion resolver (`lol_champions.py`), rank formatter (`lol_ranks.py`), and thread-safe RPC manager (`discord_rpc_manager.py`) | none | DONE |
| M4 | Application Integration & Bundle Sync | Master integration in `app_gui.py` and bundle synchronization to `/Applications/League of Legends RPC.app` | M1, M2, M3 | DONE |
| M5 | Final E2E Test Pass & Coverage Hardening | 100% pass of E2E test suite (149 tests across Tiers 1-5), Gate APPROVE by 2 Reviewers, 2 Challengers, and CLEAN by Auditor | M4, E2E | DONE |

## Interface Contracts

### assets_gen.py ↔ status_item.py
- `generate_status_icons(output_dir: str) -> Dict[str, str]`:
  Returns dictionary mapping states (`"normal"`, `"active"`, `"paused"`) to absolute PNG file paths.
- Icons are 44x44 px (Retina 22x22 pt) and 22x22 px (1x).
- `status_item.py` loads `NSImage` from file and calls `setTemplate_(True)` for `"normal"`, and `setTemplate_(False)` for `"active"` and `"paused"`.

### discord_rpc_manager.py ↔ popover_ui.py / app_gui.py
- `DiscordRPCManager(client_id: str, on_state_change: Callable[[str, str], None], on_match_reset: Callable[[int], None])`
- Methods:
  - `set_active(active: bool) -> None`: Non-blocking, enqueues `SET_ACTIVE`.
  - `update_presence_config(**kwargs) -> None`: Non-blocking, enqueues `CONFIG_CHANGE` with fields `mode`, `champion_name`, `champion_image_url`, `rank_text`, `rank_image_url`, `game_mode`, `autoreset`.
  - `restart_match() -> None`: Non-blocking, enqueues `RESTART_MATCH`.
  - `shutdown() -> None`: Terminates background worker gracefully.
- Callbacks:
  - `on_state_change(state: str, message: str)`: Called on main thread via `PyObjCTools.AppHelper.callAfter`. States: `disconnected`, `connecting`, `connected`, `paused`.
  - `on_match_reset(new_start_time: int)`: Called on main thread when auto-restart timer resets match.

### lol_champions.py ↔ popover_ui.py / discord_rpc_manager.py
- `ChampionResolver.resolve_champion(user_input: str) -> Tuple[str, str]`:
  Returns `(ddragon_id, display_name)`. Guarantees valid CDN ID.
- `ChampionResolver.get_square_icon_url(champion_id: str) -> str`:
  Returns `https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{champion_id}.png`.

### lol_ranks.py ↔ popover_ui.py / discord_rpc_manager.py
- `format_rank_display(tier: str, division: str = "II") -> str`:
  Formats rank string for Discord RPC. Suppresses division suffixes for Apex tiers (`Master`, `Grandmaster`, `Challenger`, `Unranked`).
- `get_rank_crest_url(tier: str) -> str`:
  Returns CommunityDragon URL for tier crest.

## Code Layout
- Project Root: `/Users/victormanuel/discord-rpc`
- Core Modules:
  - `/Users/victormanuel/discord-rpc/assets_gen.py` — Icon generator
  - `/Users/victormanuel/discord-rpc/status_item.py` — NSStatusItem controller
  - `/Users/victormanuel/discord-rpc/popover_ui.py` — NSPopover UI and views
  - `/Users/victormanuel/discord-rpc/lol_champions.py` — DDragon & champion resolver
  - `/Users/victormanuel/discord-rpc/lol_ranks.py` — Rank crests & formatting
  - `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` — Thread-safe RPC actor
  - `/Users/victormanuel/discord-rpc/app_gui.py` — Main macOS application entry point
  - `/Users/victormanuel/discord-rpc/sync_bundle.py` — Application bundle synchronizer
- Testing Suite:
  - `/Users/victormanuel/discord-rpc/tests/` — E2E and module test cases
  - `/Users/victormanuel/discord-rpc/tests/run_tests.py` — Master test runner
- macOS Application Bundle:
  - `/Applications/League of Legends RPC.app`
