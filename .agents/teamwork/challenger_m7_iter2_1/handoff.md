# Handoff Report — Empirical Challenger Stress Test (M7 Remediation)

**Agent**: `challenger_m7_iter2_1`  
**Date**: 2026-09-30T03:48:00Z  
**Verdict**: **REQUEST_CHANGES**  
**Role**: Critic / Empirical Challenger  

---

## 1. Observation

### 1.1 Concurrency & Deadlock Stress Test
- Tested multi-threaded stress invocations of `_process_command("RECONNECT", None)` and `reconnect()` on `DiscordRPCManager`:
  * Harness 1 (`auto_start=False`, `is_active=True`): 40 threads, 100 iterations per thread.
    - Result: `Deadlock test 1: threads alive=0, errors=0, elapsed=0.000s`.
  * Harness 2 (`auto_start=True` with active worker loop): 20 threads, 50 iterations per thread.
    - Result: `Deadlock test 2: alive=0, errors=0, elapsed=0.063s`.
- Direct observation: The worker's remediation replacing `threading.Lock` with `threading.RLock` at line 233 of `discord_rpc_manager.py` and removing the redundant outer lock at lines 590-596 resolved the recursive self-deadlock.

### 1.2 Execution of `tests/test_adversarial_m7_challenger.py`
- Executed command:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_adversarial_m7_challenger.py
  ```
- Output:
  ```
  Ran 12 tests in 2.374s
  OK
  ```
- All 12 empirical process isolation, context menu, and LaunchAgent tests passed cleanly.

### 1.3 Execution of Master Test Runner `tests/run_tests.py`
- Executed command:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
  ```
- Result: **FAILED** (Exit code 1).
- Verbatim output:
  ```
    Tier 1: Feature Coverage
      Module   : tests.test_tier1_features
      Status   : FAIL
      Results  : 59 passed, 0 skipped, 1 failed / 60 total
      Duration : 4.908s

      --- Failures in Tier 1: Feature Coverage ---
      • test_f10_graceful_shutdown (tests.test_tier1_features.TestF10RPCManager)
          File "/Users/victormanuel/discord-rpc/tests/test_tier1_features.py", line 654, in test_f10_graceful_shutdown
            self.assertFalse(mgr._worker_thread.is_alive())
        AssertionError: True is not false

  ══════════════════════════════════════════════════════════════════════════════
  FINAL TEST SUITE SUMMARY
  ══════════════════════════════════════════════════════════════════════════════
    Tier Name                                Total    Pass    Skip    Fail     Time
    -------------------------------------- ------- ------- ------- ------- --------
    Tier 1: Feature Coverage                    60      59       0       1   4.908s
    Tier 2: Boundary & Corner Cases             60      60       0       0   0.817s
    Tier 3: Cross-Feature Interactions          14      14       0       0   0.065s
    Tier 4: Real-World Scenarios                 5       5       0       0   7.075s
    Tier 5: Adversarial Stress & Faults         10      10       0       0  13.829s
    -------------------------------------- ------- ------- ------- ------- --------
    TOTAL                                      149     148       0       1  26.694s
  ══════════════════════════════════════════════════════════════════════════════

  ✗ TEST SUITE FAILED WITH 1 ERRORS/FAILURES
  ```

### 1.4 Stress-Testing `shutdown()` While Connection Loop is Active
- Executed empirical test calling `mgr.shutdown()` while the background connection loop is active:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python -c '
  import time
  from discord_rpc_manager import DiscordRPCManager

  failures = 0
  for i in range(5):
      mgr = DiscordRPCManager(auto_start=True)
      time.sleep(0.1)
      t0 = time.time()
      mgr.shutdown()
      dur = time.time() - t0
      alive = mgr._worker_thread.is_alive()
      if alive:
          failures += 1
          print(f"Iter {i}: FAILED (alive={alive}, dur={dur:.3f}s)")
      else:
          print(f"Iter {i}: PASSED (alive={alive}, dur={dur:.3f}s)")
  print(f"Total failures: {failures}/5")
  '
  ```
- Output:
  ```
  Iter 0: FAILED (alive=True, dur=4.006s)
  Iter 1: FAILED (alive=True, dur=4.005s)
  Iter 2: FAILED (alive=True, dur=4.003s)
  Iter 3: FAILED (alive=True, dur=4.005s)
  Iter 4: FAILED (alive=True, dur=4.000s)
  Total failures: 5/5
  ```
- **Thread Stack Inspection**:
  During the 4.0-second shutdown hang, stack inspection via `sys._current_frames()` reveals the worker thread blocked at:
  ```
    File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 418, in _worker_loop
      new_rpc.connect()
    File "/Users/victormanuel/discord-rpc/venv/lib/python3.9/site-packages/pypresence/presence.py", line 85, in connect
      self.loop.run_until_complete(self.handshake())
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/asyncio/base_events.py", line 629, in run_until_complete
      self.run_forever()
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/asyncio/base_events.py", line 1854, in _run_once
      event_list = self._selector.select(timeout)
    File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/selectors.py", line 562, in select
      kev_list = self._selector.control(None, max_ev, timeout)
  ```
- **Code Inspection in `discord_rpc_manager.py`**:
  * Lines 417–420:
    ```python
    new_rpc = Presence(self.client_id, loop=self._loop)
    new_rpc.connect()
    with self._lock:
        self._rpc = new_rpc
    ```
    `new_rpc` is a local variable. `self._rpc` remains `None` throughout the execution of `new_rpc.connect()`.
  * Lines 320–327 in `shutdown()`:
    ```python
    def shutdown(self) -> None:
        self._running = False
        self._safe_close_rpc()
        self._cmd_queue.put(("SHUTDOWN", None))
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=4.0)
    ```
  * Lines 384–398 in `_safe_close_rpc()`:
    ```python
    def _safe_close_rpc(self) -> None:
        with self._lock:
            rpc = self._rpc
            self._rpc = None
        if rpc: ...
    ```
    Because `self._rpc` is `None` while `connect()` is in-flight, `_safe_close_rpc()` does nothing.
  * In `pypresence`, `Presence.connect()` instantiates its own event loop via `self.update_event_loop(get_event_loop())`. The connection blocks on socket read/write inside kernel `kqueue`.
  * Because `shutdown()` neither closes `new_rpc` nor stops its event loop, `self._worker_thread.join(timeout=4.0)` blocks for the full 4.0 seconds, times out, and leaves the worker thread permanently running.

---

## 2. Logic Chain

```
Observation 1.4: During active connection attempts, new_rpc is created as a local variable; self._rpc remains None until connect() finishes.
       │
       ▼
Logic Step 1: When shutdown() is invoked while connect() is in-flight, _safe_close_rpc() finds self._rpc == None and takes no action. The active Unix socket writer and its transport remain open.
       │
Observation 1.4 Stack Trace: Worker thread blocks in new_rpc.connect() -> self.loop.run_until_complete(self.handshake()) -> kqueue select().
       │
       ▼
Logic Step 2: Because the socket is not aborted or closed, and the asyncio event loop is not stopped, new_rpc.connect() cannot complete or raise an exception.
       │
Observation 1.4 Timing: shutdown() calls self._worker_thread.join(timeout=4.0), which always times out at 4.005s.
       │
       ▼
Logic Step 3: shutdown() exits while self._worker_thread is still running in the background, creating a thread leak.
       │
Observation 1.3: Master test runner venv/bin/python tests/run_tests.py fails in Tier 1 with AssertionError: True is not false at line 654 of test_tier1_features.py (self.assertFalse(mgr._worker_thread.is_alive())).
       │
       ▼
Logic Step 4: The master test suite fails to achieve the required 100% pass rate (148/149 passed).
       │
       ▼
Conclusion: The M7 remediation is incomplete. A definitive verdict of REQUEST_CHANGES must be issued to fix the shutdown socket abortion and event loop termination.
```

---

## 3. Caveats

- **No Unexplored Areas**: Both concurrency/deadlock stress and connection shutdown stress were directly executed and empirically verified with multiple multi-threaded harnesses and stack introspection.
- **Root Cause Verified via Working Prototype**: An empirical test subclassing `DiscordRPCManager` with `self._pending_rpc`, `sock_writer.transport.abort()`, and loop stopping reduced `shutdown()` duration from 4.005s to 0.000s with 0 thread leaks across 5/5 runs.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

The M7 remediation made significant progress:
1. Upgrading `self._lock` to `threading.RLock()` and removing the outer lock in `_process_command("RECONNECT", None)` completely eliminated the recursive mutex deadlock.
2. `tests/test_adversarial_m7_challenger.py` passes 100% (12/12 tests).
3. The `NameError` in `popover_ui.py` and non-dict WebKit payloads in `LoLWebBridge` are resolved.

However, **Milestone M7 cannot be approved** because:
1. `tests/run_tests.py` failed with 1 failure in Tier 1 (`test_f10_graceful_shutdown`), violating the requirement of 100% passing tests (148/149).
2. Calling `shutdown()` while the connection loop is active blocks for 4.0 seconds and leaves the worker thread alive (100% failure rate in empirical stress testing).

### Actionable Remediation Required:
1. **Track In-Flight Connection in `discord_rpc_manager.py`**:
   - In `__init__`, add `self._pending_rpc: Optional[Presence] = None`.
   - In `_worker_loop`, set `with self._lock: self._pending_rpc = new_rpc` *before* calling `new_rpc.connect()`. Upon completion or in a `finally` block, clear `self._pending_rpc = None`.
2. **Harden `_safe_close_rpc()`**:
   - In `_safe_close_rpc()`, retrieve and clear both `self._rpc` and `self._pending_rpc`.
   - For all active instances:
     * If `rpc.sock_writer` exists and has `transport`: call `rpc.sock_writer.transport.abort()`.
     * Call `rpc.sock_writer.close()`.
     * If `rpc.loop` exists and `rpc.loop.is_running()`: call `rpc.loop.call_soon_threadsafe(rpc.loop.stop)`.
     * Call `rpc.close()`.
3. **Patch `TestF10RPCManager` in `tests/test_tier1_features.py`**:
   - Use `unittest.mock.patch("discord_rpc_manager.Presence", MockPresence)` across `TestF10RPCManager` so unit tests do not attempt live socket handshakes against external daemons.

---

## 5. Verification Method

To independently verify the failure and subsequent fix:

1. **Reproduce Master Test Suite Failure**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
   *Expected Current Failure*: Tier 1 `test_f10_graceful_shutdown` fails with `AssertionError: True is not false`.

2. **Reproduce Shutdown Hang & Thread Leak**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import time
   from discord_rpc_manager import DiscordRPCManager

   mgr = DiscordRPCManager(auto_start=True)
   time.sleep(0.1)
   t0 = time.time()
   mgr.shutdown()
   dur = time.time() - t0
   alive = mgr._worker_thread.is_alive()
   print(f"dur={dur:.3f}s, alive={alive}")
   assert not alive, "Worker thread leaked after shutdown!"
   '
   ```
   *Expected Current Failure*: `dur=4.005s, alive=True`, `AssertionError: Worker thread leaked after shutdown!`.

3. **Verify Concurrency & Deadlock Safety (Passing)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import threading
   from discord_rpc_manager import DiscordRPCManager

   mgr = DiscordRPCManager(auto_start=False)
   threads = [threading.Thread(target=mgr._process_command, args=("RECONNECT", None)) for _ in range(50)]
   for t in threads: t.start()
   for t in threads: t.join(timeout=1.0)
   assert all(not t.is_alive() for t in threads), "Deadlock occurred!"
   print("SUCCESS: Zero deadlocks detected.")
   '
   ```

4. **Invalidation Conditions**:
   - `tests/run_tests.py` passes with 149/149 (100%) tests.
   - `shutdown()` while connection is active terminates in `< 0.1s` with `mgr._worker_thread.is_alive() == False`.
