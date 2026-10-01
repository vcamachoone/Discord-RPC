## 2026-09-30T04:13:10Z

You are worker_m8_1.
Your working directory is: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m8_1
Project root: /Users/victormanuel/discord-rpc
Authoritative requirements: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md (specifically section ## Follow-up — 2026-09-29T23:10:58Z, Requirement R2).
Read the comprehensive survey blueprint at:
/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_2/handoff.md
Also consult /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF MILESTONE M8 (Requirement R2: Discord Interactive Profile Buttons):
1. Discord Rich Presence payload requirements for clickable buttons:
   - Add "buttons" to ALLOWED_CONFIG_KEYS in discord_rpc_manager.py.
   - Implement sanitize_buttons(raw_buttons: Any) -> Optional[List[Dict[str, str]]]:
     * Enforce maximum of 2 buttons.
     * Validate each button has non-empty 'label' (truncate to 32 chars) and 'url' (truncate to 512 chars).
     * Enforce HTTPS: prefix 'https://' if missing, upgrade 'http://' to 'https://'.
     * Drop incomplete buttons (label without URL or URL without label).
     * Return None if list is empty, so rpc.update() completely omits the "buttons" key (preventing pypresence/Discord schema rejection on empty list).
   - In _send_rpc_update(), pass `buttons=valid_buttons` if valid_buttons is not None.
2. Configuration UI in #view-config (liquid_html.py):
   - In #view-config, add card inputs for Button 1 (label max 32, url max 512) and Button 2 (label max 32, url max 512).
   - In saveConfig(), extract and sanitize button values, package into buttons array, and send with action 'save_config'.
   - In updateLiquidUI(state), populate the button inputs from state.buttons.
   - Add CSS styling (.buttons-config-group, .btn-config-card, .btn-fields-grid) and ensure #view-config has overflow-y: auto with max-height to avoid clipping.
3. WebBridge & Persistence (popover_ui.py):
   - In LoLPopoverController: store self._buttons (default []), load from ~/.config/lol_discord_rpc/config.json.
   - In apply_config(..., buttons=None), update self._buttons, persist in config.json, and forward to rpc_manager.update_presence_config(buttons=self._buttons).
   - Include "buttons": self._buttons in _sync_to_web / _build_web_ui.
4. Unit & Regression Tests:
   - Add tests/test_milestone8_buttons.py with comprehensive tests covering URL sanitization, HTTPS enforcement, label/URL truncation, partial button discarding, None handling, config persistence, and update_presence_config dispatch.
   - Run master test runner: /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py (149/149 must pass).
   - Synchronize bundle to /Applications/League of Legends RPC.app using sync_bundle.py.

Produce a detailed handoff report in your working directory at:
/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m8_1/handoff.md
Send a message when finished.
