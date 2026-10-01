# Dispatch: worker_m10_1

- **Assigned Worker**: `worker_m10_1`
- **Working Directory**: `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m10_1`
- **Milestone**: M10 (Full Production Test Suite Integration, Hardening & Forensic Audit)
- **Authoritative Specifications**:
  - `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md` (specifically section ## Follow-up — 2026-09-29T23:10:58Z, Requirements R1–R4)
  - `/Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md`
  - `/Users/victormanuel/discord-rpc/.agents/teamwork/orchestrator_3/handoff.md`


## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## 2026-09-30T05:04:41Z
You are worker_m10_1.
Your working directory is: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m10_1
Project root: /Users/victormanuel/discord-rpc
Authoritative requirements: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md (specifically section ## Follow-up — 2026-09-29T23:10:58Z, Requirements R1–R4).
Consult also:
- /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md
- /Users/victormanuel/discord-rpc/.agents/teamwork/orchestrator_3/handoff.md
- /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m10_1/DISPATCH.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF MILESTONE M10 (Full Production Test Suite Integration, Hardening & Final Audit):
1. Code Cleanup & Defect Hardening:
   - In /Users/victormanuel/discord-rpc/app_gui.py line 57:
     Remove the residual developer personal path fallback:
     `fallback = os.path.join("/Users/victormanuel/discord-rpc", filename)`
     Ensure asset resolution relies only on base_dir and base_dir/assets. Verify with grep that ZERO occurrences of "/Users/victormanuel/" exist across all Python files in the project.
   - In /Users/victormanuel/discord-rpc/tests/test_challenger_audit.py:
     Update `test_challenger_06b_unhandled_non_dict_in_coalescer_defect_probe` to assert that sending non-dict to `_process_command` does NOT crash the worker (assert `manager.is_alive()` or `self.assertTrue(manager.is_active is not None)`), converting this obsolete defect probe into a positive regression test for worker survival.
2. Author Consolidated Acceptance Test Suite (tests/test_tier6_production.py):
   - Implement comprehensive, un-mocked acceptance tests covering all four follow-up requirements (R1–R4):
     * R1 (Lifecycle & Menubar):
       - Test NSStatusItem right-click context menu: verify menu title, items ("Abrir Ventana Principal", "Pausar Presencia" / "Reanudar Presencia", "Configuración ⚙️", "Salir (Cmd+Q)"), targets, and action selectors.
       - Test Quit application action in popover UI: verify both view-main and view-config send action 'quit_app', and that LoLPopoverController.handle_web_action('quit_app') triggers NSApplication.sharedApplication().terminate_ cleanly.
       - Test Single-Instance Lock: verify socket binding at ~/.config/lol_discord_rpc/app.sock and fcntl.flock on lock file. Verify secondary instance connection sends 'FOCUS' command and exits with code 0 without launching duplicate UI.
       - Test LaunchAgent Plist: verify /Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC path, StandardOutPath/StandardErrorPath in ~/Library/Logs/, and osascript notification execution on startup.
     * R2 (Discord Interactive Profile Buttons):
       - Test sanitize_buttons with 0, 1, 2, 3+ buttons, max 2 enforcement.
       - Test label truncation (<=32 chars) and URL truncation (<=512 chars).
       - Test HTTPS protocol enforcement: upgrading 'http://' to 'https://' and prefixing 'https://' if scheme missing.
       - Test dropping incomplete buttons (missing label or missing URL).
       - Test None return on empty list, verifying pypresence.update receives None / omits "buttons" key.
       - Test persistence in ~/.config/lol_discord_rpc/config.json and WebBridge sync.
     * R3 (CI/CD Pipeline & Standalone DMG Hardening):
       - Test .github/workflows/release.yml syntax, triggers (release published, tags v*.*.*, workflow_dispatch), runner macos-latest, bundle pre-staging step, test execution, DMG build, and release asset attachment.
       - Test build_dmg.py locate_site_packages() dynamic resolution across venv, system Python, and fallbacks.
       - Test launcher script portability: verify zero /Users/ paths.
       - Test automated SHA-256 export and format verification with shasum -a 256.
       - Test self-healing bundle auto-initialization in sync_bundle.py.
     * R4 (System Event Listeners & Error Resilience):
       - Test Cocoa NSWorkspace notification registration for NSWorkspaceDidLaunchApplicationNotification and NSWorkspaceDidWakeNotification.
       - Test that Discord launch notification triggers rpc_manager.reconnect() immediately.
       - Test that system wake notification triggers rpc_manager.reconnect() immediately.
       - Test in-app error toast handling in liquid_html.py.
3. Master Test Runner Integration (tests/run_tests.py):
   - Add Tier 6 ("Tier 6: Production Acceptance & System Integration") to `tests/run_tests.py` pointing to `tests/test_tier6_production.py`.
   - Update summary report table to display Tier 6 results alongside Tiers 1-5.
   - Run the master test runner and verify that 100% of tests pass cleanly across ALL 6 TIERS.
4. Bundle Synchronization & Verification:
   - Run `/Users/victormanuel/discord-rpc/venv/bin/python sync_bundle.py`.
   - Verify bundle integrity with `/Users/victormanuel/discord-rpc/venv/bin/python sync_bundle.py --verify-only`.
5. Testing Verification Commands:
   - Run `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_tier6_production.py -v`
   - Run `/Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py`
   - Run `/Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover -s tests -p "test_*.py"`

