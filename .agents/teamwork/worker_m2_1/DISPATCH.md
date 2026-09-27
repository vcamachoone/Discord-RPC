# Dispatch Assignment — worker_m2_1

## Objective
Implement Milestone 2: Native Dark NSPopover UI Component (`popover_ui.py`).

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Master Plan: `/Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md`
- Visual Mockup: `/Users/victormanuel/Desktop/123.png` and `/Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m2_1`
- Project Root: `/Users/victormanuel/discord-rpc`
- Virtual Environment: `/Users/victormanuel/discord-rpc/venv`

## File Ownership
You exclusively own:
- `/Users/victormanuel/discord-rpc/popover_ui.py`

## Technical Requirements
1. Class `LoLPopoverController` managing an `NSPopover`:
   - Configured with `NSPopoverBehaviorTransient` so clicking outside dismisses it cleanly.
   - Dark theme appearance using `NSAppearance.appearanceNamed_(NSAppearanceNameDarkAqua)` or `NSAppearanceNameVibrantDark`.
   - Hosted in a custom `NSViewController` with an `NSVisualEffectView` HUD container (`NSVisualEffectMaterialHUDWindow` or dark material, blending mode behind window).
   - Method `show(button)` anchoring the popover to the status item button using `showRelativeToRect_ofView_preferredEdge_(button.bounds(), button, NSRectEdgeMinY)` (or `close()`).
2. Header Component:
   - Discord logo icon (32x32 pt)
   - Title label: "Discord RPC" (bold white)
   - Subtitle label: "League of Legends" (secondary text color)
   - Settings gear button (using SF Symbol `gearshape` or custom icon) that toggles the Settings panel.
3. Mode Selection (Cards / Radio):
   - Card 1: "Modo Oficial" with subtitle "Solo LoL + Tiempo"
   - Card 2: "Modo Detallado" with subtitle "Campeón, Rango y Modo"
   - Clicking a card updates selection state and shows/hides detailed controls.
4. Interactive Switches:
   - Row 1: "Reiniciar partida" with description "automáticamente cada 20–30 min", toggled via `NSSwitch`.
   - Row 2: "Iniciar automáticamente" with description "con macOS Auto-run", toggled via `NSSwitch`.
   - Setting changes notify the RPC manager.
5. Prominent Action Button:
   - Bottom full-width button.
   - Active state: "⏹ DETENER EN DISCORD" (turns presence off, updates status item icon to paused).
   - Paused / Inactive state: "▶ INICIAR PRESENCIA" (starts presence, updates status item icon to active).
6. Settings / Detailed Configuration Panel:
   - Champion input text field with real-time resolution using `ChampionResolver` from `lol_champions.py`.
   - Rank popup (`NSPopUpButton`) listing Iron through Challenger.
   - Division popup (`NSPopUpButton`) with divisions I, II, III, IV. Automatically disabled if an Apex tier (Master, Grandmaster, Challenger, Unranked) is selected.
   - Game mode selector / popup ("Grieta del Invocador (Clasificatoria)", "ARAM", etc.).
7. Concurrency & Event Handling:
   - All UI actions push commands non-blockingly to `DiscordRPCManager`.
   - Callbacks from `DiscordRPCManager` (`on_state_change`, `on_match_reset`) update the UI elements (e.g. updating button title, elapsed timer, status icons).
8. Verification:
   - Run unit tests and `./venv/bin/python tests/run_tests.py` to ensure all Tier 1, 2, 3 tests for F3, F4, F5, F6, F7 pass!
9. Report results in `/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m2_1/handoff.md`.

## 2026-09-27T10:13:44Z
Received worker_m2_1 dispatch for Native Dark NSPopover UI Component (popover_ui.py).
Target file: /Users/victormanuel/discord-rpc/popover_ui.py
Visual reference: /Users/victormanuel/Desktop/123.png
All Tier 1-3 tests for F3, F4, F5, F6, F7 must pass.

