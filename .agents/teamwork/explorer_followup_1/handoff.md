# Architectural Survey & Investigation Report: Requirements R1 & R4

**Agent**: `explorer_followup_1`  
**Date**: 2026-09-29T23:17:30Z  
**Target Milestone**: follow-up requirements R1 & R4 (`ORIGINAL_REQUEST.md` Follow-up 2026-09-29T23:10:58Z)  
**Status**: COMPLETE (Hard Handoff)

---

## 1. Observation

### 1.1 Status Bar Click Interception & Native Context Menu (R1)
- **Current Click Interception (`status_item.py:91-95, 136-148`)**:
  ```python
  self._button = self._status_item.button()
  if self._button is not None:
      self._button.setTarget_(self)
      self._button.setAction_(b"statusItemButtonClicked:")
  ```
  `statusItemButtonClicked_(self, sender)` is currently invoked only for standard mouse clicks. In AppKit, `NSStatusBarButton` defaults to an event mask of `NSEventMaskLeftMouseUp` (mask value `4`).
- **Right-Click Interception Verification**:
  Using PyObjC, executing `btn.sendActionOn_(AppKit.NSEventMaskLeftMouseUp | AppKit.NSEventMaskRightMouseUp)` configures the button to trigger `statusItemButtonClicked:` on both left and right mouse up events.
- **Event Differentiation**:
  In `statusItemButtonClicked:`, querying `event = AppKit.NSApp.currentEvent()` yields:
  - `event.type() == AppKit.NSEventTypeRightMouseUp` (value `4`) or `AppKit.NSEventTypeRightMouseDown` (value `3`).
  - Control-click (macOS standard secondary click): `bool(event.modifierFlags() & AppKit.NSEventModifierFlagControl)` (flag `262144`).
- **Cocoa Context Menu Presentation**:
  `AppKit.NSStatusItem` natively exposes `popUpStatusItemMenu_(menu: AppKit.NSMenu)`. Verified via terminal PyObjC execution that `hasattr(item, "popUpStatusItemMenu_") == True` and it renders without permanently assigning `item.setMenu_(menu)` (which would otherwise suppress standard left-click popover actions).
- **Target Menu Items**:
  The menu requires 4 primary items:
  1. *Open Popover* (`"Abrir Popover"` / `"Open Popover"`) -> toggles/opens `NSPopover`.
  2. *Toggle Presence (Pause/Resume)* (`"Pausar Presencia"` / `"Reanudar Presencia"`) -> non-blocking call to `rpc_manager.set_active(...)`.
  3. *Settings (⚙️)* (`"Configuración ⚙️"` / `"Settings ⚙️"`) -> switches to `#view-config` and presents popover.
  4. *Quit (Cmd+Q)* (`"Salir de Discord RPC"` / `"Quit"`) -> selector `terminate:` or `controller.quit()` with key equivalent `"q"`.

### 1.2 User-Facing "Salir de la aplicación" (Quit App) Controls (R1)
- **Popover Views Inspection (`liquid_html.py:860-942`)**:
  - `#view-main` (lines 862-867): Contains only the action button `<div class="action-btn" id="btn-action">...</div>`. No application termination control exists.
  - `#view-config` (lines 870-941): Contains only the back button and `<button class="save-config-btn" onclick="saveConfig()">`. No application termination control exists.
- **Web Bridge Inspection (`popover_ui.py:138-170`)**:
  `LoLWebBridge.userContentController_didReceiveScriptMessage_` routes actions `select_mode`, `toggle_autoreset`, `toggle_autorun`, `action_button`, `toggle_settings`, `close_settings`, `save_config`, `change_champion`, `change_rank`, `change_division`, `change_game_mode`. No handler exists for an action such as `quit_app`.
- **Termination Pathway (`app_gui.py:188-216`)**:
  `LoLAppController.quit()` already exists and cleanly tears down `popover.close()`, `status_item.cleanup()`, `rpc_manager.shutdown()`, and calls `NSApplication.sharedApplication().terminate_(None)`.

### 1.3 Single-Instance Lock Mechanism (R1)
- **Reopen Handler (`app_gui.py:254-263`)**:
  `LoLAppDelegate.applicationShouldHandleReopen_hasVisibleWindows_` is implemented and triggers `self.controller.popover.toggle(btn)` when macOS LaunchServices (`open -a`) reopens an already-running `.app` bundle.
- **Direct CLI Execution Gap (`app_gui.py:317-340`)**:
  `main()` directly creates `NSApplication`, instantiates `LoLAppDelegate`, and enters `AppHelper.runEventLoop()`. If executed from CLI (`/Applications/.../Contents/MacOS/League of Legends RPC` or `python app_gui.py`), a duplicate process runs, registers an extra status bar item, creates conflicting writes to `~/.config/lol_discord_rpc/config.json`, and triggers socket collisions with Discord's IPC socket.
- **Socket / Lock Verification**:
  Verified via Python execution that a Unix Domain Socket at `~/.config/lol_discord_rpc/app.sock` paired with non-blocking `fcntl.flock` on `app.lock` allows a second process to send `b"FOCUS\n"` to the primary process and immediately terminate (`exit 0`). The primary process receives the message and executes `AppHelper.callAfter(controller.focus_popover)` to bring the UI to the front. Stale socket handling (`ConnectionRefusedError`, `OSError: [Errno 38] Socket operation on non-socket`) safely recovers if an earlier instance was terminated abnormally.

### 1.4 macOS Auto-Start Hardening (LaunchAgent) (R1)
- **Current LaunchAgent Configuration (`popover_ui.py:1257-1277`)**:
  ```xml
  <key>ProgramArguments</key>
  <array>
      <string>/usr/bin/open</string>
      <string>-a</string>
      <string>/Applications/League of Legends RPC.app</string>
      <string>--args</string>
      <string>--silent</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>ProcessType</key>
  <string>Interactive</string>
  ```
- **Direct Binary Launcher (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`)**:
  Lines 35-36:
  ```bash
  export TK_SILENCE_DEPRECATION=1
  exec "$PYTHON_BIN" "$RESOURCES/app_gui.py" "$@"
  ```
  The bundle binary directly replaces the shell with Python and passes all CLI arguments (`"$@"`).
- **Log Redirection**:
  The current plist omits `StandardOutPath` and `StandardErrorPath`. `launchd` requires absolute paths for log files (it does not expand `~`).
- **Launch Notification Gap (`app_gui.py:231-243`)**:
  ```python
  is_silent = "--silent" in sys.argv or "--background" in sys.argv
  if not is_silent:
      AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
          0.6, self, b"autoShowPopoverOnLaunch:", None, False
      )
      try:
          subprocess.Popen([
              "osascript", "-e",
              'display notification "Haz clic en el icono de Discord en la barra superior para abrir el menú." with title "League of Legends RPC" subtitle "Iniciado en la barra de menús"'
          ])
      except Exception:
          pass
  ```
  When launched by LaunchAgent with `--silent`, the notification is completely suppressed. The requirement dictates: *"Display a brief system notification upon launch confirming active menubar presence."*

### 1.5 System Event Listeners (Discord Launch & Wake from Sleep) (R4)
- **NSWorkspace Notification Center**:
  Verified in AppKit: `AppKit.NSWorkspace.sharedWorkspace().notificationCenter()`.
  Exposes:
  - `AppKit.NSWorkspaceDidLaunchApplicationNotification`
  - `AppKit.NSWorkspaceDidWakeNotification`
- **Discord Launch Detection**:
  In `NSWorkspaceDidLaunchApplicationNotification`, `notification.userInfo()["NSWorkspaceApplicationKey"]` provides an `NSRunningApplication`.
  Verified running Discord instance on macOS: `bundleIdentifier == "com.hnc.Discord"`, `localizedName == "Discord"`.
- **Discord Reconnection Latency (`discord_rpc_manager.py:418-436`)**:
  During backoff, the background worker thread performs:
  `cmd, payload = self._cmd_queue.get(timeout=3.5)`
  Calling `rpc_manager.reconnect()` by enqueueing `("RECONNECT", None)` immediately breaks the 3.5s sleep, resets `self._rpc = None`, closes stale pipes, and triggers an immediate `Presence.connect()`.

### 1.6 In-App Error Boundary Toast (R4)
- **WebKit Frontend Injection (`liquid_html.py:121-145, 949-958`)**:
  Currently, `liquid_html.py` lacks a dedicated toast container, CSS toast animations, and global JavaScript error listeners (`window.addEventListener('error')`, `window.addEventListener('unhandledrejection')`).
- **JavaScript Evaluation (`popover_ui.py:894-898`)**:
  `LoLPopoverController` already possesses `self._web_view.evaluateJavaScript_completionHandler_(...)`. A helper `show_toast(message: str, type: str = "error")` can inject toast events directly into the DOM.
- **Backend Error Routing (`app_gui.py:151-171`)**:
  When `DiscordRPCManager` dispatches `on_rpc_state_change(state, message)` with an error condition, or when unhandled socket exceptions occur, the error message can be delivered to `popover.show_toast(...)`.

### 1.7 Current Test Suite Baseline
- Command: `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
  Result: 149 / 149 tests passed cleanly across Tiers 1–5 in 16.248s.
- Command: `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover -s tests -p "test_*.py"`
  Result: 241 / 241 tests passed cleanly in 20.758s.

---

## 2. Logic Chain

```
Observation 1.1: NSStatusBarButton only fires for left click by default;
popUpStatusItemMenu_ provides native Cocoa context menu without breaking popover toggle.
       │
       ▼
Logic Step 1: Call sendActionOn_(LeftMouseUp | RightMouseUp). In statusItemButtonClicked_,
inspect currentEvent() for RightMouseUp / Control-click. If right-click, pop up NSMenu;
if left-click, toggle NSPopover.
       │
Observation 1.2: No Quit button in popover UI or WebBridge.
       │
       ▼
Logic Step 2: Add "Salir de la aplicación" in both #view-main and #view-config in liquid_html.py,
wire sendAction('quit_app') to LoLWebBridge, and call LoLAppController.quit().
       │
Observation 1.3: Direct execution spawns duplicate processes with duplicate status items.
       │
       ▼
Logic Step 3: Implement SingleInstanceLock in app_gui.py using a Unix domain socket
(~/.config/lol_discord_rpc/app.sock) and flock. Secondary instances send "FOCUS" and exit 0.
Primary instance activates NSApp and displays popover.
       │
Observation 1.4: LaunchAgent uses /usr/bin/open, lacks log paths, and suppresses launch notification.
       │
       ▼
Logic Step 4: Update LaunchAgent plist to target the bundle binary directly, configure
StandardOutPath and StandardErrorPath in ~/Library/Logs/, and show system notification on launch.
       │
Observation 1.5: NSWorkspaceDidLaunchApplicationNotification & NSWorkspaceDidWakeNotification.
       │
       ▼
Logic Step 5: Register NSWorkspace notification observers on LoLAppController. When Discord starts
or Mac wakes, send immediate ("RECONNECT", None) command to DiscordRPCManager.
       │
Observation 1.6: No toast UI in WebKit; JS or socket exceptions fail silently.
       │
       ▼
Logic Step 6: Embed toast container and CSS into liquid_html.py with JS showToast() function,
add window error boundary, and expose show_toast() in popover_ui.py for backend socket errors.
```

---

## 3. Caveats

1. **LaunchAgent Test Suite Assertions**:
   - `tests/test_audit_fixes.py` line 257 checks:
     `self.assertIn("<string>--args</string>", source)`
   - `tests/test_challenger_audit_2.py` lines 374-377 checks:
     `self.assertIn("/usr/bin/open", args)`, `self.assertIn("--args", args)`.
   *Impact*: Modifying the plist generator to use direct binary execution (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`) will fail these specific legacy assertions unless:
     a) The plist retains backwards-compatible aliases or comments, OR
     b) The test files are updated to reflect the new requirements in R1.
2. **Launchd Path Expansion**:
   `launchd` does NOT expand `~` in `StandardOutPath` or `StandardErrorPath`. The generator must evaluate `os.path.expanduser("~/Library/Logs/com.victormanuel.lolrpc.log")` at plist generation time.
3. **Control-Click vs Right-Click**:
   Some macOS users rely on Trackpad secondary clicks or Ctrl+Click. Both `NSEventTypeRightMouseUp` and `event.modifierFlags() & AppKit.NSEventModifierFlagControl` must be checked.
4. **App Bundle Synchronization**:
   If a new module is created (e.g., `launch_agent.py`), it must be registered in `RUNTIME_MODULES` in both `sync_bundle.py` and `build_dmg.py` so that DMG builds and bundle installations include it.
5. **Discord Client Variations**:
   Discord can run as Discord Stable (`com.hnc.Discord`), Discord PTB (`com.hnc.DiscordPTB`), or Discord Canary (`com.hnc.DiscordCanary`). The bundle identifier check should match `bundle_id.startswith("com.hnc.discord")` or `"discord" in app_name.lower()`.

---

## 4. Conclusion & Actionable Implementation Plan

### 4.1 Requirement R1 Implementation Blueprint

#### A. Status Item Right-Click Context Menu (`status_item.py` & `app_gui.py`)
1. In `status_item.py:LoLStatusItemController._init_status_item()`:
   ```python
   self._button.sendActionOn_(
       AppKit.NSEventMaskLeftMouseUp | AppKit.NSEventMaskRightMouseUp
   )
   ```
2. Implement `build_context_menu()` on `LoLStatusItemController`:
   - Title: "StatusItemContextMenu"
   - Items:
     * `"Abrir Popover"` -> target action `menuOpenPopover:`
     * `"Pausar Presencia"` / `"Reanudar Presencia"` (dynamically labeled based on `self._current_state`) -> target action `menuTogglePresence:`
     * `"Configuración ⚙️"` -> target action `menuOpenSettings:`
     * Separator
     * `"Salir de Discord RPC"` (`keyEquivalent="q"`) -> target action `menuQuit:`
3. In `statusItemButtonClicked_(self, sender)`:
   ```python
   event = AppKit.NSApp.currentEvent()
   is_right = False
   if event is not None:
       etype = event.type()
       if etype in (AppKit.NSEventTypeRightMouseUp, AppKit.NSEventTypeRightMouseDown):
           is_right = True
       elif bool(event.modifierFlags() & AppKit.NSEventModifierFlagControl):
           is_right = True

   if is_right:
       menu = self.build_context_menu()
       self._status_item.popUpStatusItemMenu_(menu)
   else:
       # Normal toggle
       self._trigger_toggle(sender)
   ```

#### B. Popover "Salir de la aplicación" Controls (`liquid_html.py` & `popover_ui.py`)
1. In `liquid_html.py`:
   - Bottom of `#view-main` (below `#btn-action`):
     ```html
     <div class="quit-container">
       <button class="quit-btn-subtle" onclick="sendAction('quit_app')">
         Salir de la aplicación <span class="kbd-shortcut">⌘Q</span>
       </button>
     </div>
     ```
   - Bottom of `#view-config` (below `.save-config-btn`):
     ```html
     <div class="quit-container config-quit-container">
       <button class="quit-btn-danger" onclick="sendAction('quit_app')">
         ✕ Salir de la aplicación
       </button>
     </div>
     ```
2. In `popover_ui.py:LoLWebBridge`:
   ```python
   elif action == "quit_app":
       self._controller.quit_app()
   ```
3. In `LoLPopoverController`:
   ```python
   def quit_app(self):
       if callable(self._on_quit):
           self._on_quit()
       else:
           app = AppKit.NSApplication.sharedApplication()
           if app:
               app.terminate_(None)
   ```

#### C. Single-Instance Lock Mechanism (`app_gui.py`)
1. Create `SingleInstanceController`:
   - Socket path: `os.path.expanduser("~/.config/lol_discord_rpc/app.sock")`
   - Lock file: `os.path.expanduser("~/.config/lol_discord_rpc/app.lock")`
   - In `check_and_acquire()`:
     Attempt non-blocking connect to `app.sock`. If successful: send `b"FOCUS\n"`, read response, activate running instance via `NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.victormanuel.lolrpc")`, and call `sys.exit(0)`.
     If connection refused or file missing: clean stale socket, acquire `fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)`, bind `app.sock`, listen on daemon thread.
   - When `b"FOCUS\n"` is received: execute `AppHelper.callAfter(controller.focus_popover)`.
   - On shutdown: unlink `app.sock` and release lock.

#### D. Hardened Auto-Start & LaunchAgent (`launch_agent.py` & `popover_ui.py`)
1. Dedicated `launch_agent.py`:
   - Bundle binary path: `"/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC"`
   - `StandardOutPath`: `os.path.expanduser("~/Library/Logs/com.victormanuel.lolrpc.log")`
   - `StandardErrorPath`: `os.path.expanduser("~/Library/Logs/com.victormanuel.lolrpc.error.log")`
   - Plist template:
     ```xml
     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
     <plist version="1.0">
     <dict>
         <key>Label</key>
         <string>com.victormanuel.lolrpc</string>
         <key>ProgramArguments</key>
         <array>
             <string>/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC</string>
             <string>--silent</string>
         </array>
         <key>RunAtLoad</key>
         <true/>
         <key>ProcessType</key>
         <string>Interactive</string>
         <key>StandardOutPath</key>
         <string>{stdout_path}</string>
         <key>StandardErrorPath</key>
         <string>{stderr_path}</string>
     </dict>
     </plist>
     ```
2. In `app_gui.py:applicationDidFinishLaunching_`:
   Always display a brief system notification upon launch (interactive or silent):
   ```python
   subtitle = "Ejecutándose en la barra de menús" if is_silent else "Iniciado en la barra de menús"
   subprocess.Popen([
       "osascript", "-e",
       f'display notification "Haz clic en el icono de Discord en la barra superior para abrir el menú." with title "League of Legends RPC" subtitle "{subtitle}"'
   ])
   ```

---

### 4.2 Requirement R4 Implementation Blueprint

#### A. System Event Listeners (`app_gui.py` & `discord_rpc_manager.py`)
1. In `app_gui.py:LoLAppController`:
   Register observers on `AppKit.NSWorkspace.sharedWorkspace().notificationCenter()`:
   - `NSWorkspaceDidLaunchApplicationNotification` -> `on_app_launched_(notification)`
   - `NSWorkspaceDidWakeNotification` -> `on_system_wake_(notification)`
2. Observer callbacks:
   ```python
   def on_app_launched_(self, notification):
       user_info = notification.userInfo()
       if not user_info:
           return
       app = user_info.get("NSWorkspaceApplicationKey")
       if not app:
           return
       bundle_id = (app.bundleIdentifier() or "").lower()
       name = (app.localizedName() or "").lower()
       if "discord" in bundle_id or "discord" in name:
           logger.info("Discord launch detected (%s). Triggering immediate RPC reconnect...", name)
           if self.rpc_manager:
               self.rpc_manager.reconnect()

   def on_system_wake_(self, notification):
       logger.info("System wake detected. Re-establishing Discord IPC socket...")
       if self.rpc_manager:
           self.rpc_manager.reconnect()
   ```
3. In `discord_rpc_manager.py`:
   Add public non-blocking method:
   ```python
   def reconnect(self) -> None:
       """Forces an immediate reconnection attempt, interrupting backoff sleep."""
       self._cmd_queue.put(("RECONNECT", None))
   ```
   In `_process_command`:
   ```python
   elif cmd == "RECONNECT":
       self._safe_close_rpc()
       if self.is_active:
           self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")
   ```

#### B. In-App Error Boundary Toast (`liquid_html.py` & `popover_ui.py`)
1. In `liquid_html.py`:
   - Inject `<div id="toast-container" class="toast-container"></div>` into HTML.
   - Inject CSS for `.toast-container`, `.toast`, `.toast-error`, `.toast-warning`, `.toast-info` with smooth opacity and translateY transitions.
   - Inject JS:
     ```javascript
     function showToast(message, type = 'error', duration = 3500) {
       const container = document.getElementById('toast-container');
       if (!container) return;
       const toast = document.createElement('div');
       toast.className = `toast toast-${type}`;
       const icon = type === 'error' ? '⚠️' : (type === 'warning' ? '⚡' : 'ℹ️');
       toast.innerHTML = `<span class="toast-icon">${icon}</span><span class="toast-msg">${escapeHtml(message)}</span>`;
       container.appendChild(toast);
       requestAnimationFrame(() => toast.classList.add('show'));
       setTimeout(() => {
         toast.classList.remove('show');
         setTimeout(() => toast.remove(), 400);
       }, duration);
     }

     window.addEventListener('error', (e) => {
       showToast(e.message || "Error en interfaz gráfica", "error");
     });
     window.addEventListener('unhandledrejection', (e) => {
       showToast(e.reason?.message || "Error en operación asíncrona", "error");
     });
     ```
2. In `popover_ui.py:LoLPopoverController`:
   ```python
   def show_toast(self, message: str, toast_type: str = "error") -> None:
       """Renders an animated toast notification inside the WebKit Liquid Glass UI."""
       if getattr(self, "_web_view", None):
           js = f"if (window.showToast) {{ window.showToast({json.dumps(message)}, {json.dumps(toast_type)}); }}"
           try:
               self._web_view.evaluateJavaScript_completionHandler_(js, None)
           except Exception:
               pass
   ```
3. In `app_gui.py`:
   Route socket errors to popover toast:
   ```python
   def on_rpc_state_change(self, state: str, message: str) -> None:
       ...
       if self.popover and ("error" in state.lower() or "error" in message.lower() or "perdida" in message.lower()):
           self.popover.show_toast(message, "error")
   ```

---

## 5. Verification Method

### Automated Test Execution
Run the complete suite to verify zero regressions:
```bash
/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
/Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

### Specific Component Verification Steps
1. **Status Item Right-Click**:
   - Inspect `status_item.py`: verify `sendActionOn_` contains `NSEventMaskRightMouseUp`.
   - Verify `popUpStatusItemMenu_` is invoked when `NSEventTypeRightMouseUp` is detected.
   - Run unit test asserting `LoLStatusItemController.build_context_menu()` returns an `NSMenu` with 4 items: Open Popover, Toggle Presence, Settings, and Quit.
2. **Single-Instance Enforcement**:
   - Launch primary instance in background.
   - Launch secondary instance via CLI: verify secondary exits with status `0` in `<0.5s` and primary instance receives `FOCUS`.
   - Test abnormal exit recovery: write empty `app.sock`, launch instance, verify `ConnectionRefusedError`/`OSError` is handled and server starts.
3. **LaunchAgent Verification**:
   - Inspect `~/Library/LaunchAgents/com.victormanuel.lolrpc.plist`:
     * `ProgramArguments` contains `/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`.
     * `StandardOutPath` points to `/Users/victormanuel/Library/Logs/com.victormanuel.lolrpc.log`.
     * `StandardErrorPath` points to `/Users/victormanuel/Library/Logs/com.victormanuel.lolrpc.error.log`.
4. **NSWorkspace Notifications**:
   - Register observer, simulate `NSWorkspaceDidLaunchApplicationNotification` with mock `NSRunningApplication("com.hnc.Discord")`.
   - Verify `DiscordRPCManager.reconnect()` is invoked without blocking.
5. **In-App Toast**:
   - Call `controller.popover.show_toast("Prueba de error de socket", "error")`.
   - Verify JavaScript evaluates `showToast(...)` and renders `.toast.toast-error`.

### Invalidation Conditions
- If `sendActionOn_` overrides standard left click toggle behavior.
- If `launchd` fails to load plist due to unexpanded `~` in log paths.
- If secondary instances spawn duplicate status bar items or background worker threads.
- If unhandled JavaScript errors in WebKit crash the Cocoa runloop.
