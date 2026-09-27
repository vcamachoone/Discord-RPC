## 2026-09-27T16:43:00Z

Task Assignment for teamwork_preview_explorer_audit_2:
- Working Directory: /Users/victormanuel/discord-rpc/.agents/teamwork/teamwork_preview_explorer_audit_2
- Original Request: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md
- Scope Document: /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md

Scope: Auditoría de Concurrencia y Resiliencia de Discord IPC
Target Files: discord_rpc_manager.py, app_gui.py, status_item.py.

Please investigate and produce a structured handoff.md with verified evidence chains for:
1. Actor model and threading.Lock protection during rapid state changes or UI interaction.
2. Discord connection resilience: cold start without Discord, Discord closing while running, Discord reopening, reconnection loop backoff, avoiding uncaught socket exceptions.
3. AppKit main runloop isolation: ensuring zero network/blocking calls on main thread, PyObjCTools.AppHelper.callAfter usage for all UI callbacks.
4. Auto-restart match timer (20-30 min randomizer) thread safety.
