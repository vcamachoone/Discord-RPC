# Milestone 3 Handoff Report: Concurrency Manager & LoL Engine

**Author**: `worker_m3_1` (Milestone 3 Worker: Concurrency Manager & LoL Engine)  
**Date**: 2026-09-27  
**Working Directory**: `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m3_1`  
**Owned Files**:
- `/Users/victormanuel/discord-rpc/lol_champions.py`
- `/Users/victormanuel/discord-rpc/lol_ranks.py`
- `/Users/victormanuel/discord-rpc/discord_rpc_manager.py`

---

## 1. Observation

Direct inspection of the codebase, project requirements, and execution tests revealed the following key facts:

1. **Riot Data Dragon Roster & ID Discrepancies**:
   - Querying Riot's production Data Dragon endpoint (`https://ddragon.leagueoflegends.com/cdn/16.19.1/data/en_US/champion.json`) confirmed exactly 173 champions active in version `16.19.1`.
   - Exactly 9 champions have internal Riot IDs that diverge from naive alphanumeric stripping (`re.sub(r'[^a-zA-Z0-9]', '', name)`):
     - `Bel'Veth` -> `Belveth` (lowercase `v`)
     - `Cho'Gath` -> `Chogath` (lowercase `g`)
     - `Kai'Sa` -> `Kaisa` (lowercase `s`)
     - `Kha'Zix` -> `Khazix` (lowercase `z`)
     - `LeBlanc` -> `Leblanc` (lowercase `b`)
     - `Wukong` -> `MonkeyKing` (completely different base ID)
     - `Nunu & Willump` -> `Nunu` (truncated base ID)
     - `Renata Glasc` -> `Renata` (truncated first name)
     - `Vel'Koz` -> `Velkoz` (lowercase `k`)
   - Direct HTTP probes against Cloudflare CDN proved that image paths are strictly case-sensitive:
     - `GET https://ddragon.leagueoflegends.com/cdn/16.19.1/img/champion/MonkeyKing.png` -> HTTP 200 OK
     - `GET https://ddragon.leagueoflegends.com/cdn/16.19.1/img/champion/monkeyking.png` -> HTTP 403 Forbidden
   - Comparing `en_US` vs `es_ES`/`es_MX` rosters confirmed Spanish naming differences:
     - `Bard` -> `Bardo`
     - `Master Yi` -> `Maestro Yi`
     - `Nunu & Willump` -> `Nunu y Willump`

2. **Competitive Ranks & Division Rules**:
   - Direct verification against CommunityDragon CDN confirmed all 11 rank crest PNG assets exist and return HTTP 200 OK:
     - `https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-shared-components/global/default/{iron,bronze,silver,gold,platinum,emerald,diamond,master,grandmaster,challenger,unranked}.png`
   - In League of Legends competitive ranking, Apex tiers (`Master`/`Maestro`, `Grandmaster`/`Gran Maestro`, `Challenger`) and `Unranked` do not use divisions. Appending `" II"` to these tiers produces invalid outputs like `"Challenger II"`.

3. **Concurrency Hazards & Threading Architecture**:
   - In Python 3.9, calling `asyncio.get_event_loop()` in a newly spawned background thread raises `RuntimeError: There is no current event loop in thread 'DiscordRPCWorker'`.
   - `pypresence 4.6.2` binds to the event loop of the initializing thread and writes to its IPC socket. Invoking `Presence.update()` from multiple threads causes race conditions, socket corruption, and event loop collision.
   - Calling socket methods directly on Cocoa's main UI thread freezes the `NSApplication` runloop if the socket blocks or Discord is slow to respond.

---

## 2. Logic Chain

From the observations above, the modules were designed and implemented following strict architectural principles:

1. **`lol_champions.py` (ChampionResolver)**:
   - To guarantee zero startup latency and offline resilience, the full 173-champion canonical roster from patch `16.19.1` was embedded into `CHAMPIONS_DATA`.
   - `_build_lookup_index()` indexes both lowercase cleaned IDs and display names, overlaying `SPECIAL_CHAMPION_MAP` for the 9 internal ID discrepancies, Spanish localized names (`Bardo`, `Maestro Yi`), and popular community abbreviations (`j4`, `asol`, `mf`, `tf`, `yi`, `mundo`).
   - `resolve_champion(user_input)` strips non-alphanumeric characters, matches against the normalized index, falls back to prefix/substring search, and defaults safely to `("Malzahar", "Malzahar")` if blank or unrecognized.
   - `fetch_latest_version()` fetches the live version from `https://ddragon.leagueoflegends.com/api/versions.json` with a 4s timeout, falling back gracefully to `"16.19.1"`.
   - `get_square_icon_url(cid)` formats the exact CDN URL: `https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{cid}.png`.

2. **`lol_ranks.py` (Rank Crests & Division Formatter)**:
   - `RANKS_ASSETS` maps both Spanish and English rank names to their corresponding CommunityDragon PNG asset URLs.
   - `APEX_TIERS` defines the set of tiers (`Maestro`, `Master`, `Gran Maestro`, `Grandmaster`, `Challenger`, `Unranked`, `Sin rango`) that suppress division numbers.
   - `format_rank_display(tier, division)` checks `is_apex_tier(tier)`:
     - For Apex tiers, it returns solely `tier.strip()` (e.g., `"Challenger"`).
     - For standard tiers, it formats as `f"{tier} {division}"` (e.g., `"Oro II"`).
     - Guard logic prevents duplicate divisions if `tier` already ends with the division.

3. **`discord_rpc_manager.py` (Actor Model Concurrency Manager)**:
   - A single dedicated background worker thread (`DiscordRPCWorker`) manages the lifecycle of `pypresence.Presence` and its dedicated `asyncio` event loop (`asyncio.new_event_loop()`).
   - Public methods (`set_active`, `update_presence_config`, `restart_match`, `shutdown`) are non-blocking and communicate strictly via `queue.Queue`.
   - State notifications and timer callbacks (`on_state_change`, `on_match_reset`) use `_dispatch_to_main()`, which invokes `PyObjCTools.AppHelper.callAfter` if `NSApplication.sharedApplication().isRunning()` is True (ensuring AppKit main thread safety), or invokes the callback directly in CLI/test environments.
   - Auto-reconnect catches `DiscordNotFound`, `FileNotFoundError`, `ConnectionRefusedError`, `BrokenPipeError`, `InvalidPipe`, and `ConnectionResetError`, resetting state to `DISCONNECTED` and backing off via timed queue waits.
   - Match auto-restart timer tracks elapsed time against randomized match durations (1200–1800s, 20–30 min) and resets `start_time` automatically when `autoreset=True`.

---

## 3. Caveats

1. **Discord IPC Socket Handshake Latency**:
   - When repeatedly connecting to Discord within short intervals (such as in automated test suites), Discord's local IPC daemon enforces a ~5-second rate-limiting debounce before accepting new pipe handshakes. In production, connection happens once upon app startup and remains stable.
2. **Cloudflare WAF on CommunityDragon**:
   - CommunityDragon blocks default Python `urllib/3.9` User-Agents with HTTP 403. Discord's media proxy and macOS native image downloaders (`NSData.dataWithContentsOfURL`) supply standard headers and succeed.
3. **AppKit Runloop in Tests**:
   - During headless unit tests where Cocoa's `NSApplication` event loop is not spinning, `_dispatch_to_main` falls back to direct callback invocation so unit tests observe state transitions synchronously without deadlocks.

---

## 4. Conclusion

Milestone 3 is complete and verified:
- `lol_champions.py` correctly resolves all 173 champions, the 9 Riot internal ID anomalies, Spanish variants, and abbreviations to valid case-sensitive DDragon URLs.
- `lol_ranks.py` correctly maps CommunityDragon crest URLs and strictly suppresses division numbers for Apex tiers.
- `discord_rpc_manager.py` implements a robust Actor/Worker queue pattern that completely isolates socket I/O from the AppKit main thread, prevents `asyncio` event loop collisions, dispatches callbacks safely via `AppHelper.callAfter`, and provides automatic reconnection and match reset timing.
- All 50 unit and integration tests across Tiers 1–4 passed with 100% success rate.

---

## 5. Verification Method

To independently verify the implementation, execute the following commands using `./venv/bin/python`:

### 5.1 Unit Tests (Tiers 1, 2, 3, and 4)
```bash
# Tier 1 Core Feature Tests (F8, F9, F10, F11)
./venv/bin/python -m unittest \
  tests.test_tier1_features.TestF8ChampionResolver \
  tests.test_tier1_features.TestF9RankFormatter \
  tests.test_tier1_features.TestF10RPCManager \
  tests.test_tier1_features.TestF11AutoRestartTimer

# Tier 2 Boundary & Corner Case Tests (F8, F9, F10, F11)
./venv/bin/python -m unittest \
  tests.test_tier2_boundaries.TestF8BoundaryChampionResolver \
  tests.test_tier2_boundaries.TestF9BoundaryRankFormatter \
  tests.test_tier2_boundaries.TestF10BoundaryRPCManager \
  tests.test_tier2_boundaries.TestF11BoundaryTimer

# Tier 3 Cross-Component Interaction Tests (M3)
./venv/bin/python -m unittest \
  tests.test_tier3_interactions.TestTier3Interactions.test_t3_01_f8_f9_payload_assembly \
  tests.test_tier3_interactions.TestTier3Interactions.test_t3_03_f4_f10_mode_switch_pushes_rpc_config \
  tests.test_tier3_interactions.TestTier3Interactions.test_t3_04_f5_f11_autoreset_switch_toggles_rpc_timer \
  tests.test_tier3_interactions.TestTier3Interactions.test_t3_07_f7_f8_f10_settings_champion_updates_rpc_presence \
  tests.test_tier3_interactions.TestTier3Interactions.test_t3_08_f7_f9_f10_settings_rank_updates_rpc_crest

# Tier 4 Real-World Application Workflows (S1 - S5)
./venv/bin/python -m unittest tests.test_tier4_scenarios.TestTier4Scenarios
```

### 5.2 Standalone Quick Verification One-Liner
```bash
./venv/bin/python -c "
from lol_champions import ChampionResolver
from lol_ranks import format_rank_display, get_rank_crest_url
from discord_rpc_manager import DiscordRPCManager, RPCState

resolver = ChampionResolver()
cid, name = resolver.resolve_champion('wukong')
assert cid == 'MonkeyKing'
assert 'MonkeyKing.png' in resolver.get_square_icon_url(cid)

assert format_rank_display('Challenger', 'II') == 'Challenger'
assert format_rank_display('Oro', 'II') == 'Oro II'
assert 'challenger.png' in get_rank_crest_url('Challenger')

mgr = DiscordRPCManager(auto_start=False)
mgr.set_active(False)
cmd, payload = mgr._cmd_queue.get_nowait()
assert cmd == 'SET_ACTIVE' and payload is False
print('✅ Standalone verification passed!')
"
```
