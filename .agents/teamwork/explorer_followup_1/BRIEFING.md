# BRIEFING — 2026-09-29T23:18:00Z

## Mission
Architectural survey and deep investigation of requirements R1 & R4 (Native App Lifecycle, Menubar Controls, System Event Listeners, Error Resilience).

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_1
- Original parent: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Milestone: followup_investigation_r1_r4

## 🔒 Key Constraints
- Read-only investigation — do NOT implement changes directly in project code
- Ground all findings with exact line numbers, file paths, and Cocoa APIs
- Follow Handoff Protocol (Observation, Logic Chain, Caveats, Conclusion, Verification Method)

## Current Parent
- Conversation ID: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Updated: 2026-09-29T23:18:00Z

## Investigation State
- **Explored paths**:
  - `status_item.py` lines 91-95, 136-148 (Click interception & Cocoa context menu)
  - `app_gui.py` lines 188-216, 231-264, 317-340 (Lifecycle, launch notification, single-instance, signal handling)
  - `popover_ui.py` lines 138-170, 852-898, 1220-1310 (LoLWebBridge, LaunchAgent plist, evaluateJavaScript)
  - `discord_rpc_manager.py` lines 177-190, 404-436, 486-585 (Worker loop, backoff, reconnect, socket error handling)
  - `liquid_html.py` lines 862-867, 870-942, 949-972 (HTML panels, action button, config save button, WebKit messaging)
  - `sync_bundle.py` & `build_dmg.py` (Runtime module synchronization and DMG packaging)
  - `tests/test_audit_fixes.py` & `tests/test_challenger_audit_2.py` (LaunchAgent test assertions)
- **Key findings**:
  - `NSStatusBarButton` can listen for secondary clicks via `sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)`.
  - Context menu can be shown via `popUpStatusItemMenu_` without permanently hijacking left-click popover toggle.
  - Single-instance lock via Unix domain socket (`app.sock`) + `flock` (`app.lock`) + `NSRunningApplication` allows focusing existing popover on CLI or Finder launch.
  - LaunchAgent hardening requires direct bundle binary execution (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`), absolute log paths in `~/Library/Logs/`, and user notification on launch.
  - `NSWorkspaceDidLaunchApplicationNotification` and `NSWorkspaceDidWakeNotification` allow instant IPC connection on Discord start or sleep wake.
  - In-app error boundary toast can be added in `liquid_html.py` and bridged via `evaluateJavaScript`.
- **Unexplored areas**: None for R1 and R4 scope.

## Key Decisions Made
- Fully documented concrete implementation blueprints, exact line numbers, code snippets, and verification procedures in `handoff.md`.

## Artifact Index
- DISPATCH.md — record of incoming tasks
- BRIEFING.md — persistent state memory
- progress.md — liveness heartbeat
- handoff.md — comprehensive handoff report for orchestrator and implementer
