# Progress — Milestone M7

Last visited: 2026-09-29T23:30:15Z
Status: Complete

## Completed
1. Menubar Controls & Native Cocoa Context Menu:
   - Configured `NSStatusBarButton` with `sendActionOn_(NSEventMaskLeftMouseUp | NSEventMaskRightMouseUp)`.
   - Handled right-click and Ctrl-click in `statusItemButtonClicked:`.
   - Added native `NSMenu` via `popUpStatusItemMenu_` containing "Abrir Popover", "Pausar Presencia" / "Reanudar Presencia", "Configuración ⚙️", and "Salir de Discord RPC" (Cmd+Q).
2. In-App Quit Controls:
   - Added visible subtle quit control in `#view-main` below action button.
   - Added danger-styled quit control in `#view-config` below save button.
   - Wired WebBridge action `quit_app` -> `LoLPopoverController.quit_application()` -> `LoLAppController.quit()`.
3. Single-Instance Lock:
   - Implemented `SingleInstanceController` using Unix domain socket at `~/.config/lol_discord_rpc/app.sock` and `fcntl.flock` on `app.lock`.
   - Secondary instances connect, send `b"FOCUS\n"`, and exit 0.
   - Primary instance listens on daemon thread, activates application, and brings popover to front.
   - Tested abnormal crash recovery with stale socket unlinking.
4. Hardened Auto-Start & Launch Notification:
   - Updated LaunchAgent plist to execute `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC` with `--silent` directly.
   - Configured absolute log paths in `~/Library/Logs/lol_discord_rpc.log` and `~/Library/Logs/lol_discord_rpc_error.log`.
   - Added system notification upon launch confirming active menubar presence for both interactive and silent starts.
   - Updated test assertions in `tests/test_audit_fixes.py` and `tests/test_challenger_audit_2.py`.
5. System Event Listeners & Error Resilience:
   - Registered `NSWorkspaceDidLaunchApplicationNotification` and `NSWorkspaceDidWakeNotification`.
   - Implemented `rpc_manager.reconnect()` to interrupt backoff sleep and reconnect immediately when Discord launches or Mac wakes.
   - Added in-app error boundary toast in `liquid_html.py` with `window.showToast` and `popover.show_toast`.
   - Forwarded RPC and socket errors to toast notification.
6. Verification & Bundle Sync:
   - Added `tests/test_milestone7_lifecycle.py` with 13 comprehensive unit tests.
   - Synchronized changes to `/Applications/League of Legends RPC.app` via `sync_bundle.py`.
   - Ran `venv/bin/python tests/run_tests.py`: 149/149 tests passed (100%).
   - Ran `venv/bin/python -m unittest discover`: 254/254 tests passed (100%).
