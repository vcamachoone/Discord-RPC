# Dispatch Assignment — worker_m4_1

## Objective
Implement Milestone 4: Application Integration (`app_gui.py`) & Bundle Synchronization (`sync_bundle.py`).

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Master Plan: `/Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m4_1`
- Project Root: `/Users/victormanuel/discord-rpc`
- Target App Bundle: `/Applications/League of Legends RPC.app`
- Virtual Environment: `/Users/victormanuel/discord-rpc/venv`

## File Ownership
You exclusively own:
- `/Users/victormanuel/discord-rpc/app_gui.py`
- `/Users/victormanuel/discord-rpc/sync_bundle.py`

## Technical Requirements
1. `app_gui.py`:
   - Replace legacy `rumps` implementation with native PyObjC `NSApplication`.
   - Instantiate `LoLStatusItemController` (Milestone 1).
   - Instantiate `DiscordRPCManager` (Milestone 3).
   - Instantiate `LoLPopoverController` (Milestone 2) anchored to the status item button.
   - Configure seamless bidirectional communication:
     - Popover toggled on status item button click.
     - Mode / champion / rank / switch changes in popover update `DiscordRPCManager`.
     - Callbacks from `DiscordRPCManager` (`on_state_change`, `on_match_reset`) update status item icon state (`normal`, `active`, `paused`) and popover UI elements on the main thread.
   - Configure `NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)`.
   - Provide clean quit handling and signal handling (`SIGINT`, `SIGTERM`).
2. `sync_bundle.py`:
   - Synchronize all runtime source modules and generated icons into `/Applications/League of Legends RPC.app/Contents/Resources/`:
     - `app_gui.py`, `assets_gen.py`, `status_item.py`, `popover_ui.py`, `discord_rpc_manager.py`, `lol_champions.py`, `lol_ranks.py`, and `assets/`.
   - Ensure launcher script `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC` has executable permissions (`0o755`).
   - Validate `Contents/Info.plist` XML integrity and `LSUIElement` setting.
   - Expose verification functions `verify_bundle_integrity()` and `sync_to_applications()`.
3. Verification:
   - Run `./venv/bin/python tests/run_tests.py` and verify that ALL 139 tests across Tiers 1-4 pass cleanly with 0 skipped and 0 failures!
   - Execute `sync_bundle.py` to synchronize `/Applications/League of Legends RPC.app`.
40: 4. Report results in `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m4_1/handoff.md`.
41: 
## 2026-09-27T10:26:37Z
You are worker_m4_1 (Milestone 4 Worker: Application Integration & Bundle Sync) for the Discord RPC redesign project.
Your assigned working directory is:
/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m4_1

MANDATORY INPUTS:
- Original Request: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md
- Master Plan: /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md
- Dispatch Instructions: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m4_1/DISPATCH.md
- Project Root: /Users/victormanuel/discord-rpc
- Application Bundle: /Applications/League of Legends RPC.app

File Ownership:
You exclusively own:
- /Users/victormanuel/discord-rpc/app_gui.py
- /Users/victormanuel/discord-rpc/sync_bundle.py

Task:
Read ORIGINAL_REQUEST.md and DISPATCH.md.
1. Implement app_gui.py:
   - Full native AppKit application integrating LoLStatusItemController, LoLPopoverController, and DiscordRPCManager.
   - NSApplicationActivationPolicyAccessory (no dock icon, menu bar agent).
   - Dynamic icon updates on presence status changes.
   - Clean shutdown and signal handling.
2. Implement sync_bundle.py:
   - Synchronizes app_gui.py, assets_gen.py, status_item.py, popover_ui.py, discord_rpc_manager.py, lol_champions.py, lol_ranks.py, and assets into /Applications/League of Legends RPC.app/Contents/Resources/.
   - Verifies bundle permissions (chmod +x launcher), Info.plist XML integrity, and LSUIElement.
   - Run sync_bundle.py to update the application bundle.
3. Verification:
   - Run ./venv/bin/python tests/run_tests.py and verify that all 139 tests across Tiers 1-4 pass (0 failures, 0 errors, 0 skipped).
Write your handoff report to /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m4_1/handoff.md and notify the orchestrator via send_message when complete.
