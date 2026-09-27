# Progress — teamwork_preview_explorer_audit_2

**Last visited**: 2026-09-27T16:47:00Z
**Current phase**: Phase 2 — Concurrency & Resilience Audit Synthesis
**Status**: IN_PROGRESS

### Completed Steps
- [x] Initialized BRIEFING.md and DISPATCH.md
- [x] Reviewed mission scope and requirements (R2, F10, F11)
- [x] Ran automated test runner (149/149 tests passing across Tiers 1-5)
- [x] Inspected discord_rpc_manager.py, app_gui.py, status_item.py, and popover_ui.py
- [x] Audited pypresence 4.6.2 internals (baseclient.py, presence.py, utils.py, exceptions.py)
- [x] Tested live Discord IPC connection on host system (`/var/folders/.../discord-ipc-0`)
- [x] Discovered 6 critical defects/edge-cases:
  1. Attribute injection/pollution vulnerability in `_process_command(CONFIG_CHANGE)`
  2. Lack of `threading.Lock` on cross-thread state variables (`state`, `is_connected`, `is_active`, `start_time`)
  3. Missing pypresence exceptions in disconnect handler (`PipeClosed`, `ConnectionTimeout`, `ResponseTimeout`, `struct.error`)
  4. Synchronous `subprocess.run` on Cocoa main thread during launch in `app_gui.py`
  5. Unclosed `sock_writer` on macOS disconnect leading to delayed socket recycling
  6. Passive idle disconnection detection (absence of socket heartbeat)
- [x] Verified AppKit runloop isolation (`PyObjCTools.AppHelper.callAfter`)
- [x] Verified 20-30 min auto-restart match timer thread safety and randomization

### Next Steps
- [ ] Update BRIEFING.md with final investigation state and decisions
- [ ] Write comprehensive, structured handoff.md in working directory
- [ ] Send summary message to parent agent
