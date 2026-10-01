## 2026-09-29T23:18:26Z

You are worker_m7_1.
Your working directory is: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m7_1
Project root: /Users/victormanuel/discord-rpc
Authoritative requirements file: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md (specifically read section ## Follow-up — 2026-09-29T23:10:58Z).
Read the explorer findings at:
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_1/handoff.md
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_2/handoff.md
Also consult /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF MILESTONE M7 (Requirements R1 & R4):
1. Menubar Controls & Native Cocoa Context Menu (status_item.py & app_gui.py):
   - Configure NSStatusBarButton to sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp).
   - In statusItemButtonClicked:, check AppKit.NSApp.currentEvent() for right-click or Control-click.
   - On right-click, present a native Cocoa NSMenu via popUpStatusItemMenu_ with:
     * "Abrir Popover" (Open Popover)
     * "Pausar Presencia" / "Reanudar Presencia" (Toggle Presence)
     * "Configuración ⚙️" (Settings)
     * "Salir de Discord RPC" (Quit, Cmd+Q)
   - Left-click preserves existing popover toggle.
2. In-App Quit Controls (liquid_html.py, popover_ui.py, app_gui.py):
   - In #view-main, add visible "Salir de la aplicación" control below the main action button.
   - In #view-config, add danger-styled "Salir de la aplicación" button below the Save button.
   - Handle action 'quit_app' in LoLWebBridge and LoLPopoverController.quit_application(), delegating to LoLAppController.quit().
3. Single-Instance Lock (app_gui.py):
   - Implement SingleInstanceController using a Unix domain socket at ~/.config/lol_discord_rpc/app.sock and fcntl.flock on app.lock.
   - If already running, connect, send b"FOCUS\n", and exit 0.
   - Primary instance listens on socket; on "FOCUS", invokes activateIgnoringOtherApps_(True) and opens/focuses popover.
   - Clean up socket on exit. Safely handle stale sockets or abnormal terminations.
4. Hardened Auto-Start & Launch Notification (popover_ui.py, app_gui.py):
   - Update LaunchAgent plist to execute /Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC with --silent directly (not /usr/bin/open).
   - Configure StandardOutPath and StandardErrorPath pointing to absolute paths in ~/Library/Logs/lol_discord_rpc.log and ~/Library/Logs/lol_discord_rpc_error.log.
   - Display a brief system notification upon launch confirming active menubar presence even when launched with --silent.
   - Update any legacy test assertions in tests/test_audit_fixes.py or tests/test_challenger_audit_2.py if they expected /usr/bin/open.
5. System Event Listeners & Error Resilience (app_gui.py, discord_rpc_manager.py):
   - Register NSWorkspaceDidLaunchApplicationNotification and NSWorkspaceDidWakeNotification on NSWorkspace.sharedWorkspace().notificationCenter().
   - When Discord launches or Mac wakes from sleep, invoke rpc_manager.reconnect() immediately to reconnect IPC socket.
   - Add in-app error boundary toast in liquid_html.py with window.showToast(message, type) and popover.show_toast(message, type).
   - Forward socket/RPC errors in app_gui.py:on_rpc_state_change to show a toast when disconnected abnormally.
6. Verification & Bundle Sync:
   - Synchronize changes to /Applications/League of Legends RPC.app using sync_bundle.py.
   - Run tests: /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py.
   - All tests must pass (100%).

Produce a detailed handoff report in your working directory at:
/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m7_1/handoff.md
Include build and test results and layout compliance.
Send a message when done.
