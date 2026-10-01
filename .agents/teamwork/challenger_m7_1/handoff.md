# Handoff Report — Milestone M7 Empirical Challenge

**Agent**: `challenger_m7_1`  
**Date**: 2026-09-29T23:41:00Z  
**Task**: Empirical Stress-Testing of Milestone M7 Implementations (SingleInstanceController, Context Menu, LaunchAgent Plist)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### 1.1 Empirical Verification of SingleInstanceController (`tests/test_adversarial_m7_challenger.py`)
- Created and executed isolated multi-process stress test suite `tests/test_adversarial_m7_challenger.py`.
- **Command**:
  ```bash
  venv/bin/python -m unittest tests/test_adversarial_m7_challenger.py
  ```
- **Results**:
  * `test_secondary_process_exits_0_and_notifies_primary`: Spawned primary process with `SingleInstanceController`. Launched secondary Python process. Verified secondary exited with returncode `0` in `< 0.2s` and delivered `b"FOCUS\n"` across the Unix domain socket. Primary received and registered FOCUS signal. **PASS**.
  * `test_sigkill_stale_socket_recovery`: Spawned primary process. Forcibly killed primary with `SIGKILL` (`kill -9`, bypassing all Python cleanup logic). Verified `app.lock` and `app.sock` remained on disk. Launched recovery instance: verified it cleanly acquired lock, unlinked stale socket file, bound new socket, and listened. Launched secondary against recovery instance: secondary exited with code `0` and delivered FOCUS to the recovered primary. **PASS**.
  * `test_burst_concurrency_10_secondaries`: Launched 10 secondary processes simultaneously against 1 primary instance. All 10 exited with code `0` within 1.2s without dropped connections, socket exhaustion, or deadlocks. **PASS**.
  * `test_corrupted_non_socket_file_recovery`: Placed corrupted non-socket regular file with arbitrary bytes at `app.sock`. SingleInstanceController cleanly unlinked it and bound a new socket. **PASS**.
  * `test_real_app_gui_entrypoint_as_secondary`: Executed actual `app_gui.py` and `app_gui.py --silent` as subprocesses against a running primary in an isolated `$HOME`. Both exited with returncode `0` immediately without presenting UI windows or dock icons. **PASS**.

### 1.2 Empirical Verification of Context Menu via PyObjC
- In `status_item.py` lines 142-189 (`build_context_menu()`):
  * Constructs native `AppKit.NSMenu` containing 5 items:
    1. `"Abrir Popover"` (`b"menuOpenPopover:"`, target `self`)
    2. Dynamic presence item (`b"menuTogglePresence:"`, target `self`): reflects `"Pausar Presencia"` when state is `"active"` and `"Reanudar Presencia"` when state is `"paused"`, `"normal"`, or invalid fallback.
    3. `"Configuración ⚙️"` (`b"menuOpenSettings:"`, keyEquivalent `","`, target `self`)
    4. Separator (`isSeparatorItem() == True`)
    5. `"Salir de Discord RPC"` (`b"menuQuit:"`, keyEquivalent `"q"`, target `self`)
  * `test_menu_structure_and_selectors`: Verified item order, actions, selectors, and keyEquivalents. **PASS**.
  * `test_dynamic_presence_title_all_states`: Verified title switching across all connection states. **PASS**.
  * `test_selector_invocations_and_none_callbacks`: Verified invoking selectors triggers registered callbacks and handles `None` callbacks without unhandled exceptions. **PASS**.
  * `test_click_event_discrimination`: Verified right-click (`NSEventTypeRightMouseUp`, `NSEventTypeRightMouseDown`) and Control+Click trigger `popUpStatusItemMenu_`, while left-click triggers `_on_toggle` without popping the menu. **PASS**.

### 1.3 Empirical Verification of LaunchAgent Plist
- Inspected installed LaunchAgent at `/Users/victormanuel/Library/LaunchAgents/com.victormanuel.lolrpc.plist` and verified code generator in `popover_ui.py:1280-1320`:
  * `Label`: `"com.victormanuel.lolrpc"`.
  * `ProgramArguments`: Exactly `['/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC', '--silent']`.
  * `/usr/bin/open`: Confirmed completely absent from arguments.
  * Target binary `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`: Confirmed exists on disk, is a file, and has executable permission (`os.access(..., os.X_OK) == True`).
  * `StandardOutPath`: `/Users/victormanuel/Library/Logs/lol_discord_rpc.log` (absolute, inside `~/Library/Logs/`).
  * `StandardErrorPath`: `/Users/victormanuel/Library/Logs/lol_discord_rpc_error.log` (absolute, inside `~/Library/Logs/`).
  * `ProcessType`: `"Interactive"`, `RunAtLoad`: `True`.
  * `test_installed_launchagent_plist` and `test_sync_login_item_code_generation`: **PASS**.

### 1.4 Defect 1: `NameError: name 'logger' is not defined` in `popover_ui.py`
- **File**: `/Users/victormanuel/discord-rpc/popover_ui.py`
- **Line 1592** in `quit_application`:
  ```python
  1587:         if callable(self._on_quit):
  1588:             try:
  1589:                 self._on_quit()
  1590:                 return
  1591:             except Exception as e:
  1592:                 logger.warning("Error invoking on_quit callback: %s", e)
  ```
- **Line 1607** in `show_toast`:
  ```python
  1604:             try:
  1605:                 self._web_view.evaluateJavaScript_completionHandler_(js, None)
  1606:             except Exception as e:
  1607:                 logger.debug("Failed evaluating showToast in WebKit: %s", e)
  ```
- **Empirical Evidence**:
  Neither `import logging` nor `logger = logging.getLogger(...)` exists in `popover_ui.py`.
  When testing exception handling in `quit_application()` and `show_toast()`, Python crashes with:
  ```
  FAIL: test_popover_quit_handles_on_quit_exception (test_challenger_m7_stress.TestInAppQuitAndLifecycleStress)
  ...
  NameError: name 'logger' is not defined
  ```
  and:
  ```
  FAIL: test_popover_ui_logger_defined (test_challenger_m7_stress.TestErrorToastStress)
  AssertionError: False is not true : popover_ui is missing 'logger' definition referenced in lines 1592 and 1607
  ```

### 1.5 Defect 2: Thread Join Timeout / Race in `discord_rpc_manager.py:shutdown()`
- **File**: `/Users/victormanuel/discord-rpc/discord_rpc_manager.py` lines 320-326
- **Evidence**:
  ```python
  def shutdown(self) -> None:
      self._running = False
      self._cmd_queue.put(("SHUTDOWN", None))
      if self._worker_thread.is_alive():
          self._worker_thread.join(timeout=2.5)
  ```
  When the Discord client is active on the macOS host, `new_rpc.connect()` blocks in socket connect/handshake. If `shutdown()` is called, `self._safe_close_rpc()` is not invoked before `join()`. The worker thread remains blocked on socket I/O exceeding 2.5 seconds, leaving the thread alive.
- **Empirical Evidence**:
  `tests/test_challenger_m7_stress.py` `test_rpc_manager_shutdown_race`:
  ```
  AssertionError: 4 != 0 : Worker thread remained alive after shutdown() in 4/10 iterations
  ```
  Also observed in `tests/run_tests.py` Tier 1 `test_f10_graceful_shutdown`:
  ```
  AssertionError: True is not false (self.assertFalse(mgr._worker_thread.is_alive()))
  ```

---

## 2. Logic Chain

1. **Observation 1.1 - 1.3**: The core Milestone M7 requirements for `SingleInstanceController` (process isolation, SIGKILL recovery, secondary exit 0, socket focus), Context Menu (NSMenu structure, dynamic titles, click discrimination), and LaunchAgent plist (direct bundle binary, --silent, logs in ~/Library/Logs) are functionally well-architected and passed all 12 empirical adversarial tests in `tests/test_adversarial_m7_challenger.py`.
2. **Observation 1.4**: `popover_ui.py` references `logger` on lines 1592 and 1607, but `logger` is never imported or defined anywhere in `popover_ui.py`.
3. **Logic Step 1**: When `quit_application()` encounters an exception in `on_quit`, or when `show_toast()` encounters a WebKit JavaScript evaluation exception, Python enters the exception handler and raises `NameError: name 'logger' is not defined`. This turns what should be a graceful error recovery path into an unhandled fatal crash.
4. **Observation 1.5**: `discord_rpc_manager.py:shutdown()` relies on `_worker_thread.join(timeout=2.5)` without aborting in-flight socket connections via `_safe_close_rpc()`.
5. **Logic Step 2**: Under live Discord IPC communication, socket handshake operations can take longer than 2.5 seconds, causing `shutdown()` to exit while `_worker_thread` is still alive. This produces intermittent test failures in Tier 1 (`test_f10_graceful_shutdown`) and thread leaks during rapid lifecycle restarts.
6. **Logic Step 3**: Because of the `NameError` crash and the shutdown thread leak race condition, Milestone M7 does not satisfy commercial-grade stability requirements and must be revised.

---

## 3. Caveats

- In headless execution environments without an active Cocoa runloop, `NSRunningApplication` activation and `AppHelper.callAfter` gracefully fall back to direct callback execution; this was verified both inside and outside runloop contexts.
- The `SingleInstanceController` test suite uses isolated temporary configuration directories (`tempfile.mkdtemp`) to avoid touching the developer's live `~/.config/lol_discord_rpc/` state.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone M7 cannot be approved until the following two defects are corrected:
1. **Fix `popover_ui.py` `NameError`**:
   Add `import logging` and `logger = logging.getLogger(__name__)` at the top of `/Users/victormanuel/discord-rpc/popover_ui.py`.
2. **Harden `discord_rpc_manager.py:shutdown()`**:
   In `shutdown()`, call `self._safe_close_rpc()` before `self._worker_thread.join()` to terminate blocking socket operations immediately, and set the join timeout to 3.5s.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Adversarial M7 Suite (12/12 Passing)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_adversarial_m7_challenger.py
   ```
2. **Reproduce `popover_ui.py` NameError and Shutdown Race**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m7_stress.py
   ```
   *Expected Failure*: Fails on `test_popover_ui_logger_defined`, `test_popover_quit_handles_on_quit_exception`, and `test_rpc_manager_shutdown_race`.
3. **Invalidation Conditions**:
   - `hasattr(popover_ui, 'logger')` evaluates to True and `quit_application()` does not raise `NameError` when `on_quit` fails.
   - `shutdown()` cleanly terminates the worker thread in 10/10 iterations under active Discord socket load.
   - All tests in `tests/test_adversarial_m7_challenger.py`, `tests/test_challenger_m7_stress.py`, and `tests/run_tests.py` pass with 100% success.
