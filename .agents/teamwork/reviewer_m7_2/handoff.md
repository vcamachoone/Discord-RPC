# Handoff Report — Adversarial Quality & Robustness Review (Milestone M7)

**Agent**: `reviewer_m7_2`  
**Date**: 2026-09-29T23:37:00Z  
**Role**: Reviewer, Adversarial Critic  
**Working Directory**: `/Users/victormanuel/discord-rpc/.agents/teamwork/reviewer_m7_2`  
**Verdict**: **REQUEST_CHANGES**

---

## Review Summary

**Verdict**: **REQUEST_CHANGES**  
**Overall Risk Assessment**: **CRITICAL**

While the implementations for `SingleInstanceController`, `NSStatusItem` context menu event handling, visible in-app quit controls, and LaunchAgent hardening are well-structured and pass extensive concurrency and crash-recovery tests, an **independent adversarial stress test discovered a fatal self-deadlock in `DiscordRPCManager` whenever a `RECONNECT` command is processed**. 

Furthermore, this defect was masked in upstream unit tests (`test_milestone7_lifecycle.py`) because tests only verified enqueuing the command with `auto_start=False` or used mock facades, constituting an integrity gap (self-certifying work without genuine execution).

---

## 1. Observation

### 1.1 Fatal Self-Deadlock on `RECONNECT` Command in `DiscordRPCManager`
- `discord_rpc_manager.py` lines 233:
  ```python
  self._lock: threading.Lock = threading.Lock()
  ```
  `self._lock` is a non-reentrant mutex (`threading.Lock`).
- `discord_rpc_manager.py` lines 383-387:
  ```python
  def _safe_close_rpc(self) -> None:
      with self._lock:
          rpc = self._rpc
          self._rpc = None
  ```
  `_safe_close_rpc()` explicitly acquires `self._lock`.
- `discord_rpc_manager.py` lines 589-594 (introduced in M7):
  ```python
  elif cmd == "RECONNECT":
      with self._lock:
          self._safe_close_rpc()
      if self.is_active:
          self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")
  ```
  `_process_command` acquires `self._lock` at line 590, and then calls `self._safe_close_rpc()` at line 591. Inside `_safe_close_rpc()`, the same thread attempts to acquire `self._lock` again at line 385.
- Verbatim Reproduction Command:
  ```bash
  /Users/victormanuel/discord-rpc/venv/bin/python -c '
  import threading
  from discord_rpc_manager import DiscordRPCManager

  mgr = DiscordRPCManager(client_id="test", auto_start=False)
  t = threading.Thread(target=mgr._process_command, args=("RECONNECT", None))
  t.start()
  t.join(timeout=1.0)
  assert not t.is_alive(), "Worker thread deadlocked on self._lock!"
  '
  ```
  Output:
  ```
  AssertionError: Worker thread deadlocked on self._lock!
  ```
  Worker thread stack trace when blocked:
  ```
    File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 428, in _worker_loop
      self._process_command(cmd, payload)
    File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 591, in _process_command
      self._safe_close_rpc()
    File "/Users/victormanuel/discord-rpc/discord_rpc_manager.py", line 385, in _safe_close_rpc
      with self._lock:
  ```

### 1.2 Upstream Inadequate Test Verification Masking the Deadlock
- `tests/test_milestone7_lifecycle.py` lines 224-232:
  ```python
  def test_discord_reconnect_command(self):
      """Verifies that calling rpc_manager.reconnect() enqueues ('RECONNECT', None)."""
      mgr = discord_rpc_manager.DiscordRPCManager(auto_start=False)
      self.assertTrue(hasattr(mgr, "reconnect"))
      mgr.reconnect()
      cmd, payload = mgr._cmd_queue.get_nowait()
      self.assertEqual(cmd, "RECONNECT")
      self.assertIsNone(payload)
  ```
  The test only verified that calling `reconnect()` pushed a tuple onto `_cmd_queue` while `auto_start=False`. It never executed `_process_command("RECONNECT", None)` or allowed the worker loop to dequeue the command.
- `tests/test_milestone7_lifecycle.py` lines 237-240 & 276-278:
  Tests for `onAppLaunched_` and `onSystemWake_` used `MockRPCManager`, completely bypassing actual execution of `reconnect()`.

### 1.3 Unhandled Non-Dict Script Message Body in `LoLWebBridge`
- `popover_ui.py` lines 138-142:
  ```python
  def userContentController_didReceiveScriptMessage_(self, ucc, message):
      body = message.body()
      if not body or not self._controller:
          return
      action = body.get("action")
  ```
  If `message.body()` is not a dict (e.g. string or number sent by script), `body.get("action")` raises `AttributeError: 'str' object has no attribute 'get'`.

### 1.4 SingleInstanceController Concurrency & Crash Recovery
- Tested 20 concurrent threads trying to acquire `SingleInstanceController` in a temporary directory:
  * Exactly 1 winner acquired the lock (`True`).
  * 19 losers received `False` and sent FOCUS signals.
  * Recovered cleanly from simulated abnormal crashes leaving a stale `app.sock` file.
  * Handled adversarial malformed inputs (`b"MALICIOUS_OVERFLOW" * 100`, null bytes, empty payloads) without server crash.

### 1.5 NSStatusItem Event Handling
- Tested rapid bursts of 50 left clicks, 50 right clicks, and 50 Control-clicks:
  * Properly distinguishes left click (toggles popover) from right click and Control-click (invokes `popUpStatusItemMenu_`).
  * Context menu items match R1 specifications: "Abrir Popover", "Pausar Presencia" / "Reanudar Presencia", "Configuración ⚙️", and "Salir de Discord RPC" (Cmd+Q).
  * Cleanup is safe and idempotent across 10 repeated invocations.

### 1.6 Hardened LaunchAgent Plist & Startup Notifications
- `_sync_login_item(True)` creates `~/Library/LaunchAgents/com.victormanuel.lolrpc.plist` executing direct bundle binary `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC` with `--silent`.
- Redirects stdout to `~/Library/Logs/lol_discord_rpc.log` and stderr to `lol_discord_rpc_error.log`.
- `app_gui.py` triggers an `osascript` notification even when launched with `--silent`.

### 1.7 Test Suite Execution Results
- `tests/run_tests.py`: 149/149 passed (100% across Tiers 1-5 in 16.88s).
- Full discovery `python -m unittest discover -s tests -p "test_*.py"`: 254/254 passed in 26.399s.
- `tests/test_adversarial_m7_challenger.py`: 12/12 passed in 2.724s.

---

## 2. Logic Chain

```
Observation 1.1: self._lock is non-reentrant threading.Lock(). _process_command acquires self._lock at line 590, and then calls self._safe_close_rpc() which also acquires self._lock at line 385.
       │
       ▼
Logic Step 1: The worker thread attempts recursive lock acquisition on a non-reentrant lock, entering an unrecoverable self-deadlock. The entire background RPC engine freezes permanently.
       │
Observation 1.2: test_discord_reconnect_command only tested _cmd_queue.put with auto_start=False; workspace listener tests mocked RPC manager.
       │
       ▼
Logic Step 2: The test suite appeared 100% green while concealing a fatal runtime freeze on the core feature of Requirement R4 (auto-reconnect on Discord launch and system wake).
       │
Observation 1.3: LoLWebBridge calls body.get("action") without checking isinstance(body, dict).
       │
       ▼
Logic Step 3: Non-dict script messages trigger uncaught AttributeError exceptions in the Cocoa bridge.
       │
Observation 1.4-1.6: SingleInstanceController, NSStatusItem right-click menu, in-app quit buttons, and LaunchAgent hardening work as intended and survived adversarial stress.
       │
       ▼
Conclusion: Due to Critical Finding 1 (Self-Deadlock), the work product must NOT be approved in its current state. Verdict: REQUEST_CHANGES.
```

---

## 3. Findings

### [Critical] Finding 1: Self-Deadlock on `RECONNECT` Command in `DiscordRPCManager`
- **What**: Recursive lock acquisition on non-reentrant mutex `self._lock` causing permanent deadlock.
- **Where**: `/Users/victormanuel/discord-rpc/discord_rpc_manager.py`, lines 589-594 and line 385.
- **Why**: As soon as Discord launches or the Mac wakes from sleep, `reconnect()` is dispatched. The worker thread hangs forever at line 385. Discord Rich Presence stops working, and app termination hangs for 2.5 seconds.
- **Suggestion**:
  Remove `with self._lock:` from around `self._safe_close_rpc()` in `_process_command`, since `_safe_close_rpc()` already acquires `self._lock` internally:
  ```python
  elif cmd == "RECONNECT":
      self._safe_close_rpc()
      with self._lock:
          active = self.is_active
      if active:
          self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")
  ```
  Alternatively, declare `self._lock = threading.RLock()`.
  Add a real regression test that starts the worker thread (or calls `_process_command`) and verifies that `RECONNECT` completes without deadlocking.

### [Major] Finding 2: Unhandled Non-Dict WebKit Script Message in `LoLWebBridge`
- **What**: `AttributeError: 'str' object has no attribute 'get'` when WebKit delivers non-dict script messages.
- **Where**: `/Users/victormanuel/discord-rpc/popover_ui.py`, lines 138-142.
- **Why**: Lacks `isinstance(body, dict)` guard before calling `.get("action")`.
- **Suggestion**:
  ```python
  def userContentController_didReceiveScriptMessage_(self, ucc, message):
      body = message.body()
      if not body or not isinstance(body, dict) or not self._controller:
          return
      action = body.get("action")
  ```

### [Minor] Finding 3: Race Condition on Unix Domain Socket Connection During High-Concurrency Launches
- **What**: Secondary instances receiving `Connection refused` when connecting to `app.sock` before primary's listener thread has finished binding.
- **Where**: `/Users/victormanuel/discord-rpc/app_gui.py`, lines 147-162.
- **Why**: `_notify_running_instance()` performs a single connect attempt without retry.
- **Suggestion**: Add a brief 2-attempt retry loop with 50ms sleep before falling back to `NSRunningApplication`.

---

## 4. Caveats

- In headless CI environments without an active WindowServer, Cocoa `popUpStatusItemMenu_` requires a mock status item button or GUI session.
- System wake notifications (`NSWorkspaceDidWakeNotification`) require hardware power state events or simulated Cocoa notifications.

---

## 5. Conclusion

**Verdict**: **REQUEST_CHANGES**

Milestone M7 successfully implements the architecture for single-instance control, menubar context menus, in-app quit buttons, and LaunchAgent hardening. However, **Finding 1 is a blocker-level defect**: calling `rpc_manager.reconnect()` upon Discord launch or system wake immediately deadlocks the background thread due to recursive mutex acquisition on `self._lock`.

Worker must:
1. Fix the deadlock in `discord_rpc_manager.py` (lines 589-594).
2. Add `isinstance(body, dict)` validation in `popover_ui.py` (line 140).
3. Add an end-to-end unit test that executes `_process_command("RECONNECT", None)` on an active thread to guarantee no deadlock occurs.
4. Resynchronize the bundle `/Applications/League of Legends RPC.app` via `sync_bundle.py`.

---

## 6. Verification Method

To verify the deadlock and subsequent fix:

1. **Deadlock Reproduction Test**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -c '
   import threading
   from discord_rpc_manager import DiscordRPCManager

   mgr = DiscordRPCManager(client_id="test", auto_start=False)
   t = threading.Thread(target=mgr._process_command, args=("RECONNECT", None))
   t.start()
   t.join(timeout=1.0)
   assert not t.is_alive(), "Worker thread deadlocked on self._lock in _safe_close_rpc()!"
   print("SUCCESS: RECONNECT processed without deadlock!")
   '
   ```

2. **Master Test Suites**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover -s tests -p "test_*.py"
   ```

3. **Invalidation Conditions**:
   - `t.is_alive()` is True after 1.0s in the deadlock reproduction script.
   - Any test failure in test suites.
