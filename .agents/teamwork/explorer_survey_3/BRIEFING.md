# BRIEFING — 2026-09-27T08:34:02Z

## Mission
Investigate Riot Data Dragon API, Champion normalization, rank asset keys, and pypresence concurrency safety for Discord RPC redesign.

## 🔒 My Identity
- Archetype: explorer
- Roles: LoL Data Dragon & Concurrency Explorer
- Working directory: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3
- Original parent: fbd9aeb5-9cc5-4b16-930b-4d15d7610d01
- Milestone: Survey & Architectural Design

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Scope limited to Data Dragon API, Champion normalization, Rank assets/divisions, and Discord RPC concurrency/thread safety
- Deliverable: handoff.md in working directory
- Communicate with parent orchestrator via send_message

## Current Parent
- Conversation ID: fbd9aeb5-9cc5-4b16-930b-4d15d7610d01
- Updated: not yet

## Investigation State
- **Explored paths**: `/Users/victormanuel/discord-rpc/lol_rpc.py`, `/Users/victormanuel/discord-rpc/app_gui.py`, `pypresence 4.6.2` source (`presence.py`, `baseclient.py`, `utils.py`), Riot Data Dragon API (`versions.json`, `champion.json`), CommunityDragon rank assets.
- **Key findings**:
  - Live Data Dragon patch is `16.19.1` (173 champions). Image URLs are strictly case-sensitive and return 403 on incorrect case.
  - Exactly 9 champions have internal ID/casing anomalies: `Wukong` -> `MonkeyKing`, `Nunu & Willump` -> `Nunu`, `Renata Glasc` -> `Renata`, `Cho'Gath` -> `Chogath`, `Kai'Sa` -> `Kaisa`, `Vel'Koz` -> `Velkoz`, `Kha'Zix` -> `Khazix`, `Bel'Veth` -> `Belveth`, `LeBlanc` -> `Leblanc`. Spanish localized names mapped: `Bardo` -> `Bard`, `Maestro Yi` -> `MasterYi`.
  - Apex tiers (Master, Grandmaster, Challenger, Unranked) must not include division suffixes.
  - `pypresence` binds an `asyncio` event loop to `Presence.connect()`. Ephemeral threads calling `Presence.update()` cause event loop collisions and socket frame corruption.
  - Validated Actor/Queue worker architecture (`DiscordRPCManager`) with single-threaded event loop and `PyObjCTools.AppHelper.callAfter` for Cocoa runloop isolation.
- **Unexplored areas**: None within assigned scope; all objectives resolved.

## Key Decisions Made
- Standardized on Actor/Worker Queue pattern with single background thread for `pypresence`.
- Implemented static fallback version `16.19.1` with asynchronous live version fetching.
- Defined explicit alias dictionary and normalization rules for all 173 champions and Spanish localizations.
- Specified division suppression for Apex tiers and verified all CommunityDragon rank URLs.

## Artifact Index
- `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_3/handoff.md` — Comprehensive technical specification and architectural blueprints.
