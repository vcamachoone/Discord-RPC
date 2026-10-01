# BRIEFING — 2026-09-29T23:30:00Z

## Mission
Implement Milestone M7: Menubar native context menu, in-app quit controls, single-instance socket lock with focus signal, hardened LaunchAgent plist with logging & launch notification, workspace wake/launch notification listeners, and error toasts.

## 🔒 My Identity
- Archetype: worker
- Roles: implementer, qa, specialist
- Working directory: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m7_1
- Original parent: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Milestone: M7

## 🔒 Key Constraints
- Genuine implementation — no facade, no hardcoded test shortcuts.
- Minimal change principle.
- All tests must pass (100%).
- Keep .agents/teamwork/ metadata-only.
- Sync bundle to /Applications/League of Legends RPC.app.

## Current Parent
- Conversation ID: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Updated: 2026-09-29T23:30:00Z

## Task Summary
- **What to build**:
  1. Menubar Controls & Native Cocoa Context Menu (status_item.py, app_gui.py).
  2. In-App Quit Controls (liquid_html.py, popover_ui.py, app_gui.py).
  3. Single-Instance Lock via Unix domain socket & flock (app_gui.py).
  4. Hardened Auto-Start plist (direct executable + logs) & launch notification (popover_ui.py, app_gui.py).
  5. System event listeners (sleep/wake, Discord app launch) & error toast notification system (app_gui.py, discord_rpc_manager.py, liquid_html.py, popover_ui.py).
  6. Bundle sync & full test suite validation.
- **Success criteria**: All 6 areas implemented genuinely, tests updated/created, tests pass 100% (254/254 unittests, 149/149 runner), bundle synchronized.
- **Interface contracts**: ORIGINAL_REQUEST.md (§ Follow-up — 2026-09-29T23:10:58Z), PROJECT.md.
- **Code layout**: src in project root, tests in tests/.

## Change Tracker
- **Files modified**:
  * `status_item.py`: Added `sendActionOn_` for right-clicks, native Cocoa context menu `build_context_menu()` with Open, Pause/Resume, Settings, Quit (Cmd+Q), and right-click event filtering.
  * `liquid_html.py`: Added quit buttons in `#view-main` and `#view-config`, toast container, CSS styles, `window.showToast`, and window error listeners.
  * `popover_ui.py`: Added WebBridge `quit_app` action handler, `quit_application()`, `show_toast()`, `open_settings_panel()`, native fallback quit button, updated layout sizes, and hardened LaunchAgent plist with direct binary execution and logging.
  * `discord_rpc_manager.py`: Added `reconnect()` method and `RECONNECT` command handling to unblock sleep and safely reconnect.
  * `app_gui.py`: Added `SingleInstanceController` with Unix domain socket and flock, context menu wiring, NSWorkspace notification observers (Discord launch and system wake), toast error routing, and launch notification for silent boot.
  * `tests/test_audit_fixes.py`: Updated LaunchAgent plist inspection assertion.
  * `tests/test_challenger_audit_2.py`: Updated LaunchAgent plist schema and logging assertions.
  * `tests/test_milestone7_lifecycle.py`: New unit and integration test suite covering all M7 features.
- **Build status**: PASS (254/254 unittests, 149/149 runner tests pass).
- **Pending issues**: None.

## Quality Status
- **Build/test result**: 100% pass across all tiers and test suites.
- **Lint status**: Clean, no regressions.
- **Tests added/modified**: Added `tests/test_milestone7_lifecycle.py` (13 test cases); updated `test_audit_fixes.py` and `test_challenger_audit_2.py`.

## Loaded Skills
- None

## Key Decisions Made
- `SingleInstanceController` checks if `AppKit.NSApplication.sharedApplication().isRunning()` before deciding between `AppHelper.callAfter` and direct synchronous dispatch, ensuring tests can execute IPC tests outside an active Cocoa run loop without hang.
- Launch notification banner is displayed on all boots (including `--silent` via LaunchAgent), confirming active menubar presence while suppressing automatic popover window pop-up on silent mode.
- Context menu dynamic toggle item reflects active connection state ("Pausar Presencia" when active, "Reanudar Presencia" when paused/normal).

## Artifact Index
- DISPATCH.md — Assignment instructions
- BRIEFING.md — Persistent context
- progress.md — Heartbeat and status
- handoff.md — Final handoff report
