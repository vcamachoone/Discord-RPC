# Dispatch Assignment — spec_miner_ui_1

## Objective
Extract UI/UX specification and component parameters from the design mockup at `/Users/victormanuel/Desktop/123.png` and `/Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png`.

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/spec_miner_ui_1`
- Mockup images: `/Users/victormanuel/Desktop/123.png` and `/Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png`

## Scope
1. Inspect the visual reference mockup (`123.png` / `design_mockup.png`).
2. Catalog all UI components:
   - Header: Discord icon, title "Discord RPC", subtitle "League of Legends", gear settings button.
   - Mode Selection: Radio/Card for "Modo Oficial" ("Solo LoL + Tiempo") vs "Modo Detallado" ("Campeón, Rango y Modo").
   - Switches: "Reiniciar partida" (auto cada 20-30 min), "Iniciar automáticamente" (con macOS Auto-run).
   - Action Button: "⏹ DETENER EN DISCORD" / "▶ INICIAR PRESENCIA".
   - Settings / Detailed Mode View: Controls for Champion and Rank (Iron to Challenger).
3. Document exact styling, colors, layout dimensions, Cocoa controls (`NSPopover`, `NSVisualEffectView`, `NSSwitch`, `NSButton`), and dynamic menubar icons (3 states: Normal, Active with blue dot, Paused dimmed).

## Deliverable
Write a clear specification report to `/Users/victormanuel/discord-rpc/.agents/teamwork/spec_miner_ui_1/handoff.md`.
Notify parent orchestrator via `send_message`.

## 2026-09-27T09:39:13Z
You are spec_miner_ui_1 (UI Spec Miner) for the Discord RPC redesign project.
Your assigned working directory is:
/Users/victormanuel/discord-rpc/.agents/teamwork/spec_miner_ui_1

MANDATORY INPUTS:
- Original Request: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md
- Dispatch Instructions: /Users/victormanuel/discord-rpc/.agents/teamwork/spec_miner_ui_1/DISPATCH.md
- Reference Images: /Users/victormanuel/Desktop/123.png and /Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png

Task:
Read ORIGINAL_REQUEST.md and DISPATCH.md. Inspect the design mockup image using view_file.
Extract the complete UI component hierarchy, visual layout, dimensions, dark theme styling, Cocoa PyObjC controls (NSPopover, NSVisualEffectView, NSSwitch, NSButton), and menubar icon states (Normal, Active with blue dot, Paused dimmed).
Document all findings concisely and completely in:
/Users/victormanuel/discord-rpc/.agents/teamwork/spec_miner_ui_1/handoff.md.

Send a completion message via send_message to parent when done.
