# Dispatch Assignment — worker_m3_1

## Objective
Implement Milestone 3: Champion Resolver (`lol_champions.py`), Rank Assets & Division Formatter (`lol_ranks.py`), and Thread-Safe Concurrency RPC Actor (`discord_rpc_manager.py`).

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Master Plan: `/Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md`
- Explorer Report: `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/handoff.md`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1`
- Project Root: `/Users/victormanuel/discord-rpc`
- Virtual Environment: `/Users/victormanuel/discord-rpc/venv`

## File Ownership
You exclusively own:
- `/Users/victormanuel/discord-rpc/lol_champions.py`
- `/Users/victormanuel/discord-rpc/lol_ranks.py`
- `/Users/victormanuel/discord-rpc/discord_rpc_manager.py`

## Technical Requirements
1. `lol_champions.py`:
   - `ChampionResolver` class:
     - Handles all 173 champions in Data Dragon `16.19.1`.
     - Normalizes all 9 internal ID discrepancies (`Wukong` -> `MonkeyKing`, `Nunu & Willump` -> `Nunu`, `Renata Glasc` -> `Renata`, `Cho'Gath` -> `Chogath`, `Kai'Sa` -> `Kaisa`, `Vel'Koz` -> `Velkoz`, `Kha'Zix` -> `Khazix`, `Bel'Veth` -> `Belveth`, `LeBlanc` -> `Leblanc`).
     - Normalizes Spanish champion variants (`Bardo` -> `Bard`, `Maestro Yi` -> `MasterYi`).
     - Normalizes abbreviations (`j4` -> `JarvanIV`, `asol` -> `AurelionSol`, `mf` -> `MissFortune`, etc.).
     - Generates valid DDragon square icon URLs: `https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{id}.png`.
2. `lol_ranks.py`:
   - Maps tiers (Iron to Challenger + Unranked) to CommunityDragon rank crest URLs.
   - `format_rank_display(tier: str, division: str = "II")`:
     - Standard tiers: `"{tier} {division}"` (e.g. `Oro II`, `Diamante IV`).
     - Apex tiers (`Master`/`Maestro`, `Grandmaster`/`Gran Maestro`, `Challenger`, `Unranked`): suppresses division numbers (e.g. returns strictly `Challenger`, NEVER `Challenger II`).
3. `discord_rpc_manager.py`:
   - `DiscordRPCManager` class implementing the Actor/Worker queue pattern:
     - Single background worker thread owning `pypresence.Presence` and its `asyncio` event loop.
     - Non-blocking methods (`set_active`, `update_presence_config`, `restart_match`, `shutdown`) push to `queue.Queue`.
     - Callbacks `on_state_change` and `on_match_reset` dispatched to Cocoa main thread via `PyObjCTools.AppHelper.callAfter`.
     - Auto-reconnection loop on Discord start/restart (catches `DiscordNotFound`, `BrokenPipeError`, `InvalidPipe`).
     - Auto-restart match timer (resets elapsed time every 20-30 min).
4. Verify your implementation by running unit tests in `./venv/bin/python`.
5. Report results in `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1/handoff.md`.

## 2026-09-27T10:00:15Z
You are worker_m3_1 (Milestone 3 Worker: Concurrency Manager & LoL Engine) for the Discord RPC redesign project.
Your assigned working directory is:
/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1

MANDATORY INPUTS:
- Original Request: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md
- Master Plan: /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md
- Dispatch Instructions: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1/DISPATCH.md
- Explorer Handoff: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/handoff.md
- Project Root: /Users/victormanuel/discord-rpc

File Ownership:
You exclusively own:
- /Users/victormanuel/discord-rpc/lol_champions.py
- /Users/victormanuel/discord-rpc/lol_ranks.py
- /Users/victormanuel/discord-rpc/discord_rpc_manager.py

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Task:
Implement lol_champions.py (ChampionResolver handling all 173 champions, the 9 internal ID discrepancies, Spanish variants, and DDragon patch versioning), lol_ranks.py (rank crests and Apex tier division suppression), and discord_rpc_manager.py (thread-safe actor queue model, pypresence lifecycle, auto-reconnect, AppKit main thread dispatch).
Run unit verification using ./venv/bin/python.
Document your results in /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1/handoff.md and notify the orchestrator via send_message when complete.
