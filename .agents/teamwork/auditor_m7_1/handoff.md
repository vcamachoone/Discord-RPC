# Forensic Audit Report — Milestone M7

**Work Product**: Milestone M7: App Lifecycle, Menubar & System Events (`app_gui.py`, `status_item.py`, `popover_ui.py`, `discord_rpc_manager.py`, `liquid_html.py`, `tests/test_milestone7_lifecycle.py`)  
**Profile**: General Project (Development Mode)  
**Verdict**: **CLEAN**

---

## 1. Observation

### 1.1 Integrity Checks (Prohibited Patterns)
1. **Hardcoded Test Results**:
   - Grep searches for hardcoded status strings or dummy returns across modified files returned zero facade patterns.
   - Command: `grep -rn "return True" app_gui.py status_item.py popover_ui.py`
   - Results: Found only legitimate boolean return in `SingleInstanceController.check_and_acquire` (line 145) and Cocoa delegate `applicationShouldTerminate_` (line 537).
2. **Facade Implementations**:
   - Zero stubbed methods, placeholder classes, or `NotImplementedError` occurrences found across the codebase.
3. **Fabricated Verification Outputs**:
   - Command: `find . -name '*.log' -o -name '*result*' -o -name '*output*'`
   - Result: 0 pre-populated or lingering artifacts.

### 1.2 Verification of Specific M7 Deliverables

1. **SingleInstanceController Implementation**:
   - File: `app_gui.py` (lines 59–234).
   - Uses real `fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)` on `~/.config/lol_discord_rpc/app.lock`.
   - Uses real Unix domain socket `socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)` at `~/.config/lol_discord_rpc/app.sock`.
   - When secondary instance launches: connects to primary socket, sends `b"FOCUS\n"`, calls `NSRunningApplication` activation, and terminates cleanly with exit code 0 (`app_gui.py` lines 597–600).
   - When primary instance receives `b"FOCUS"`: triggers focus callback on main thread via `AppHelper.callAfter(focus_popover)` (`app_gui.py` line 201).
   - Cleans up stale sockets, unlinks socket on exit, and releases flock (`app_gui.py` lines 210–233).
   - Empirical test: Multi-instance acquisition test passed cleanly.

2. **Cocoa NSMenu & Selectors on Status Item**:
   - File: `status_item.py` (lines 94–96, 139–256).
   - Real `self._button.sendActionOn_(AppKit.NSEventMaskLeftMouseUp | AppKit.NSEventMaskRightMouseUp)`.
   - Native `AppKit.NSMenu` constructed with 4 functional items and 1 separator:
     * `"Abrir Popover"` (`b"menuOpenPopover:"`)
     * `"Pausar Presencia"` / `"Reanudar Presencia"` (`b"menuTogglePresence:"`)
     * `"Configuración ⚙️"` (`b"menuOpenSettings:"`, keyEquivalent `","`)
     * Separator (`AppKit.NSMenuItem.separatorItem()`)
     * `"Salir de Discord RPC"` (`b"menuQuit:"`, keyEquivalent `"q"`)
   - `statusItemButtonClicked_` checks `AppKit.NSApp.currentEvent()` for `RightMouseUp`, `RightMouseDown`, and Control-click, invoking `popUpStatusItemMenu_` while preserving left-click popover toggle.
   - Empirical test: Confirmed NSMenu class, menu item titles, selectors, and Cmd+Q shortcut.

3. **Hardened LaunchAgent Plist**:
   - File: `popover_ui.py` (lines 1280–1326).
   - `_sync_login_item(True)` generates plist containing:
     * Label: `com.victormanuel.lolrpc`
     * ProgramArguments: Direct path `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC` with `--silent` (completely omits `/usr/bin/open`).
     * `StandardOutPath`: `/Users/victormanuel/Library/Logs/lol_discord_rpc.log`
     * `StandardErrorPath`: `/Users/victormanuel/Library/Logs/lol_discord_rpc_error.log`
   - Empirical test: Generated plist verified via `plistlib.load`.

4. **System Event Listeners & RPC Reconnection**:
   - File: `app_gui.py` (lines 280–332) & `discord_rpc_manager.py` (lines 316–320, 426–430, 586–594).
   - Cocoa observers registered on `NSWorkspace.sharedWorkspace().notificationCenter()` for:
     * `NSWorkspaceDidLaunchApplicationNotification` (`onAppLaunched_`): checks `userInfo["NSWorkspaceApplicationKey"]`, filters for `"discord"` in bundle ID or localized name, and triggers `rpc_manager.reconnect()`.
     * `NSWorkspaceDidWakeNotification` (`onSystemWake_`): triggers `rpc_manager.reconnect()`.
   - `discord_rpc_manager.reconnect()` enqueues `("RECONNECT", None)`. The worker thread's queue wait `self._cmd_queue.get(timeout=3.5)` unblocks immediately, closes the previous socket, and re-executes `connect()`.
   - Empirical test: Verified notification handlers and queue unblocking.

5. **WebKit Bridge Routing & In-App Quit Controls**:
   - File: `liquid_html.py` (lines 720–775, 989–1000, 1070–1081) & `popover_ui.py` (lines 169–172, 694–703, 1587–1598).
   - Added `.quit-btn` in `#view-main` and `.quit-app-btn` in `#view-config` with `onclick="sendAction('quit_app')"`.
   - Also added native fallback quit button in `_build_action_button`.
   - `LoLWebBridge.userContentController_didReceiveScriptMessage_` receives action `"quit_app"` and invokes `LoLPopoverController.quit_application()`, which closes the popover and executes `LoLAppController.quit()`.
   - Empirical test: Verified HTML markup and WebKit script message dispatch to `quit_application`.

### 1.3 Test Suite Execution Results
- **Master Test Runner**:
  - Command: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
  - Output: 149/149 passed cleanly (100% across Tiers 1 to 5) in 21.293s.
- **Dedicated Milestone M7 Lifecycle Suite**:
  - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone7_lifecycle.py`
  - Output: 13/13 passed in 0.735s.
- **Existing Audit Test Suites**:
  - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_audit_fixes.py tests/test_challenger_audit_2.py`
  - Output: 30/30 passed in 3.958s.
- **Application Bundle Integrity**:
  - Command: `/Users/victormanuel/discord-rpc/venv/bin/python -c "import sync_bundle; print(sync_bundle.verify_bundle_integrity(detailed=True))"`
  - Output: `{'valid': True, 'bundle_path': '/Applications/League of Legends RPC.app', 'checks': {...}, 'errors': []}`.

---

## 2. Logic Chain

```
Observation 1.1: Code contains zero hardcoded test outputs, zero facade/dummy methods, and zero pre-populated verification logs.
       │
       ▼
Logic Step 1: Baseline integrity requirements are fully satisfied under General Project profile in Development Mode.
       │
Observation 1.2: SingleInstanceController enforces mutual exclusion using real fcntl.flock on app.lock and real Unix domain socket app.sock, notifying primary via b"FOCUS" and exiting code 0.
       │
       ▼
Logic Step 2: Single-instance locking and cross-instance activation logic is genuine, non-trivial, and functionally verified.
       │
Observation 1.3: status_item.py builds real NSMenu with 4 selectors and keyEquivalent 'q'; handles secondary right-click and Control-click via popUpStatusItemMenu_.
       │
       ▼
Logic Step 3: Cocoa menubar context menu implementation is authentic and follows native macOS AppKit patterns.
       │
Observation 1.4: popover_ui.py generates LaunchAgent plist executing the bundle executable directly with --silent and log redirection to ~/Library/Logs/.
       │
       ▼
Logic Step 4: Auto-start requirements are genuinely fulfilled without reliance on /usr/bin/open.
       │
Observation 1.5: NSWorkspace notification listeners detect Discord launch and system wake; discord_rpc_manager.reconnect() enqueues RECONNECT which immediately unblocks backoff sleep.
       │
       ▼
Logic Step 5: System event resilience operates via genuine OS-level notifications and thread-safe queue unblocking.
       │
Observation 1.6: liquid_html.py, LoLWebBridge, and LoLPopoverController provide visible quit buttons in both views and route 'quit_app' to app termination.
       │
       ▼
Logic Step 6: Application lifecycle termination is genuinely accessible from both the UI and menubar.
       │
Observation 1.3: All test suites (149/149 master, 13/13 M7 lifecycle, 30/30 audit fixes) pass cleanly with zero regressions.
       │
       ▼
Conclusion: Milestone M7 is authentic, genuine, and free of integrity violations. Verdict is CLEAN.
```

---

## 3. Caveats & Non-Blocking Findings

1. **Defect in Exception Logging (`popover_ui.py`)**:
   - In `popover_ui.py`, lines 1592 (`logger.warning(...)`) and 1607 (`logger.debug(...)`) reference `logger`, but neither `import logging` nor `logger = logging.getLogger(__name__)` is defined in `popover_ui.py`.
   - Under normal execution this does not trigger, but if `evaluateJavaScript` or `on_quit` throws an exception, the handler raises `NameError: name 'logger' is not defined`.
   - *Recommendation*: While this is a code defect rather than an integrity violation (cheating/facade), it should be addressed in subsequent polishing by adding `import logging; logger = logging.getLogger(__name__)` at module top in `popover_ui.py`.
2. **PyObjC Monkeypatching in Adversarial Tests**:
   - In adversarial tests created by challengers (`test_challenger_m7_stress.py`), patching `AppKit.NSWorkspace.sharedWorkspace` or `AppKit.NSApp.currentEvent` mutates PyObjC C-method descriptors across the entire Python process. Tests running Cocoa integrations in the same process should avoid modifying immutable AppKit class methods.

---

## 4. Conclusion

**Verdict: CLEAN**

Milestone M7 satisfies all requirements laid out in `ORIGINAL_REQUEST.md` (§ Follow-up 2026-09-29T23:10:58Z):
- Authentic single-instance protection with real `fcntl.flock` and Unix domain socket IPC.
- Native Cocoa `NSMenu` on secondary right-click with selectors, dynamic titles, and Cmd+Q shortcut.
- Direct binary path and absolute `~/Library/Logs/` in LaunchAgent plist.
- Genuine `NSWorkspace` notifications for Discord launch and system wake, with non-blocking queue reconnection.
- Complete UI quit controls in WebKit HUD and Cocoa popover controller.
- 100% test pass rate across master suite (149/149) and dedicated lifecycle suite (13/13).

---

## 5. Verification Method

To independently verify this audit:

1. **Run Master Test Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
2. **Run Dedicated Milestone M7 Lifecycle Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone7_lifecycle.py
   ```
3. **Run Audit Fixes and Regression Suites**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_audit_fixes.py tests/test_challenger_audit_2.py
   ```
4. **Empirical Single-Instance Verification**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "
   import tempfile, app_gui
   tmp = tempfile.mkdtemp()
   c1 = app_gui.SingleInstanceController(config_dir=tmp)
   assert c1.check_and_acquire() == True
   c2 = app_gui.SingleInstanceController(config_dir=tmp)
   assert c2.check_and_acquire() == False
   c1.cleanup()
   "
   ```
5. **Invalidation Conditions**:
   - Any failure in `tests/run_tests.py` or `tests/test_milestone7_lifecycle.py`.
   - Discovery of any hardcoded test results, facade methods, or pre-populated artifacts.
