# BRIEFING — 2026-09-27T08:40:40Z

## Mission
Investigate the existing Discord RPC codebase, packaging mechanisms, virtual environments, dependencies, and `/Applications/League of Legends RPC.app` to produce an architectural survey.

## 🔒 My Identity
- Archetype: explorer
- Roles: explorer
- Working directory: /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1
- Original parent: fbd9aeb5-9cc5-4b16-930b-4d15d7610d01
- Milestone: codebase-architecture-investigation

## 🔒 Key Constraints
- Read-only investigation — do NOT implement
- Write only inside working directory /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1
- Use exact evidence (file paths, line numbers, command outputs)
- Report to parent via send_message when handoff.md is ready

## Current Parent
- Conversation ID: fbd9aeb5-9cc5-4b16-930b-4d15d7610d01
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `/Users/victormanuel/discord-rpc` (root directory, scripts, assets, virtualenv)
  - `/Applications/League of Legends RPC.app` (macOS app bundle, Info.plist, launcher bash script, resources)
  - `/Users/victormanuel/Desktop/123.png` (design mockup reference)
  - `/Applications/Discord.app` (system installed Discord, verified running process and IPC socket)
- **Key findings**:
  1. Virtualenv `./venv` runs Python 3.9.6 with `pyobjc-core 11.1`, `pyobjc-framework-Cocoa 11.1`, `pypresence 4.6.2`, `pillow 11.3.0`, `rumps 0.4.0`.
  2. The existing app at `/Applications/League of Legends RPC.app` uses a custom launcher script that imports `./venv/lib/python3.9/site-packages` and executes `Contents/Resources/app_gui.py`.
  3. `app_gui.py` is currently a `rumps.App` text-menu statusbar application. `rumps` only supports `NSMenu` textual items and cannot support the custom `NSPopover` UI from `123.png`.
  4. PyObjC `AppKit` natively supports `NSPopover`, `NSVisualEffectView` (HUD dark glass), `NSSwitch`, and SF Symbols (`gearshape`, `arrow.clockwise`, `display`).
  5. Discord presence is currently handled via `pypresence.Presence("1402418696126992445")`. Current implementation lacks concurrency locking around the RPC socket, has race conditions, hardcodes rank division ("II") across all ranks including Challenger, and lacks champion name normalization (Wukong -> MonkeyKing, etc.).
- **Unexplored areas**: None for survey scope. All required areas examined.

## Key Decisions Made
- Recommending replacing `rumps` with pure native PyObjC `NSApplication` + `NSStatusItem` + `NSPopover`.
- Recommending thread-safe RPC worker pattern with `threading.Lock` and main thread UI dispatch via `NSOperationQueue.mainQueue()`.
- Recommending synchronizing `/Applications/League of Legends RPC.app/Contents/Resources/app_gui.py` whenever local code changes.

## Artifact Index
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1/DISPATCH.md — Dispatch instructions
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1/BRIEFING.md — Situational awareness
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1/progress.md — Liveness heartbeat
- /Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_1/handoff.md — Final deliverable report
