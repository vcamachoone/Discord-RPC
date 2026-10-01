# Handoff Report — Requirements R1 (UI Quit Controls) & R2 (Discord Interactive Profile Buttons)

## 1. Observation

### 1.1 Existing Application Quit Architecture
- **In `app_gui.py`**:
  * `LoLAppController.quit(self)` (lines 188–216) handles full graceful teardown:
    ```python
    def quit(self) -> None:
        """Clean shutdown of UI and background workers."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        logger.info("Initiating graceful shutdown...")
        if self.popover:
            try: self.popover.close()
            except Exception: pass
        if self.status_item:
            try: self.status_item.cleanup()
            except Exception: pass
        if self.rpc_manager:
            try: self.rpc_manager.shutdown()
            except Exception: pass
        app = AppKit.NSApplication.sharedApplication()
        if app and app.isRunning():
            app.terminate_(None)
    ```
  * `setup_main_menu(app)` (lines 279–293) adds a standard Cocoa menu item with "Quit League of Legends RPC" (Cmd+Q).
  * However, the application activation policy is `NSApplicationActivationPolicyAccessory` (line 321), which hides the app from the macOS Dock. Users without an active window or menu bar shortcut knowledge cannot discover or trigger Cmd+Q easily.
- **In `popover_ui.py`**:
  * `LoLWebBridge` (lines 129–170) receives script messages from WebKit via `userContentController_didReceiveScriptMessage_`:
    Supported actions: `"select_mode"`, `"toggle_autoreset"`, `"toggle_autorun"`, `"action_button"`, `"toggle_settings"`, `"close_settings"`, `"save_config"`, `"change_champion"`, `"change_rank"`, `"change_division"`, `"change_game_mode"`.
    **Verbatim absence**: There is no handler for action `"quit_app"` or `"quit"`.
  * `LoLPopoverController` (lines 172–1623) currently has no method `quit_application()` and does not accept or store an `on_quit` callback.
- **In `liquid_html.py`**:
  * `#view-main` (lines 721–867) contains header, mode cards, settings panel, switches, and `.action-btn` ("DETENER EN DISCORD" / "INICIAR PRESENCIA"). It does not contain any quit button or exit link.
  * `#view-config` (lines 870–941) contains preset selector, Client ID input, details input, duration select, and save button. It does not contain any quit control.

### 1.2 Existing Discord RPC & pypresence Button Architecture
- **In `pypresence` library (`venv/lib/python3.9/site-packages/pypresence/payloads.py`)**:
  * `Payload.set_activity` signature:
    ```python
    @classmethod
    def set_activity(
        cls,
        pid: int = os.getpid(),
        ...,
        buttons: list | None = None,
        instance: bool = True,
        activity: bool | None = True,
        _rn: bool = True,
    ):
    ```
  * Inside `set_activity`, `act_details["buttons"] = buttons`.
  * In `Payload.__init__`:
    ```python
    if clear_none:
        data = remove_none(data)
    ```
  * **Critical behavioral observation verified via Python interpreter**:
    - When `buttons=[{"label": "OP.GG", "url": "https://op.gg"}]`:
      Resulting payload contains `"buttons": [{"label": "OP.GG", "url": "https://op.gg"}]`.
    - When `buttons=None`:
      `remove_none` deletes the `"buttons"` key completely from `"activity"`.
    - When `buttons=[]`:
      Resulting payload contains `"buttons": []`.
    - Conclusion: If no valid buttons exist, passing `buttons=None` or omitting `"buttons"` from `rpc.update()` is necessary to avoid sending empty lists to Discord Gateway IPC.
- **In `discord_rpc_manager.py`**:
  * Line 166:
    ```python
    ALLOWED_CONFIG_KEYS = {
        "mode",
        "champion_name",
        "champion_image_url",
        "rank_text",
        "rank_image_url",
        "game_mode",
        "details",
        "autoreset",
    }
    ```
    `"buttons"` is currently NOT in `ALLOWED_CONFIG_KEYS`. Any update dispatched to `update_presence_config(buttons=...)` is silently dropped by line 567:
    `if k in ALLOWED_CONFIG_KEYS and hasattr(self, k):`
  * In `_send_rpc_update` (lines 586–651):
    Calls `rpc.update(...)` for `lol` mode and other game presets. It does not pass any `buttons` argument.
- **In `tests/run_tests.py`**:
  * Full test suite runs 149 tests across 5 tiers:
    Results: 149 passed, 0 skipped, 0 failed.

---

## 2. Logic Chain

### 2.1 UI Quit Control Logic Flow (Requirement R1)
1. **Trigger Points**:
   - In `#view-main`: A dedicated secondary action row below `.action-btn` styled with a subtle power icon and label "Salir de la aplicación".
   - In `#view-config`: A distinct red-accented danger button below the "Guardar" button: "🚪 Salir de la aplicación".
2. **Bridge Messaging**:
   - Both buttons call `sendAction('quit_app')`.
   - `window.webkit.messageHandlers.lolrpc.postMessage({ action: 'quit_app' })` transmits the message to Cocoa WebKit bridge.
3. **Dispatch & Teardown**:
   - `LoLWebBridge.userContentController_didReceiveScriptMessage_` receives `{ "action": "quit_app" }`.
   - The bridge invokes `self._controller.quit_application()`.
   - `LoLPopoverController.quit_application()` delegates to `self._on_quit()` (registered by `LoLAppController`).
   - If `self._on_quit` is not set (e.g. standalone test), it falls back to `AppKit.NSApplication.sharedApplication().terminate_(None)`.
   - `LoLAppController.quit()` closes the popover, cleans up `NSStatusItem`, shuts down `DiscordRPCManager` background thread and asyncio loop, and terminates `NSApplication`.
4. **Layout Height Adjustments**:
   - Popover height in `_update_layout`:
     * `#view-main` Official mode: 370px (fits cards + switches + action btn + quit btn).
     * `#view-main` Detailed mode: 600px.
     * `#view-config`: 620px, with `.view-panel#view-config` configured with `overflow-y: auto` to prevent vertical clipping on smaller displays.

### 2.2 Discord Interactive Profile Buttons Logic Flow (Requirement R2)
1. **Discord Rich Presence Constraints**:
   - Discord Rich Presence allows a maximum of 2 buttons.
   - Each button must be an object with `"label"` and `"url"`.
   - `"label"` must be 1–32 characters in length (non-empty string).
   - `"url"` must be 1–512 characters and **MUST** start with `https://`. (Discord IPC rejects or drops presence with non-HTTPS URLs).
2. **Configuration UI in `#view-config`**:
   - Two input pairs added in `#view-config`:
     * Button 1: `#config-btn1-label` (maxlength 32) and `#config-btn1-url` (maxlength 512, monospace).
     * Button 2: `#config-btn2-label` (maxlength 32) and `#config-btn2-url` (maxlength 512, monospace).
   - Instant client-side validation in `saveConfig()`:
     * If user enters `op.gg` or `twitch.tv/abc`, automatically prefix with `https://`.
     * If user enters `http://`, upgrade to `https://`.
     * If label is provided but URL is empty, or URL is provided but label is empty, discard that button cleanly and display a helpful feedback message.
3. **Serialization & WebKit Bridge**:
   - In `liquid_html.py:saveConfig()`:
     Extracts valid buttons into a clean array:
     ```javascript
     const buttons = [];
     if (b1_label && b1_url) buttons.push({ label: b1_label, url: b1_url });
     if (b2_label && b2_url) buttons.push({ label: b2_label, url: b2_url });
     sendAction('save_config', {
       game_id: gameId,
       client_id: clientId,
       details: details,
       duration_min: durationMin,
       buttons: buttons
     });
     ```
   - In `LoLWebBridge`:
     Passes `buttons=body.get("buttons", [])` to `LoLPopoverController.apply_config(...)`.
4. **Persistence in `~/.config/lol_discord_rpc/config.json`**:
   - `apply_config` saves `"buttons": self._buttons` in the config dictionary passed to `save_user_config(cfg)`.
   - On startup, `load_user_config()` loads `"buttons"` into both `LoLPopoverController` and `DiscordRPCManager`.
5. **Sanitization & Actor Worker Processing**:
   - Add `"buttons"` to `ALLOWED_CONFIG_KEYS` in `discord_rpc_manager.py`.
   - Implement `sanitize_buttons(raw_buttons: Any) -> Optional[List[Dict[str, str]]]`:
     * Validates type is list/tuple.
     * Enforces `len <= 2`.
     * Drops items without both valid label and valid URL.
     * Truncates label to 32 chars.
     * Validates/normalizes HTTPS URL and length <= 512 chars.
     * Returns `None` if list is empty (so `rpc.update()` does not send empty array).
   - In `_send_rpc_update()`:
     ```python
     valid_buttons = sanitize_buttons(self.buttons)
     if valid_buttons:
         kwargs["buttons"] = valid_buttons
     ```
     Applies to both `oficial` and `detallado` modes in LoL as well as other game presets.

---

## 3. Caveats

1. **Local Discord Client Self-Click Restriction**:
   - By Discord's intentional protocol design, the local user running Discord Rich Presence cannot click their own buttons when viewing their own profile in the desktop client (Discord displays them as disabled/preview-only for self). Other users viewing the profile see fully interactive, clickable buttons that open the browser. This is normal Discord behavior and not a bug.
2. **WebKit Availability Fallback**:
   - If WebKit is unavailable (`HAS_WEBKIT = False`), native Cocoa controls in `popover_ui.py` (`_content_view`) are displayed. The native fallback should also include an accessible "Salir de la aplicación" button or menu item, and `quit_application()` must function uniformly.
3. **Backwards Compatibility of Signatures**:
   - `LoLPopoverController.apply_config` must maintain backwards compatibility:
     `def apply_config(self, game_id: str, client_id: str, details: str, duration_min: int = 25, buttons: Optional[List[Dict[str, str]]] = None) -> None:`
     Existing tests call `apply_config` with 4 arguments; adding `buttons=None` as optional prevents test breakages.
4. **Adversarial / Attribute Injection Protection**:
   - Tests in `test_adversarial_stress.py` and `test_challenger_audit.py` probe `ALLOWED_CONFIG_KEYS`. Only the exact key `"buttons"` should be added.

---

## 4. Conclusion & Concrete Implementation Blueprint

### 4.1 Changes in `liquid_html.py`
1. **Add CSS styles**:
   - `.quit-row`, `.quit-btn`, `.quit-app-btn` with hover transition, red accent (`#EF4444`), and flex centering.
   - `.buttons-config-group`, `.btn-config-card`, `.btn-fields-grid` with input styling.
   - `.view-panel#view-config` with `overflow-y: auto; max-height: 520px; padding-right: 4px;`.
2. **Add HTML in `#view-main`**:
   - Below `.action-btn`:
     ```html
     <div class="quit-row">
       <button class="quit-btn" onclick="sendAction('quit_app')" title="Salir completamente de la aplicación">
         <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
           <path d="M18.36 6.64a9 9 0 1 1-12.73 0"></path>
           <line x1="12" y1="2" x2="12" y2="12"></line>
         </svg>
         <span>Salir de la aplicación</span>
       </button>
     </div>
     ```
3. **Add HTML in `#view-config`**:
   - Interactive Profile Buttons section with 2 card inputs (Label & URL for Button 1 and Button 2).
   - Danger Quit button below Save button:
     ```html
     <button class="quit-app-btn" onclick="sendAction('quit_app')">
       <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
         <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
         <polyline points="16 17 21 12 16 7"></polyline>
         <line x1="21" y1="12" x2="9" y2="12"></line>
       </svg>
       <span>Salir de la aplicación</span>
     </button>
     ```
4. **Add JavaScript in `liquid_html.py`**:
   - In `saveConfig()`:
     Extract and normalize `config-btn1-label`, `config-btn1-url`, `config-btn2-label`, `config-btn2-url`.
     Ensure `https://` prefix. Package into `buttons` array.
   - In `updateLiquidUI(state)`:
     Populate button inputs from `state.buttons`.

### 4.2 Changes in `popover_ui.py`
1. **Bridge Handler (`LoLWebBridge`)**:
   ```python
   elif action == "quit_app":
       self._controller.quit_application()
   ```
2. **`LoLPopoverController` additions**:
   - Add `self._on_quit = None` and `self._buttons = saved.get("buttons", [])`.
   - Update `_configure`: accept `on_quit: Optional[Callable[[], None]] = None`.
   - Add public `quit_application(self)`:
     ```python
     def quit_application(self) -> None:
         """Closes the popover and cleanly terminates the macOS application."""
         self.close()
         if callable(self._on_quit):
             try:
                 self._on_quit()
                 return
             except Exception:
                 pass
         app = AppKit.NSApplication.sharedApplication()
         if app and app.isRunning():
             app.terminate_(None)
     ```
   - Update `apply_config`:
     Accept `buttons: Optional[List[Dict[str, str]]] = None`.
     Store in `self._buttons`, save in `config.json`, pass `buttons=self._buttons` to `update_presence_config()`.
   - In `_build_web_ui` and `_sync_to_web`: pass `"buttons": self._buttons` in `state`.
   - In `_update_layout`: adjust heights:
     * Official: 380px
     * Detailed: 600px
     * Settings expanded (`#view-config`): 620px

### 4.3 Changes in `discord_rpc_manager.py`
1. **`ALLOWED_CONFIG_KEYS`**:
   Add `"buttons"` to the set.
2. **`DiscordRPCManager.__init__`**:
   Initialize `self.buttons: List[Dict[str, str]] = saved.get("buttons", [])`.
3. **Add `sanitize_buttons` helper function**:
   Validates list of dicts, truncates label to 32 chars, enforces HTTPS and 512 char max on URL, skips partial buttons, returns `Optional[List[Dict[str, str]]]`.
4. **In `_send_rpc_update`**:
   Include `buttons=valid_buttons` if `valid_buttons` is not None.

### 4.4 Changes in `app_gui.py`
1. Pass `on_quit=self.quit` when instantiating `LoLPopoverController` in `LoLAppController._setup`.

---

## 5. Verification Method

### 5.1 Automated Test Execution
Run the full test runner to ensure 100% test pass with zero regressions:
```bash
/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
```

### 5.2 Unit & Boundary Test Cases to Add
1. **UI Quit Verification**:
   - Instantiate `LoLPopoverController(on_quit=mock_quit)`.
   - Trigger `ctrl.quit_application()`. Assert `mock_quit` is called and `ctrl.is_shown()` is False.
   - Simulate WebKit message `{ "action": "quit_app" }` on `LoLWebBridge`. Assert `mock_quit` is called.
2. **Discord RPC Button Payload & Sanitization**:
   - Pass valid 2-button list `[{"label": "OP.GG", "url": "https://op.gg"}, {"label": "Twitch", "url": "https://twitch.tv"}]` -> verify `sanitize_buttons` returns identical list.
   - Pass 3 buttons -> verify only first 2 buttons are returned.
   - Pass button with HTTP `http://op.gg` -> verify auto-upgraded to `https://op.gg`.
   - Pass button missing label or missing URL -> verify button is skipped.
   - Pass button with empty strings or whitespace -> verify returns `None`.
   - Verify `update_presence_config(buttons=[...])` enqueues cleanly without exception and is accepted by `ALLOWED_CONFIG_KEYS`.
   - Verify attribute pollution tests pass (`_running`, `_cmd_queue` untouched).
3. **Persistence Verification**:
   - Call `apply_config(..., buttons=[{"label": "Test", "url": "https://example.com"}])`.
   - Check `~/.config/lol_discord_rpc/config.json` contains `"buttons"` array.
   - Re-instantiate `DiscordRPCManager(load_config=True)` and verify `mgr.buttons` matches saved value.

### 5.3 Invalidation Conditions
- Any failure in existing test suites (Tiers 1–5).
- Any unhandled exception in `pypresence` when partial or empty buttons are provided.
- Any UI truncation or invisible fields in `#view-config`.
