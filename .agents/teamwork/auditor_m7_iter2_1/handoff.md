# Forensic Audit Report — Milestone M7 Remediation

**Work Product**: Milestone M7 Remediation (`discord_rpc_manager.py`, `popover_ui.py`, `tests/test_milestone7_lifecycle.py`)  
**Auditor**: `auditor_m7_iter2_1`  
**Profile**: General Project  
**Integrity Mode**: Development (authoritative baseline from `ORIGINAL_REQUEST.md`)  
**Verdict**: **INTEGRITY VIOLATION** (REJECTED)

---

## Forensic Audit Summary

| Check # | Forensic Verification Check | Status | Direct Empirical Evidence |
|---|---|---|---|
| 1 | Genuine `threading.RLock()` in `discord_rpc_manager.py` | **PASS** | Line 233 declares `self._lock: threading.RLock = threading.RLock()`. |
| 2 | Removal of redundant outer lock in `_process_command("RECONNECT")` | **PASS** | Lines 598-604 call `self._safe_close_rpc()` directly; no nested lock. |
| 3 | Genuine `logging` import and `logger` in `popover_ui.py` | **PASS** | Lines 27 & 32 declare `import logging` and `logger = logging.getLogger("popover_ui")`. |
| 4 | Genuine body type validation in `LoLWebBridge` | **PASS** | Line 143 validates `isinstance(body, dict)`. |
| 5 | Genuineness of tests in `tests/test_milestone7_lifecycle.py` | **PASS** | Direct execution of production classes and methods; no mock bypasses masking logic. |
| 6 | Execution of `tests/test_milestone7_lifecycle.py` | **PASS** | 19/19 tests passed in 0.854s. |
| 7 | Execution of Master Test Runner (`tests/run_tests.py`) | **FAIL** | **Exited with code 1**. 148 passed, 0 skipped, 1 failed (`test_f11_b5_timer_cleanup_on_shutdown`). |
| 8 | Concurrency & Thread Teardown Determinism | **FAIL** | Worker thread leaks on shutdown: 12% failure rate on `test_f11_b5_timer_cleanup_on_shutdown` (6/50 failures) and 14% on `test_rpc_manager_shutdown_closes_rpc_and_joins` (7/50 failures). |

---

## 1. Observation

### 1.1 Verified Genuine Remediations
1. **`threading.RLock()` in `discord_rpc_manager.py`**:
   * File: `/Users/victormanuel/discord-rpc/discord_rpc_manager.py:233`
   * Verbatim code:
     ```python
     self._lock: threading.RLock = threading.RLock()
     ```
2. **`_process_command("RECONNECT")` Lock Nesting Removed**:
   * File: `/Users/victormanuel/discord-rpc/discord_rpc_manager.py:598-604`
   * Verbatim code:
     ```python
     elif cmd == "RECONNECT":
         self._safe_close_rpc()
         with self._lock:
             active = self.is_active
         if active:
             self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")
     ```
3. **`logger` in `popover_ui.py`**:
   * File: `/Users/victormanuel/discord-rpc/popover_ui.py:27, 32`
   * Verbatim code:
     ```python
     import logging
     ...
     logger = logging.getLogger("popover_ui")
     ```
   * Safely called in `quit_application()` (line 1595) and `show_toast()` (line 1610).
4. **`LoLWebBridge` Body Validation**:
   * File: `/Users/victormanuel/discord-rpc/popover_ui.py:141-145`
   * Verbatim code:
     ```python
     def userContentController_didReceiveScriptMessage_(self, ucc, message):
         body = message.body()
         if not body or not isinstance(body, dict) or not self._controller:
             return
         action = body.get("action")
     ```
5. **No Mock Bypasses in `tests/test_milestone7_lifecycle.py`**:
   * Tests directly exercise production code (`LoLStatusItemController.build_context_menu()`, `SingleInstanceController.check_and_acquire()`, `LoLWebBridge.userContentController_didReceiveScriptMessage_`, `popover_ui.LoLPopoverController.quit_application()`, `discord_rpc_manager.DiscordRPCManager.reconnect()`).

---

### 1.2 Direct Empirical Failure: Master Test Suite (`tests/run_tests.py`)
- **Execution Command**:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
  ```
- **Exit Code**: `1` (Non-zero failure).
- **Verbatim Tool Output**:
  ```
  Tier 1: Feature Coverage
    Module   : tests.test_tier1_features
    Status   : PASS
    Results  : 60 passed, 0 skipped, 0 failed / 60 total
    Duration : 0.894s

  Tier 2: Boundary & Corner Cases
    Module   : tests.test_tier2_boundaries
    Status   : FAIL
    Results  : 59 passed, 0 skipped, 1 failed / 60 total
    Duration : 4.871s

    --- Failures in Tier 2: Boundary & Corner Cases ---
    • test_f11_b5_timer_cleanup_on_shutdown (tests.test_tier2_boundaries.TestF11BoundaryTimer)
        File "/Users/victormanuel/discord-rpc/tests/test_tier2_boundaries.py", line 651, in test_f11_b5_timer_cleanup_on_shutdown
          self.assertFalse(mgr._worker_thread.is_alive())
      AssertionError: True is not false

  Tier 3: Cross-Feature Interactions
    Module   : tests.test_tier3_interactions
    Status   : PASS
    Results  : 14 passed, 0 skipped, 0 failed / 14 total
    Duration : 0.064s

  Tier 4: Real-World Scenarios
    Module   : tests.test_tier4_scenarios
    Status   : PASS
    Results  : 5 passed, 0 skipped, 0 failed / 5 total
    Duration : 7.072s

  Tier 5: Adversarial Stress & Faults
    Module   : tests.test_adversarial_stress
    Status   : PASS
    Results  : 10 passed, 0 skipped, 0 failed / 10 total
    Duration : 13.816s

  TOTAL: 149 total, 148 passed, 0 skipped, 1 failed / 26.718s
  ✗ TEST SUITE FAILED WITH 1 ERRORS/FAILURES
  ```

---

### 1.3 Concurrency Flaw & Thread Leak in `DiscordRPCManager.shutdown()`
In `worker_m7_2/handoff.md`, the worker claimed:
> *"In `shutdown()` (lines 320-327): Proactively called `self._safe_close_rpc()` before `self._worker_thread.join(timeout=4.0)`. This aborts any active socket I/O immediately so the worker thread is not blocked in connection teardown."*

This claim is **empirically false**.
1. **Flaky Stress Test Execution**:
   - Running `test_f11_b5_timer_cleanup_on_shutdown` 50 times in isolation:
     ```bash
     /Users/victormanuel/discord-rpc/venv/bin/python -c '
     from tests.test_tier2_boundaries import TestF11BoundaryTimer
     import unittest
     suite = unittest.TestSuite()
     for _ in range(50):
         suite.addTest(TestF11BoundaryTimer("test_f11_b5_timer_cleanup_on_shutdown"))
     runner = unittest.TextTestRunner(verbosity=0)
     res = runner.run(suite)
     print(f"Ran 50 times: failures={len(res.failures)}, errors={len(res.errors)}")
     '
     ```
     **Result**: `Ran 50 times: failures=6, errors=0` (**12% failure rate**).
   - Running the worker's own new test `test_rpc_manager_shutdown_closes_rpc_and_joins` 50 times:
     ```bash
     /Users/victormanuel/discord-rpc/venv/bin/python -c '
     from tests.test_milestone7_lifecycle import TestSystemEventListenersAndToast
     import unittest
     suite = unittest.TestSuite()
     for _ in range(50):
         suite.addTest(TestSystemEventListenersAndToast("test_rpc_manager_shutdown_closes_rpc_and_joins"))
     runner = unittest.TextTestRunner(verbosity=0)
     res = runner.run(suite)
     print(f"Lifecycle test ran 50 times: failures={len(res.failures)}, errors={len(res.errors)}")
     '
     ```
     **Result**: `Lifecycle test ran 50 times: failures=7, errors=0` (**14% failure rate**).

2. **Root Cause Thread Dump**:
   When `mgr.shutdown()` takes > 4.0s, inspection of `sys._current_frames()` reveals the worker thread's exact stack trace:
   ```python
   FAILED on iteration 5, took 4.01s
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/threading.py", line 930, in _bootstrap
       self._bootstrap_inner()
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/threading.py", line 973, in _bootstrap_inner
       self.run()
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/threading.py", line 910, in run
       self._target(*self._args, **self._kwargs)
     File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 418, in _worker_loop
       new_rpc.connect()
     File "/Users/victormanuel/discord-rpc/venv/lib/python3.9/site-packages/pypresence/presence.py", line 85, in connect
       self.loop.run_until_complete(self.handshake())
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/base_events.py", line 629, in run_until_complete
       self.run_forever()
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/base_events.py", line 596, in run_forever
       self._run_once()
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/asyncio/base_events.py", line 1854, in _run_once
       event_list = self._selector.select(timeout)
     File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/selectors.py", line 562, in select
       kev_list = self._selector.control(None, max_ev, timeout)
   ```
   **Mechanism of Failure**:
   - In `_worker_loop` (lines 417-420):
     ```python
     new_rpc = Presence(self.client_id, loop=self._loop)
     new_rpc.connect()
     with self._lock:
         self._rpc = new_rpc
     ```
   - While `new_rpc.connect()` is executing its handshake (searching/connecting to the Discord IPC pipe in `asyncio.run_until_complete(self.handshake())`), `self._rpc` is still `None`.
   - When `shutdown()` is called:
     ```python
     def shutdown(self) -> None:
         self._running = False
         self._safe_close_rpc()
         self._cmd_queue.put(("SHUTDOWN", None))
         if self._worker_thread.is_alive():
             self._worker_thread.join(timeout=4.0)
     ```
     `self._safe_close_rpc()` only inspects and closes `self._rpc`. Because `self._rpc` is `None`, `self._safe_close_rpc()` does **nothing**.
   - The worker thread is not reading `self._cmd_queue` because it is blocked in `new_rpc.connect()`.
   - `pypresence`'s handshake timeout is ~5 seconds.
   - `self._worker_thread.join(timeout=4.0)` expires after 4.0 seconds, returning while the thread is still alive.
   - Any test checking `self.assertFalse(mgr._worker_thread.is_alive())` immediately fails.

---

## 2. Logic Chain

```
Observation 1.2: tests/run_tests.py failed with exit code 1 during audit execution (test_f11_b5_timer_cleanup_on_shutdown failed in Tier 2).
       │
       ▼
Logic Step 1: ORIGINAL_REQUEST.md (§Acceptance Criteria) requires: "100% of automated tests pass across all tiers with zero regressions." A non-zero test runner exit violates this baseline acceptance criterion.
       │
Observation 1.3: Worker claimed in handoff.md that calling self._safe_close_rpc() in shutdown() "aborts any active socket I/O immediately so the worker thread is not blocked in connection teardown."
       │
       ▼
Logic Step 2: Thread stack trace inspection proves that while new_rpc.connect() is executing, self._rpc is None. self._safe_close_rpc() is a no-op on new_rpc. The worker thread remains blocked in selector control for ~5 seconds.
       │
Observation 1.3: Empirical testing of both test_f11_b5_timer_cleanup_on_shutdown and test_rpc_manager_shutdown_closes_rpc_and_joins over 50 iterations exhibits a 12% to 14% failure rate.
       │
       ▼
Logic Step 3: Under the Integrity Forensics specification: "The build must succeed and tests must execute — a project that doesn't build or whose tests don't run is automatically flagged." If ANY check fails, the verdict is INTEGRITY VIOLATION.
       │
       ▼
Conclusion: Work product fails behavioral verification and acceptance criteria. Final verdict is INTEGRITY VIOLATION.
```

---

## 3. Caveats

- **No Caveats**: The investigation isolated the failure down to the thread stack trace and reproduction frequency. The deadlock, logger NameError, and WebBridge type checking items were successfully fixed; however, the concurrency teardown flaw causes genuine, non-deterministic test failures in the master test runner and violates the 100% pass requirement.

---

## 4. Conclusion

**Verdict: INTEGRITY VIOLATION (REJECTED)**

1. `tests/run_tests.py` failed with exit code 1 due to `test_f11_b5_timer_cleanup_on_shutdown` (`AssertionError: True is not false`).
2. `DiscordRPCManager.shutdown()` possesses a race condition where `_safe_close_rpc()` fails to abort an ongoing `new_rpc.connect()` attempt because `self._rpc` is not yet populated. This causes `join(timeout=4.0)` to time out and leaves the background worker thread alive, resulting in a 12-14% failure rate across test suites.
3. The work product must be returned to the worker to fix the shutdown teardown sequence so that any in-flight connection attempt is immediately aborted/cancelled and `_worker_thread.join()` deterministically completes in < 0.5s without timing out.

---

## 5. Verification Method

To independently reproduce this forensic finding:

1. **Run Master Test Runner**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
2. **Reproduce the Thread Teardown Timeout Stress (Tier 2)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   from tests.test_tier2_boundaries import TestF11BoundaryTimer
   import unittest
   suite = unittest.TestSuite()
   for _ in range(50):
       suite.addTest(TestF11BoundaryTimer("test_f11_b5_timer_cleanup_on_shutdown"))
   runner = unittest.TextTestRunner(verbosity=0)
   res = runner.run(suite)
   print(f"Tier 2 test ran 50 times: failures={len(res.failures)}, errors={len(res.errors)}")
   '
   ```
3. **Reproduce the Thread Teardown Timeout Stress (Milestone 7 Lifecycle)**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   from tests.test_milestone7_lifecycle import TestSystemEventListenersAndToast
   import unittest
   suite = unittest.TestSuite()
   for _ in range(50):
       suite.addTest(TestSystemEventListenersAndToast("test_rpc_manager_shutdown_closes_rpc_and_joins"))
   runner = unittest.TextTestRunner(verbosity=0)
   res = runner.run(suite)
   print(f"Lifecycle test ran 50 times: failures={len(res.failures)}, errors={len(res.errors)}")
   '
   ```
4. **Invalidation Condition**:
   - `tests/run_tests.py` exits 0 with 100% pass across multiple consecutive runs.
   - `test_f11_b5_timer_cleanup_on_shutdown` and `test_rpc_manager_shutdown_closes_rpc_and_joins` pass 100/100 runs with 0 failures, and `shutdown()` terminates worker threads in < 0.5s.
