# BRIEFING — 2026-09-30T04:03:00Z

## Mission
Investigate the exact in-flight connection abortion race condition during shutdown() in discord_rpc_manager.py, analyze prior forensic auditor reports and peer findings, and formulate the exact, foolproof fix.

## 🔒 My Identity
- Archetype: explorer
- Roles: investigation, synthesis
- Working directory: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_m7_iter3_1
- Original parent: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Milestone: m7_iter3

## 🔒 Key Constraints
- Read-only investigation — do NOT implement directly in production files
- Adhere strictly to the Handoff Protocol and Verification standards
- Eliminate the 12-14% failure rate on test_f11_b5_timer_cleanup_on_shutdown and test_rpc_manager_shutdown_race
- Keep BRIEFING.md under ~100 lines

## Current Parent
- Conversation ID: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
- Updated: 2026-09-30T03:49:44Z

## Investigation State
- **Explored paths**:
  * `discord_rpc_manager.py` (lines 228-235, 320-327, 384-450, 480-520)
  * `venv/lib/python3.9/site-packages/pypresence/` (`presence.py`, `baseclient.py`, `utils.py`)
  * `tests/test_tier1_features.py`, `tests/test_tier2_boundaries.py`, `tests/test_adversarial_stress.py`
  * Prior handoffs: `auditor_m7_iter2_1`, `reviewer_m7_iter2_2`, `challenger_m7_iter2_1`, `challenger_m7_iter2_2`
- **Key findings**:
  * Root cause 1: `self._rpc` is None during `new_rpc.connect()`, causing `_safe_close_rpc()` to be a no-op during in-flight handshakes.
  * Root cause 2: `pypresence.Presence.connect()` on line 84 overrides `self.loop` with `get_event_loop()`, bypassing any pre-existing loop reference and leaving freshly created loops running.
  * Root cause 3: Window between lock release and `new_rpc.connect()` invocation allowed `shutdown()` to clear references before `connect()` ran, causing `connect()` to proceed unstopped.
  * Solution verified: Tracking `self._connecting_rpc`, wrapping `update_event_loop` to halt freshly created loops, intercepting pre- and post-connect shutdown flags, aborting socket transport, and safely stopping event loops eliminated 100% of thread leaks and achieved 0 failures across 400 consecutive stress runs and 149/149 test runner passes.
- **Unexplored areas**: None. Deterministic reproduction and resolution verified down to microseconds.

## Key Decisions Made
- Formulated `_safe_close_target()` helper to decouple target instance teardown.
- Intercepted `update_event_loop` on the connecting instance to guarantee that `pypresence` cannot create an unstopped orphan event loop.
- Added guard checks before and after `connect()` under `self._lock`.
- Produced both `discord_rpc_manager.patch` and `proposed_discord_rpc_manager.py`.

## Artifact Index
- `DISPATCH.md` — Parent dispatch instructions
- `BRIEFING.md` — Situational awareness index
- `progress.md` — Liveness heartbeat tracker
- `test_fix_prototype.py` — Prototype test script verifying 400 shutdowns with 0 failures
- `proposed_discord_rpc_manager.py` — Complete proposed file ready for Worker
- `discord_rpc_manager.patch` — Clean unified diff patch file for Worker
- `handoff.md` — 5-component structured handoff report
