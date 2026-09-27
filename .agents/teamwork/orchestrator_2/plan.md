# Execution Plan: Audit and Defect Discovery (orchestrator_2)

## Phase 0: Specialized Survey & Codebase Investigation (Exploration)
- Spawn 3 Explorers in parallel to inspect each functional domain against the user requirements in ORIGINAL_REQUEST.md (§ Follow-up — 2026-09-27T16:39:44Z):
  - **Explorer 1 (UI & Liquid Glass / Popover)**:
    - Focus: `popover_ui.py`, HTML/JS/CSS WebKit overlay, 173-champion avatar searcher (DDragon CDN images, keyboard navigation, click selection), canonical game modes, rank updates & crests, Apex division suppression, UI switch responsiveness.
    - Output: Report bugs, performance bottlenecks, visual or functional discrepancies.
  - **Explorer 2 (Discord IPC & Concurrency)**:
    - Focus: `discord_rpc_manager.py`, `app_gui.py`, threading.Lock protection, queue handling, reconnect loops when Discord starts/closes, main-thread runloop non-blocking, socket error handling.
    - Output: Race conditions, deadlock risks, reconnection flaws, unhandled exceptions.
  - **Explorer 3 (macOS Integration, LaunchAgent & Test Suite)**:
    - Focus: `status_item.py`, `assets_gen.py`, `sync_bundle.py`, `~/Library/LaunchAgents/com.victormanuel.lolrpc.plist`, dock icon behavior, and running/inspecting the test suite `tests/run_tests.py` (Tiers 1-5).
    - Output: NSStatusItem 3-state rendering, LaunchAgent configuration, Python dock flicker analysis, existing test suite results and failing tests.

## Phase 1: Defect Triage & Implementation (Worker)
- Synthesize all findings from Explorers into a prioritized defect/hardening list.
- Dispatch Worker to implement fixes across affected modules.
- Ensure Worker verifies fixes with test runs and updates the bundle `/Applications/League of Legends RPC.app` if needed.

## Phase 2: Independent Multi-Agent Verification (Reviewers, Challengers, Auditor)
- Dispatch 2 independent Reviewers to review code quality, bug resolutions, and interface adherence.
- Dispatch 2 independent Challengers to execute stress tests, edge cases, and adversarial validation.
- Dispatch 1 Forensic Auditor to verify authentic implementation without cheating, hardcoded shortcuts, or mocks in production code.

## Phase 3: Gate Evaluation & Final Handoff
- Evaluate Gate results in `GATE_STATUS.md`.
- Ensure 100% test pass (Tiers 1-5, all tests passing cleanly).
- Write `handoff.md` and send completion report to Sentinel via `send_message`.
