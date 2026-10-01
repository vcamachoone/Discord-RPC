# Handoff Report — Milestone M7 Adversarial Challenge (Empirical Challenger)

**Agent**: `challenger_m7_iter2_2`  
**Date**: 2026-09-30T03:49:00Z  
**Role**: Empirical Challenger (Critic / Specialist)  
**Task**: Empirically stress test M7 UI & Error Boundaries, malformed WebKit message bodies, exception logging, and full test suites.  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

### 1.1 Malicious & Malformed Script Message Bodies in `popover_ui.py`
- **Location**: `popover_ui.py` lines 141–176 (`LoLWebBridge.userContentController_didReceiveScriptMessage_`).
- **Implementation**:
  ```python
  def userContentController_didReceiveScriptMessage_(self, ucc, message):
      body = message.body()
      if not body or not isinstance(body, dict) or not self._controller:
          return
      action = body.get("action")
      ...
  ```
- **Empirical Stress Test**:
  Executed a matrix of 49 distinct malformed, hostile, and circular payloads via `python -c`:
  * Non-dict primitives: `0`, `1`, `-1`, `10**50`, `0.0`, `3.14`, `float("nan")`, `float("inf")`, `""`, `"malicious\x00str"`, `None`, `True`, `False`, `[]`, `[1, 2]`, `[{"action": "quit_app"}]`, `()`, `set()`, `object()`.
  * Circular objects: Circular list `l = []; l.append(l)`.
  * Malformed dict structures: `{}`, `{"action": None}`, `{"action": 123}`, `{"action": "unknown_action"}`, `{"action": ""}`.
  * Circular dictionaries: `d = {}; d["self"] = d; d["action"] = "select_mode"`.
  * Circular dictionary references inside action fields:
    - `{"action": "select_mode", "mode": circ_dict}`
    - `{"action": "toggle_autoreset", "value": circ_dict}`
    - `{"action": "toggle_autorun", "value": "true"}`
    - `{"action": "save_config", "game_id": circ_dict, "client_id": 9999, "details": None, "duration_min": "invalid"}`
    - `{"action": "change_champion", "name": circ_dict}`
    - `{"action": "change_rank", "rank": circ_dict}`
    - `{"action": "change_division", "division": circ_dict}`
    - `{"action": "change_game_mode", "game_mode": circ_dict}`
  * Results: All 49 payloads were handled safely without raising unhandled exceptions or crashing `LoLPopoverController`.
  * Edge Case: Calling `bridge.userContentController_didReceiveScriptMessage_(None, None)` raises `AttributeError: 'NoneType' object has no attribute 'body'`, though WebKit Cocoa delegate protocol guarantees non-nil `WKScriptMessage` in standard runtime.

### 1.2 Exception Simulation in `on_quit` and `evaluateJavaScript`
- **Location**: `popover_ui.py` lines 1588–1611 (`quit_application()` and `show_toast()`).
- **Implementation**:
  ```python
  def quit_application(self) -> None:
      self.close()
      if callable(self._on_quit):
          try:
              self._on_quit()
              return
          except Exception as e:
              logger.warning("Error invoking on_quit callback: %s", e)
      app = AppKit.NSApplication.sharedApplication()
      if app and app.isRunning():
          app.terminate_(None)

  def show_toast(self, message: str, toast_type: str = "error") -> None:
      if getattr(self, "_web_view", None):
          import json
          escaped_msg = json.dumps(str(message))
          escaped_type = json.dumps(str(toast_type))
          js = f"if (window.showToast) {{ window.showToast({escaped_msg}, {escaped_type}); }}"
          try:
              self._web_view.evaluateJavaScript_completionHandler_(js, None)
          except Exception as e:
              logger.debug("Failed evaluating showToast in WebKit: %s", e)
  ```
- **Empirical Verification**:
  * Simulated `RuntimeError`, `ValueError`, and custom exceptions with unicode/emojis (`CustomError("💥⚠️")`) in `on_quit`.
  * Output captured from `popover_ui.logger`:
    ```
    [WARNING] popover_ui: Error invoking on_quit callback: Simulated runtime error in on_quit
    [WARNING] popover_ui: Error invoking on_quit callback: Simulated value error:   invalid!
    [WARNING] popover_ui: Error invoking on_quit callback: Custom error with unicode: ⚠️💥
    ```
  * Simulated `RuntimeError`, `ValueError`, and custom exceptions in `_web_view.evaluateJavaScript_completionHandler_`:
    ```
    [DEBUG] popover_ui: Failed evaluating showToast in WebKit: WebKit evaluateJavaScript failed
    [DEBUG] popover_ui: Failed evaluating showToast in WebKit: Invalid JS eval parameter
    [DEBUG] popover_ui: Failed evaluating showToast in WebKit: WebKit crashed: ⚡️
    ```
  * `logger = logging.getLogger("popover_ui")` is instantiated at line 32. Zero `NameError` exceptions occurred; formatting and logging operate cleanly.

### 1.3 Master E2E Test Runner Execution
- **Command**: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
- **Output**:
  ```
  Tier 1: Feature Coverage                    60      60       0       0   0.929s
  Tier 2: Boundary & Corner Cases             60      60       0       0   0.846s
  Tier 3: Cross-Feature Interactions          14      14       0       0   0.075s
  Tier 4: Real-World Scenarios                 5       5       0       0   7.119s
  Tier 5: Adversarial Stress & Faults         10      10       0       0  13.829s
  -------------------------------------- ------- ------- ------- ------- --------
  TOTAL                                      149     149       0       0  22.797s

  ✓ ALL EXECUTED TESTS PASSED CLEANLY (100% SUCCESS)
  ```

### 1.4 Defect Discovery: Shutdown Race in `DiscordRPCManager`
- **Command**:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests.test_challenger_m7_stress.TestErrorToastStress.test_rpc_manager_shutdown_race
  ```
- **Verbatim Error Output**:
  ```
  FAIL: test_rpc_manager_shutdown_race (tests.test_challenger_m7_stress.TestErrorToastStress)
  Stress-tests RPCManager rapid auto_start shutdown to detect worker thread join timeout.
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/tests/test_challenger_m7_stress.py", line 295, in test_rpc_manager_shutdown_race
      self.assertEqual(failures, 0, f"Worker thread remained alive after shutdown() in {failures}/10 iterations")
  AssertionError: 2 != 0 : Worker thread remained alive after shutdown() in 2/10 iterations
  ```
- **Discovery in Full Test Discovery**:
  Running `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover -s tests -p "test_*.py"` also failed with:
  `AssertionError: 3 != 0 : Worker thread remained alive after shutdown() in 3/10 iterations`.
- **Thread Stack Inspection**:
  Dumping stack of the hanging worker thread:
  ```
    File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 418, in _worker_loop
      new_rpc.connect()
    File "/Users/victormanuel/discord-rpc/venv/lib/python3.9/site-packages/pypresence/presence.py", line 85, in connect
      self.loop.run_until_complete(self.handshake())
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/asyncio/base_events.py", line 629, in run_until_complete
      self.run_forever()
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/asyncio/base_events.py", line 596, in run_forever
      self._run_once()
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/asyncio/base_events.py", line 1854, in _run_once
      event_list = self._selector.select(timeout)
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/selectors.py", line 562, in select
      kev_list = self._selector.control(None, max_ev, timeout)
  ```
- **Post-Shutdown Activity Defect**:
  When `new_rpc.connect()` returns after `shutdown()` was called, `_worker_loop` (lines 419–422) still executes:
  ```python
  with self._lock:
      self._rpc = new_rpc
  self._notify_state(RPCState.CONNECTED, "Activo en Discord")
  self._send_rpc_update()
  ```
  Empirically verified that `_send_rpc_update()` was invoked AFTER `mgr.shutdown()` had finished.

---

## 2. Logic Chain

```
Observation 1.1 & 1.2: LoLWebBridge type-validates message bodies; popover_ui logger is defined and cleanly logs exceptions in on_quit and show_toast.
       │
       ▼
Logic Step 1: UI WebBridge and Error Boundaries in popover_ui.py are verified resilient against hostile script messages and callback exceptions.
       │
Observation 1.3: Master test suite (tests/run_tests.py) passes 149/149 tests cleanly.
       │
Observation 1.4: test_rpc_manager_shutdown_race in tests/test_challenger_m7_stress.py fails intermittently (2 to 3 out of 10 runs).
       │
       ▼
Logic Step 2: In discord_rpc_manager.py line 417, new_rpc = Presence(self.client_id, loop=self._loop) is a local variable during new_rpc.connect().
       │
       ▼
Logic Step 3: When shutdown() is called while new_rpc.connect() is performing socket handshake, self._safe_close_rpc() finds self._rpc is None and cannot close new_rpc.sock_writer.
       │
       ▼
Logic Step 4: The worker thread remains blocked on asyncio socket read in handshake() until Discord responds or socket times out.
       │
       ▼
Logic Step 5: self._worker_thread.join(timeout=4.0) in shutdown() times out after 4.0s, leaving the worker thread alive (mgr._worker_thread.is_alive() == True).
       │
       ▼
Logic Step 6: When connect() completes, _worker_loop lacks an "if not self._running: break" guard, causing it to transition to CONNECTED and dispatch _send_rpc_update() after shutdown.
       │
       ▼
Conclusion: Milestone M7 cannot be approved until the shutdown race condition in DiscordRPCManager is resolved. Verdict is REQUEST_CHANGES.
```

---

## 3. Caveats

- In standard macOS Cocoa WebKit runtime, `userContentController:didReceiveScriptMessage:` always passes a non-nil `WKScriptMessage`. The `AttributeError` on `None` message object only arises in artificial direct Python calls (`bridge.userContentController_didReceiveScriptMessage_(None, None)`).
- The shutdown race in `test_rpc_manager_shutdown_race` manifests when Discord is running locally on the test host and socket handshakes take longer than join timeouts under rapid sequential connections.

---

## 4. Conclusion

**Verdict**: **REQUEST_CHANGES**

While UI script message validation and exception logging in `popover_ui.py` meet requirements and all 149 tests in `tests/run_tests.py` pass, **`tests/test_challenger_m7_stress.py` exhibits a real, reproducible failure** in `test_rpc_manager_shutdown_race`:
1. `DiscordRPCManager.shutdown()` does not abort in-flight `new_rpc.connect()` attempts, causing thread join timeouts (4.0s) and leaving `self._worker_thread.is_alive() == True`.
2. `DiscordRPCManager._worker_loop` dispatches presence updates even after `shutdown()` has completed.

### Actionable Mitigation for Worker:
In `discord_rpc_manager.py`:
1. Store the in-flight instance as `self._connecting_rpc = new_rpc` under lock prior to `new_rpc.connect()`, and clear it in a `finally:` block.
2. In `_safe_close_rpc()`, close both `self._rpc` and `self._connecting_rpc` (closing `sock_writer` so any pending `sock_reader.read(8)` in `handshake()` aborts immediately).
3. Immediately after `new_rpc.connect()` returns, add an exit guard:
   ```python
   if not self._running:
       self._safe_close_rpc()
       break
   ```
   preventing post-shutdown presence updates.

---

## 5. Verification Method

To independently verify this failure and resolution:

1. **Reproduce Failure in `test_challenger_m7_stress.py`**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests.test_challenger_m7_stress.TestErrorToastStress.test_rpc_manager_shutdown_race
   ```
   *Expected Current Output*: `AssertionError: 2 != 0 : Worker thread remained alive after shutdown() in 2/10 iterations`.

2. **Deterministic Race Reproduction**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import threading, time
   from unittest.mock import patch
   import discord_rpc_manager

   connect_started = threading.Event()

   class SlowPresence:
       def __init__(self, *args, **kwargs):
           self.sock_writer = None
       def connect(self):
           connect_started.set()
           time.sleep(5.0)
       def close(self):
           pass

   with patch("discord_rpc_manager.Presence", SlowPresence):
       mgr = discord_rpc_manager.DiscordRPCManager(auto_start=True)
       connect_started.wait(timeout=2.0)
       t0 = time.time()
       mgr.shutdown()
       dt = time.time() - t0
       alive = mgr._worker_thread.is_alive()
       print(f"Deterministic race: alive={alive}, shutdown_duration={dt:.2f}s")
       assert alive, "Expected alive=True due to timeout!"
   '
   ```

3. **Verify Malformed WebKit Message Bodies (49 Cases)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import popover_ui
   ctrl = popover_ui.LoLPopoverController()
   bridge = popover_ui.LoLWebBridge.alloc().initWithController_(ctrl)
   class Msg:
       def __init__(self, b): self._b = b
       def body(self): return self._b

   for p in [0, "str", None, True, [], {}, {"action": None}, {"action": {}}]:
       bridge.userContentController_didReceiveScriptMessage_(None, Msg(p))
   print("SUCCESS: Malformed bodies handled without exception")
   '
   ```

4. **Verify Clean Logging on `on_quit` and `evaluateJavaScript`**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import popover_ui
   ctrl = popover_ui.LoLPopoverController(on_quit=lambda: (_ for _ in ()).throw(RuntimeError("test")))
   ctrl.quit_application()
   ctrl.show_toast("test")
   print("SUCCESS: No NameError, clean logs")
   '
   ```

5. **Invalidation Conditions**:
   - `test_rpc_manager_shutdown_race` consistently passes 10/10 iterations without worker thread join timeout.
   - Deterministic in-flight shutdown cleanly terminates within <0.5s without timing out or leaving worker thread alive.
   - No presence updates are dispatched after `shutdown()`.
