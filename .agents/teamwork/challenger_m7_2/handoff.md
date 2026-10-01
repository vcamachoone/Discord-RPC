# Handoff Report — Milestone M7 Empirical Challenge

**Agent**: `challenger_m7_2`  
**Date**: 2026-09-29T23:36:30Z  
**Task**: Milestone M7 Empirical Stress Testing (System Event Listeners, Error Toast, UI Quit, Master Test Suite)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### 1.1 `popover_ui.py`: Undefined Variable `logger` (NameError)
- **File**: `/Users/victormanuel/discord-rpc/popover_ui.py`
- **Lines 1587-1593** (`quit_application`):
  ```python
  1587:         if callable(self._on_quit):
  1588:             try:
  1589:                 self._on_quit()
  1590:                 return
  1591:             except Exception as e:
  1592:                 logger.warning("Error invoking on_quit callback: %s", e)
  ```
- **Lines 1604-1608** (`show_toast`):
  ```python
  1604:             try:
  1605:                 self._web_view.evaluateJavaScript_completionHandler_(js, None)
  1606:             except Exception as e:
  1607:                 logger.debug("Failed evaluating showToast in WebKit: %s", e)
  ```
- **Evidence**:
  Neither `import logging` nor `logger = logging.getLogger(...)` exists in `popover_ui.py`.
  When testing exception handling in `quit_application()` and `show_toast()`, Python crashes with:
  ```
  NameError: name 'logger' is not defined
  ```
  Verbatim traceback from `tests/test_challenger_m7_stress.py`:
  ```
  FAIL: test_popover_quit_handles_on_quit_exception (tests.test_challenger_m7_stress.TestInAppQuitAndLifecycleStress)
  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/popover_ui.py", line 1589, in quit_application
      self._on_quit()
  RuntimeError: Failure in on_quit callback

  During handling of the above exception, another exception occurred:

  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/tests/test_challenger_m7_stress.py", line 388, in test_popover_quit_handles_on_quit_exception
      ctrl.quit_application()
  NameError: name 'logger' is not defined
  ```

### 1.2 `tests/run_tests.py`: Intermittent Test Failure in `test_f10_graceful_shutdown`
- **Command**: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
- **Result**: Exit code 1 on initial run:
  ```
  Tier 1: Feature Coverage
    Module   : tests.test_tier1_features
    Status   : FAIL
    Results  : 59 passed, 0 skipped, 1 failed / 60 total
    Duration : 3.478s

    --- Failures in Tier 1: Feature Coverage ---
    • test_f10_graceful_shutdown (tests.test_tier1_features.TestF10RPCManager)
        File "/Users/victormanuel/discord-rpc/tests/test_tier1_features.py", line 654, in test_f10_graceful_shutdown
          self.assertFalse(mgr._worker_thread.is_alive())
      AssertionError: True is not false
  ```
- **Root Cause Analysis**:
  In `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` lines 320-326:
  ```python
  def shutdown(self) -> None:
      self._running = False
      self._cmd_queue.put(("SHUTDOWN", None))
      if self._worker_thread.is_alive():
          self._worker_thread.join(timeout=2.5)
  ```
  When Discord is running on the macOS host, `new_rpc.connect()` performs socket connection and handshake with `/var/folders/.../discord-ipc-0`, followed by `_send_rpc_update()`. If `shutdown()` is called concurrently, the socket connection is NOT closed by `shutdown()` (it is only closed after the thread exits loop at line 482). The thread remains blocked in socket operations exceeding the 2.5s join timeout, leaving `mgr._worker_thread.is_alive() == True`.

### 1.3 System Event Listeners (`NSWorkspace` Notifications)
- **Files**: `app_gui.py` lines 296-341, `discord_rpc_manager.py` lines 316-320
- **Empirical Test Results** (`tests/test_challenger_m7_stress.py`):
  * `test_discord_launch_matrix`: Verified `onAppLaunched_` triggers `reconnect()` for Discord bundle IDs (`com.hnc.Discord`, `com.hnc.DiscordCanary`, `com.hnc.DiscordPTB`, `com.hnc.DiscordDevelopment`, uppercase variations) and ignores non-Discord applications (`Safari`, `Chrome`, `League of Legends`, `Finder`, `Slack`, `Spotify`). **PASS**.
  * `test_malformed_launch_notifications`: Verified `None`, empty dicts, missing keys, or corrupted notification objects do not crash `onAppLaunched_`. **PASS**.
  * `test_shutdown_suppresses_launch_events`: Verified `onAppLaunched_` and `onSystemWake_` are ignored when `_is_shutting_down == True`. **PASS**.
  * `test_system_wake_notification`: Verified `onSystemWake_` triggers `reconnect()`. **PASS**.
  * `test_reconnect_concurrency_stress`: 50 concurrent threads executing 500 rapid `reconnect()` calls enqueued cleanly without deadlock or race condition. **PASS**.

### 1.4 Error Toast Boundary
- **Files**: `liquid_html.py` lines 779-840 & 1090-1130, `popover_ui.py` lines 1597-1608
- **Empirical Test Results**:
  * DOM container `#toast-container` and CSS animation classes (`.toast`, `.toast-error`, `.toast-warning`, `.toast-info`) are properly generated. **PASS**.
  * `window.showToast` correctly escapes HTML tags, preventing XSS injection. **PASS**.
  * Global error boundary (`window.addEventListener('error')` and `window.addEventListener('unhandledrejection')`) forwards unhandled errors to `window.showToast`. **PASS**.
  * `popover_ui.py:show_toast` converts messages via `json.dumps()` and safely handles null web views. **PASS**.
  * **Defect**: Exception during `evaluateJavaScript_completionHandler_` crashes with `NameError: name 'logger' is not defined` (see Section 1.1).

### 1.5 UI Quit Controls
- **Files**: `liquid_html.py`, `popover_ui.py`, `app_gui.py`
- **Empirical Test Results**:
  * In-app quit buttons present in `#view-main` (`.quit-btn`) and `#view-config` (`.quit-app-btn`) with `sendAction('quit_app')`. **PASS**.
  * `LoLWebBridge` receives `quit_app` and invokes `controller.quit_application()`. **PASS**.
  * `LoLPopoverController.quit_application()` closes popover and invokes `on_quit`. **PASS**.
  * `LoLAppController.quit()` cleanly unregisters Cocoa workspace notifications, closes popover, cleans up status item, shuts down RPC manager, and is idempotent. **PASS**.
  * **Defect**: If `on_quit` raises an exception, `popover_ui.py:1592` crashes with `NameError: name 'logger' is not defined` (see Section 1.1).

---

## 2. Logic Chain

1. **Observation 1.1**: `popover_ui.py` lines 1592 and 1607 call `logger.warning(...)` and `logger.debug(...)`, but `logger` is not defined anywhere in the module.
2. **Logic Step 1**: When an exception occurs in `_on_quit()` or in `_web_view.evaluateJavaScript_completionHandler_`, Python enters the `except Exception as e:` block and encounters an undefined identifier `logger`, triggering an uncaught `NameError`.
3. **Observation 1.2**: Running `tests/run_tests.py` resulted in a test failure in `Tier 1: Feature Coverage (test_f10_graceful_shutdown)` because `_worker_thread.join(timeout=2.5)` timed out while communicating with the active Discord IPC socket.
4. **Logic Step 2**: `DiscordRPCManager.shutdown()` sets `_running = False` and enqueues `SHUTDOWN`, but does not call `self._safe_close_rpc()` before `join()`. If the worker thread is in the middle of socket I/O (connecting or handshaking with Discord), it does not read from the queue until the socket call completes, which can exceed 2.5 seconds.
5. **Logic Step 3**: Because of the `NameError` in `popover_ui.py` and the intermittent failure in the master test runner, the work product does not pass empirical challenge criteria and cannot be approved in its current state.

---

## 3. Caveats

- System event notification tests rely on simulated `NSNotification` objects because triggering actual macOS kernel sleep/wake cycles or external Discord app launches would disrupt the developer environment.
- The `test_f10_graceful_shutdown` failure is timing-dependent and reproduces primarily when the Discord client is actively running on the host machine.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The implementation of Milestone M7 is largely robust and complete, but contains two concrete defects that must be addressed:
1. **Fix `NameError` in `popover_ui.py`**:
   Add `import logging` and `logger = logging.getLogger(__name__)` at module top in `popover_ui.py`.
2. **Harden `DiscordRPCManager.shutdown()` in `discord_rpc_manager.py`**:
   Call `self._safe_close_rpc()` inside `shutdown()` before joining the worker thread (to immediately abort blocking socket operations) and increase the join timeout slightly (e.g., to 3.5s-4.0s) to prevent intermittent timeouts under live Discord IPC load.

---

## 5. Verification Method

1. **Verify `NameError` Bug Reproduction**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m7_stress.py
   ```
   *Expected Failure*: `test_popover_ui_logger_defined` and `test_popover_quit_handles_on_quit_exception` fail with `NameError: name 'logger' is not defined`.
   *Resolution Target*: After adding `logger = logging.getLogger(__name__)` in `popover_ui.py`, all 17 tests in `tests/test_challenger_m7_stress.py` must pass.

2. **Verify Master Test Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
   *Resolution Target*: 149/149 tests pass cleanly across all 5 tiers (100% success).

3. **Verify Milestone M7 Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone7_lifecycle.py
   ```
