# Handoff Report — Milestone M7 Remediation Review (Hard Handoff)

**Agent**: `reviewer_m7_iter2_2`  
**Roles**: Reviewer, Adversarial Critic  
**Date**: 2026-09-30T03:47:00Z  
**Verdict**: **REQUEST_CHANGES**  

---

## 1. Observation

### 1.1 `discord_rpc_manager.py` Concurrency & Mutex Inspection
- **Line 233**: Mutex upgraded to re-entrant lock:
  ```python
  self._lock: threading.RLock = threading.RLock()
  ```
  Verified: Re-entrant acquisition on the same thread succeeds without deadlock.
- **Lines 598-604**: Redundant outer lock around `self._safe_close_rpc()` removed in `_process_command`:
  ```python
  elif cmd == "RECONNECT":
      self._safe_close_rpc()
      with self._lock:
          active = self.is_active
      if active:
          self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")
  ```
  Verified: Calling `_process_command("RECONNECT", None)` on a thread does not cause self-deadlock.

### 1.2 Flaw in `shutdown()` and `_worker_loop` Socket Lifecycle
- **Lines 320-327** (`shutdown()`):
  ```python
  def shutdown(self) -> None:
      """Gracefully terminates the background worker and closes Discord IPC socket."""
      self._running = False
      self._safe_close_rpc()
      self._cmd_queue.put(("SHUTDOWN", None))
      if self._worker_thread.is_alive():
          self._worker_thread.join(timeout=4.0)
  ```
- **Lines 411-422** (`_worker_loop()`):
  ```python
  if active and (rpc is None):
      self._notify_state(RPCState.CONNECTING, "Conectando a Discord...")
      try:
          new_rpc = Presence(self.client_id, loop=self._loop)
          new_rpc.connect()
          with self._lock:
              self._rpc = new_rpc
          self._notify_state(RPCState.CONNECTED, "Activo en Discord")
          self._send_rpc_update()
  ```
- **Defect Observation**:
  `new_rpc = Presence(...)` calls `new_rpc.connect()` before storing `new_rpc` in `self._rpc`.
  During the execution of `new_rpc.connect()`, `self._rpc` remains `None`.
  When `shutdown()` is called while `new_rpc.connect()` is awaiting a response on the Discord IPC socket (`sock_reader.read(8)` in `pypresence` without timeout), `self._safe_close_rpc()` finds `self._rpc is None` and fails to close `new_rpc`'s socket.
  Because the socket is not closed and `new_rpc.connect()` is blocked on network I/O, the worker thread does not process `_cmd_queue`.
  After 4.0 seconds, `self._worker_thread.join(timeout=4.0)` expires, leaving `self._worker_thread.is_alive()` as `True`.

### 1.3 Test Execution Results

#### Test Suite 1: Milestone M7 Lifecycle Tests
- **Command**: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone7_lifecycle.py`
- **Output**:
  ```
  Ran 19 tests in 0.827s
  OK
  ```
  Status: **PASS** (19/19 passed).

#### Test Suite 2: Challenger M7 Stress Suite
- **Command**: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m7_stress.py`
- **Output**:
  ```
  ======================================================================
  FAIL: test_rpc_manager_shutdown_race (tests.test_challenger_m7_stress.TestErrorToastStress)
  Stress-tests RPCManager rapid auto_start shutdown to detect worker thread join timeout.
  ----------------------------------------------------------------------
  Traceback (most recent call last):
    File "/Users/victormanuel/discord-rpc/tests/test_challenger_m7_stress.py", line 295, in test_rpc_manager_shutdown_race
      self.assertEqual(failures, 0, f"Worker thread remained alive after shutdown() in {failures}/10 iterations")
  AssertionError: 1 != 0 : Worker thread remained alive after shutdown() in 1/10 iterations

  ----------------------------------------------------------------------
  Ran 17 tests in 9.240s
  FAILED (failures=1)
  ```
  Status: **FAIL** (1 failure).

#### Test Suite 3: Master E2E Test Runner (`tests/run_tests.py`)
- **Command**: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
- **Output**:
  ```
    Tier 1: Feature Coverage
      Module   : tests.test_tier1_features
      Status   : FAIL
      Results  : 59 passed, 0 skipped, 1 failed / 60 total
      Duration : 5.005s

      --- Failures in Tier 1: Feature Coverage ---
      • test_f10_graceful_shutdown (tests.test_tier1_features.TestF10RPCManager)
          File "/Users/victormanuel/discord-rpc/tests/test_tier1_features.py", line 654, in test_f10_graceful_shutdown
            self.assertFalse(mgr._worker_thread.is_alive())
        AssertionError: True is not false

  FINAL TEST SUITE SUMMARY
    TOTAL 149, 148 passed, 0 skipped, 1 failed
  ✗ TEST SUITE FAILED WITH 1 ERRORS/FAILURES
  Exit code: 1
  ```
  Status: **FAIL** (Exit code 1).

### 1.4 Stack Trace of Stuck Worker Thread During Shutdown
Captured via diagnostic thread frame dump when `shutdown()` times out:
```
THREAD STILL ALIVE! Frame:
  File ".../threading.py", line 910, in run
    self._target(*self._args, **self._kwargs)
  File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 418, in _worker_loop
    new_rpc.connect()
  File ".../pypresence/presence.py", line 85, in connect
    self.loop.run_until_complete(self.handshake())
  File ".../asyncio/base_events.py", line 629, in run_until_complete
    self.run_forever()
  File ".../asyncio/base_events.py", line 596, in run_forever
    self._run_once()
  File ".../asyncio/base_events.py", line 1854, in _run_once
    event_list = self._selector.select(timeout)
  File ".../selectors.py", line 562, in select
    kev_list = self._selector.control(None, max_ev, timeout)
```

---

## 2. Logic Chain

```
Observation 1.1: self._lock was upgraded to threading.RLock(), and redundant outer lock around _safe_close_rpc() in RECONNECT handler was removed.
       │
       ▼
Logic Step 1: Internal recursive locking and RECONNECT command dispatch no longer self-deadlock.
       │
Observation 1.2 & 1.4: In _worker_loop(), new_rpc is created and new_rpc.connect() is called BEFORE assigning self._rpc = new_rpc. While connect() awaits handshake data, self._rpc is None.
       │
       ▼
Logic Step 2: Calling shutdown() invokes _safe_close_rpc(). Because self._rpc is None, the socket cannot be closed by shutdown(). The worker thread remains stuck in connect() on the live Discord IPC socket.
       │
Observation 1.2: shutdown() waits self._worker_thread.join(timeout=4.0).
       │
       ▼
Logic Step 3: When connect() takes longer than 4.0s or Discord delays response, join() times out and returns while the worker thread is still alive.
       │
Observation 1.3: test_rpc_manager_shutdown_race in test_challenger_m7_stress.py fails (1/10 iterations alive after shutdown) and test_f10_graceful_shutdown in tests/run_tests.py fails with AssertionError: True is not false.
       │
       ▼
Conclusion: Milestone M7 fails acceptance criteria (100% test pass across all suites). The verdict must be REQUEST_CHANGES.
```

---

## 3. Findings

### Critical Finding 1: Race Condition in `shutdown()` While `Presence.connect()` is in Progress
- **What**: `DiscordRPCManager.shutdown()` fails to terminate the worker thread within `timeout=4.0` when `shutdown()` is called rapidly after `auto_start=True`.
- **Where**: `discord_rpc_manager.py`, lines 320–327 and 416–422.
- **Why**:
  1. `new_rpc` is not assigned to `self._rpc` (or any instance variable) prior to calling `new_rpc.connect()`.
  2. `_safe_close_rpc()` only inspects `self._rpc`. Because `self._rpc` is `None` during connection setup, `_safe_close_rpc()` cannot close the connecting socket.
  3. `new_rpc.connect()` performs `self.loop.run_until_complete(self.handshake())` which waits synchronously on socket I/O without timeout.
  4. The worker thread cannot unblock to read `("SHUTDOWN", None)` from `self._cmd_queue`.
  5. `self._worker_thread.join(timeout=4.0)` times out, causing `test_rpc_manager_shutdown_race` and `test_f10_graceful_shutdown` to fail.
- **Suggested Fix**:
  1. In `_worker_loop`:
     Track the pending connection instance under lock before calling `connect()` (e.g., `with self._lock: self._connecting_rpc = new_rpc`), OR wrap `connect()` with an explicit `asyncio.wait_for(new_rpc.handshake(), timeout=2.0)`.
  2. In `_safe_close_rpc()`:
     Close both `self._rpc` and `self._connecting_rpc` (closing `sock_writer` and calling `sock_writer.transport.abort()` if present).
  3. Immediately after `new_rpc.connect()` returns or catches an exception, verify `if not self._running:` before assigning `self._rpc` or notifying state.
  4. In `shutdown()`:
     Ensure the connecting socket is proactively aborted so `new_rpc.connect()` raises/aborts immediately, allowing the worker thread to exit promptly.

---

## 4. Caveats

- **No Caveats**: The issue was reproduced under live conditions with Discord running on macOS. The failures in `tests/test_challenger_m7_stress.py` and `tests/run_tests.py` are reproducible and documented with verbatim tracebacks.

---

## 5. Conclusion

**Verdict**: **REQUEST_CHANGES**

Milestone M7 remediation resolved the re-entrant deadlock and missing `logger` definitions, but introduced/retained a critical shutdown race condition where `shutdown()` cannot abort an in-flight `new_rpc.connect()`. Both `tests/test_challenger_m7_stress.py` and `tests/run_tests.py` fail. Changes must be requested from the worker agent to track and abort in-flight connection sockets during `shutdown()`.

---

## 6. Verification Method

To independently verify these findings:

1. **Reproduce Failure in `test_challenger_m7_stress.py`**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_challenger_m7_stress.py -k test_rpc_manager_shutdown_race
   ```
   *Expected Result*: Fails with `AssertionError: 1 != 0 : Worker thread remained alive after shutdown() in 1/10 iterations`.

2. **Reproduce Failure in Master Runner**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   ```
   *Expected Result*: Exits with code 1, reporting failure in `test_f10_graceful_shutdown`.

3. **Verify Thread Hang Diagnostic**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import discord_rpc_manager
   mgr = discord_rpc_manager.DiscordRPCManager(auto_start=True)
   mgr.shutdown()
   assert not mgr._worker_thread.is_alive(), "Worker thread alive after shutdown"
   '
   ```
