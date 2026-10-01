# Review & Adversarial Verification Report — Milestone M7

**Reviewer / Critic**: `reviewer_m7_1`  
**Date**: 2026-09-29T23:37:00Z  
**Target Milestone**: M7 (Requirements R1 & R4) — App Lifecycle, Menubar & System Events  
**Target Agent**: `worker_m7_1`  
**Definitive Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### 1.1 Critical Defect: Missing `logger` Identifier in `popover_ui.py`
In `popover_ui.py`, `logger` is referenced in two critical exception handlers introduced in Milestone M7:

- Line 1592 (`quit_application`):
  ```python
  1587:     def quit_application(self) -> None:
  1588:         """Closes the popover and cleanly terminates the macOS application."""
  1589:         self.close()
  1590:         if callable(self._on_quit):
  1591:             try:
  1592:                 self._on_quit()
  1593:                 return
  1594:             except Exception as e:
  1595:                 logger.warning("Error invoking on_quit callback: %s", e)
  1596:         app = AppKit.NSApplication.sharedApplication()
  1597:         if app and app.isRunning():
  1598:             app.terminate_(None)
  ```

- Line 1607 (`show_toast`):
  ```python
  1600:     def show_toast(self, message: str, toast_type: str = "error") -> None:
  1601:         """Displays an animated toast message in the WebKit Liquid Glass UI."""
  1602:         if getattr(self, "_web_view", None):
  1603:             import json
  1604:             escaped_msg = json.dumps(str(message))
  1605:             escaped_type = json.dumps(str(toast_type))
  1606:             js = f"if (window.showToast) {{ window.showToast({escaped_msg}, {escaped_type}); }}"
  1607:             try:
  1608:                 self._web_view.evaluateJavaScript_completionHandler_(js, None)
  1609:             except Exception as e:
  1610:                 logger.debug("Failed evaluating showToast in WebKit: %s", e)
  ```

Observation details:
- `grep_search` across `popover_ui.py` confirms `logger` is only referenced on lines 1592 and 1607. Neither `import logging` nor `logger = logging.getLogger(...)` exists in `popover_ui.py`.
- Verbatim error reproduced when `show_toast` encounters any WebKit JavaScript evaluation failure:
  ```
  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/popover_ui.py", line 1605, in show_toast
      self._web_view.evaluateJavaScript_completionHandler_(js, None)
  RuntimeError: WebKit IPC bridge down

  During handling of the above exception, another exception occurred:

  Traceback (most recent call last):
    ...
  NameError: name 'logger' is not defined
  ```
- Verbatim error reproduced when `_on_quit` throws an exception during `quit_application`:
  ```
  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/popover_ui.py", line 1590, in quit_application
      self._on_quit()
  Exception: [Mock error]

  During handling of the above exception, another exception occurred:

  NameError: name 'logger' is not defined
  ```
- The out-of-process application bundle `/Applications/League of Legends RPC.app/Contents/Resources/popover_ui.py` contains the identical defect on lines 1592 and 1607.

### 1.2 Status Item Right-Click Cocoa NSMenu (R1)
- `status_item.py` lines 94-96:
  `self._button.sendActionOn_(AppKit.NSEventMaskLeftMouseUp | AppKit.NSEventMaskRightMouseUp)` properly enables both mouse buttons.
- `status_item.py` lines 134-182:
  `build_context_menu()` constructs `AppKit.NSMenu` with:
  * "Abrir Popover" (`menuOpenPopover:`)
  * "Pausar Presencia" / "Reanudar Presencia" (`menuTogglePresence:`) dynamically reflecting `self._current_state`
  * "Configuración ⚙️" (`menuOpenSettings:`, shortcut `,`)
  * Separator
  * "Salir de Discord RPC" (`menuQuit:`, shortcut `q`)
- `statusItemButtonClicked_`:
  Properly checks `AppKit.NSApp.currentEvent()` for `NSEventTypeRightMouseUp`, `NSEventTypeRightMouseDown`, and `NSEventModifierFlagControl`. If true, displays menu with `popUpStatusItemMenu_`. Left click preserves standard popover toggle.

### 1.3 In-App Quit Controls (R1)
- `liquid_html.py` lines 989-1000 and 1073-1083:
  Quit buttons `<button class="quit-btn" onclick="sendAction('quit_app')">` and `<button class="quit-app-btn" onclick="sendAction('quit_app')">` are rendered in `#view-main` and `#view-config`.
- `popover_ui.py` line 169:
  `LoLWebBridge` maps action `"quit_app"` to `self._controller.quit_application()`.
- Native fallback button `self._quit_button` exists for environments where WebKit is not active.

### 1.4 Single-Instance Controller & Focus IPC (R1)
- `app_gui.py` lines 63-234:
  `SingleInstanceController` implements non-blocking `fcntl.flock` on `~/.config/lol_discord_rpc/app.lock` and Unix domain socket server on `~/.config/lol_discord_rpc/app.sock`.
- Stale socket detection: unlinks dead socket before binding.
- Secondary instance: sends `b"FOCUS\n"` to domain socket, activates existing application via `NSRunningApplication.activateWithOptions_`, and exits with code `0`.
- Primary instance listener thread: accepts `b"FOCUS"`, dispatches focus and popover show via `AppHelper.callAfter(self.controller.focus_popover)`.
- Cleanup: safely unlinks socket and releases `flock`.

### 1.5 Hardened LaunchAgent Plist (R1)
- `popover_ui.py` lines 1285-1315:
  LaunchAgent plist template points directly to `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC` with `--silent`. It does NOT use `/usr/bin/open`.
- Plist specifies `StandardOutPath` (`~/Library/Logs/lol_discord_rpc.log`) and `StandardErrorPath` (`~/Library/Logs/lol_discord_rpc_error.log`).
- `app_gui.py` line 510:
  When launched with `--silent`, suppresses auto-display of the popover while displaying system notification via `osascript` with subtitle `"Ejecutándose en la barra de menús"`.

### 1.6 System Event Listeners & Error Toast Boundary (R4)
- `app_gui.py` lines 295-345:
  Registers `NSWorkspace.sharedWorkspace().notificationCenter()` observers for `NSWorkspaceDidLaunchApplicationNotification` and `NSWorkspaceDidWakeNotification`.
  Matches `bundleIdentifier` or `localizedName` containing `"discord"` and calls `rpc_manager.reconnect()`. System wake also calls `rpc_manager.reconnect()`.
- `discord_rpc_manager.py` lines 316-320 & 589-594:
  `reconnect()` puts `("RECONNECT", None)` on `_cmd_queue`. Unblocks backoff sleep in `_cmd_queue.get(timeout=3.5)`, safely closes existing RPC client, and re-initiates connection immediately.
- `liquid_html.py` lines 766-836 & 1079-1108:
  Adds `#toast-container` with animated CSS toasts (`.toast-error`, `.toast-warning`, `.toast-info`), `window.showToast()`, and window listeners for `error` and `unhandledrejection`.
- `app_gui.py` line 431:
  Routes RPC state errors to `popover.show_toast(message, "error")`.

### 1.7 Verification Commands and Results
1. `venv/bin/python -m unittest tests/test_milestone7_lifecycle.py`:
   - Result: 13/13 tests passed in 0.718s.
2. `venv/bin/python tests/run_tests.py`:
   - Result: 149/149 tests passed (100% across Tiers 1 to 5) in 21.240s.
3. `venv/bin/python -m unittest tests/test_audit_fixes.py tests/test_challenger_audit_2.py`:
   - Result: 30/30 tests passed in 3.190s.
4. `venv/bin/python -c "import sync_bundle; print(sync_bundle.verify_bundle_integrity(detailed=True))"`:
   - Result: `valid: True`, 0 errors.
5. `venv/bin/python -m unittest tests/test_challenger_m7_stress.py`:
   - Result: FAILED (failures=1, errors=8).
   - Verbatim failure: `AssertionError: show_toast failed to catch evaluateJavaScript exception: name 'logger' is not defined`.

---

## 2. Logic Chain

```
Observation 1.1: popover_ui.py uses `logger.warning(...)` on line 1592 and `logger.debug(...)` on line 1607, but neither `logging` nor `logger` is imported or defined.
       │
       ▼
Logic Step 1: When WebKit JavaScript evaluation fails during `show_toast()`, or when `_on_quit()` raises an exception during `quit_application()`, Python raises `NameError: name 'logger' is not defined`.
       │
       ▼
Logic Step 2: Requirement R4 explicitly mandates an in-app error boundary so WebKit or socket exceptions display friendly feedback rather than crashing or terminating silently. Because the exception handler itself raises a NameError, any WebKit evaluation failure crashes the host process.
       │
       ▼
Logic Step 3: Requirement R1 mandates clean in-app quit controls. If an exception occurs in `_on_quit()`, the application is supposed to fall back to `AppKit.NSApplication.sharedApplication().terminate_(None)`. Instead, it crashes with an unhandled NameError.
       │
       ▼
Logic Step 4: The production application bundle at `/Applications/League of Legends RPC.app/Contents/Resources/popover_ui.py` contains the identical code and will fail identically in production.
       │
       ▼
Conclusion: The milestone implementation fails quality and correctness criteria due to an unhandled NameError in the error boundary and quit handlers. Verdict MUST be REQUEST_CHANGES.
```

---

## 3. Findings

### [Critical] Finding 1: Unhandled `NameError` in `LoLPopoverController.show_toast`
- **What**: `logger.debug("Failed evaluating showToast in WebKit: %s", e)` causes an unhandled `NameError` because `logger` is undefined in `popover_ui.py`.
- **Where**: `popover_ui.py:1607`
- **Why**: Violates Requirement R4. When WebKit encounters an evaluation error, IPC crash, or during window teardown, `show_toast` crashes the application instead of degrading gracefully.
- **Suggestion**: Add the following imports to `popover_ui.py`:
  ```python
  import logging

  logger = logging.getLogger("popover_ui")
  ```

### [Critical] Finding 2: Unhandled `NameError` in `LoLPopoverController.quit_application`
- **What**: `logger.warning("Error invoking on_quit callback: %s", e)` causes an unhandled `NameError` when `_on_quit()` throws an exception.
- **Where**: `popover_ui.py:1592`
- **Why**: Violates Requirement R1. Prevents fallback termination via `NSApp.terminate_` when `_on_quit` encounters an error.
- **Suggestion**: Resolved by defining `logger` at module level as described in Finding 1.

### [Major] Finding 3: Application Bundle Out of Sync with Defect Resolution
- **What**: `/Applications/League of Legends RPC.app/Contents/Resources/popover_ui.py` contains the defective code.
- **Where**: `/Applications/League of Legends RPC.app/Contents/Resources/popover_ui.py:1592, 1607`
- **Why**: The production bundle must not ship with unhandled `NameError` bugs.
- **Suggestion**: Re-run `venv/bin/python sync_bundle.py` after fixing `popover_ui.py`.

### [Minor / Test Fragility] Finding 4: PyObjC Runtime Pollution in Adversarial Test Suite
- **What**: `tests/test_challenger_m7_stress.py` lines 399-401 uses `unittest.mock.patch("AppKit.NSWorkspace.sharedWorkspace")`. In PyObjC, patching class selectors on Objective-C class objects fails on `__exit__` with `AttributeError: Cannot remove selector 'sharedWorkspace' in 'NSWorkspace'`, leaving the selector permanently bound to a `MagicMock`. This caused 98 subsequent test failures across discovery.
- **Where**: `tests/test_challenger_m7_stress.py:399`
- **Why**: Tests should avoid monkey-patching native PyObjC class selectors.
- **Suggestion**: In `test_challenger_m7_stress.py`, mock `notificationCenter` without patching `sharedWorkspace` on `NSWorkspace` class.

---

## 4. Verified Claims

| Claim | Method | Pass/Fail |
|---|---|---|
| Menubar Right-Click Context Menu with 4 required items | `tests/test_milestone7_lifecycle.py::TestStatusItemContextMenu` | **PASS** |
| Dynamic presence title ("Pausar Presencia" / "Reanudar Presencia") | Inspected `status_item.py:156` & unit tests | **PASS** |
| In-app quit buttons in `#view-main` and `#view-config` | Inspected `liquid_html.py` & WebBridge dispatch tests | **PASS** |
| Single-Instance lock prevents duplicates and sends FOCUS | Inspected `SingleInstanceController`, verified via standalone test | **PASS** |
| LaunchAgent plist points to binary directly with logs in `~/Library/Logs/` | Inspected `_sync_login_item` and verified plist XML | **PASS** |
| Launch notification displayed on silent launch | Inspected `LoLAppDelegate.applicationDidFinishLaunching_` | **PASS** |
| NSWorkspace observers reconnect on Discord launch and sleep wake | Inspected `onAppLaunched_`, `onSystemWake_`, and tests | **PASS** |
| Master test runner 149/149 passing | Executed `venv/bin/python tests/run_tests.py` | **PASS** |
| WebKit JS evaluation failure in `show_toast` handled cleanly | Executed `test_challenger_m7_stress.py::test_popover_show_toast_evaluation_failure_safe` | **FAIL** (`NameError: name 'logger' is not defined`) |

---

## 5. Adversarial Challenge & Stress Test Results

- **Overall Risk Assessment**: HIGH (due to NameError crash in error boundary)
- **Attack Scenario 1**: WebKit bridge down or evaluation error during `show_toast`.
  - Trigger: WebKit web process terminates or evaluates invalid JS.
  - Expected: `show_toast` catches exception and logs debug warning; host app continues uninterrupted.
  - Actual: `NameError: name 'logger' is not defined` unhandled exception crashes app.
  - Result: **FAIL**
- **Attack Scenario 2**: `on_quit` callback throws exception during `quit_application`.
  - Trigger: Teardown exception in listener or socket unbind.
  - Expected: Caught, warning logged, fallback `NSApp.terminate_(None)` called.
  - Actual: `NameError: name 'logger' is not defined` unhandled exception crashes app.
  - Result: **FAIL**
- **Attack Scenario 3**: Primary instance killed with SIGKILL leaving dead socket.
  - Trigger: Terminate primary with `-9`.
  - Expected: Next instance acquires `fcntl.flock`, deletes stale socket, rebinds server.
  - Actual: Passed cleanly.
  - Result: **PASS**
- **Attack Scenario 4**: Rapid concurrent Discord launch notifications.
  - Trigger: 50 concurrent notifications.
  - Expected: Thread-safe queue enqueuing without blocking UI.
  - Actual: Passed cleanly.
  - Result: **PASS**

---

## 6. Caveats

- As reviewer/critic, per strict teamwork constraints, I have not modified `popover_ui.py`. The fix must be applied by `worker_m7_1`.
- The PyObjC mock leak in `tests/test_challenger_m7_stress.py` was authored by the challenger agent and does not reflect product code, but should be addressed for clean test discovery.

---

## 7. Conclusion

**Verdict**: **REQUEST_CHANGES**

The core functional logic of Milestone M7 (right-click NSMenu, UI quit buttons, SingleInstanceController, LaunchAgent hardening, and NSWorkspace listeners) is well-architected and genuine. However, `popover_ui.py` contains two critical `NameError: name 'logger' is not defined` bugs on lines 1592 and 1607 that cause the error boundary and quit fallback to crash the application.

Required actions before approval:
1. In `popover_ui.py`, add `import logging` and `logger = logging.getLogger("popover_ui")`.
2. Re-synchronize the application bundle using `venv/bin/python sync_bundle.py`.
3. Verify that `venv/bin/python -m unittest tests/test_challenger_m7_stress.py` passes the `test_popover_show_toast_evaluation_failure_safe` test.

---

## 8. Verification Method

1. **Verify `logger` presence**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "import popover_ui; assert hasattr(popover_ui, 'logger'), 'logger missing'"
   ```

2. **Verify `show_toast` exception handling**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import popover_ui
   from unittest.mock import MagicMock
   ctrl = popover_ui.LoLPopoverController()
   ctrl._web_view = MagicMock()
   ctrl._web_view.evaluateJavaScript_completionHandler_.side_effect = RuntimeError("Bridge down")
   ctrl.show_toast("test", "error")
   print("show_toast exception handling: PASSED")
   '
   ```

3. **Verify `quit_application` fallback**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import popover_ui
   ctrl = popover_ui.LoLPopoverController(on_quit=lambda: (_ for _ in ()).throw(RuntimeError("fail")))
   ctrl.quit_application()
   print("quit_application fallback: PASSED")
   '
   ```

4. **Verify bundle synchronization**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c "import sync_bundle; print(sync_bundle.verify_bundle_integrity(detailed=True))"
   ```

5. **Invalidation Conditions**:
   - `hasattr(popover_ui, 'logger')` evaluates to `False`.
   - Any unhandled `NameError` when `evaluateJavaScript_completionHandler_` or `on_quit` raises an exception.
