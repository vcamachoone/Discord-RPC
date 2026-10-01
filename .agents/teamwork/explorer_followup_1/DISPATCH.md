## 2026-09-29T23:12:38Z
You are explorer_followup_1.
Your working directory is: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_1
Project root: /Users/victormanuel/discord-rpc
Authoritative requirements file: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md (specifically read section ## Follow-up — 2026-09-29T23:10:58Z).
Also consult /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md.

TASK:
Perform a comprehensive architectural survey and investigation on requirements R1 & R4:
1. Native App Lifecycle & Menubar Controls:
   - Status bar icon (`NSStatusItem` in `status_item.py` / `app_gui.py`): How click events are currently intercepted. How to implement secondary right-click (rightMouseDown or Cocoa target/action with NSEvent) displaying a native Cocoa `NSMenu` with: Open Popover, Toggle Presence (Pause/Resume), Settings (⚙️), and Quit (Cmd+Q).
   - Single-instance lock mechanism: How to ensure launching a second instance focuses the running instance without spawning duplicate processes or background daemons (e.g., lock file / Unix socket / Cocoa NSRunningApplication).
   - macOS Auto-start hardening (LaunchAgent in `launch_agent.py` or similar): Point LaunchAgent directly to the bundle binary (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`), configure logs in `~/Library/Logs/`, and brief system notification upon launch.
2. System Event Listeners & Error Resilience:
   - Cocoa `NSWorkspaceDidLaunchApplicationNotification` to connect when Discord launches.
   - Cocoa `NSWorkspaceDidWakeNotification` to re-establish Discord IPC connection on sleep wake.
   - In-app error boundary toast for WebKit or socket exceptions.

Investigate the existing code (`app_gui.py`, `status_item.py`, `popover_ui.py`, `discord_rpc_manager.py`, `launch_agent.py`, etc.).
Produce a detailed handoff report in your working directory at:
/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_1/handoff.md
Update your progress in progress.md as you work.
When finished, send a message to orchestrator_3 with the path to your report.
