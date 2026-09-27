# Dispatch Assignment — explorer_survey_2_gen2

## Objective
Investigate the design specifications, visual mockups, and Cocoa/PyObjC NSPopover architecture for macOS dark theme. (Replacing explorer_survey_2 after network timeout).

## Context & Inputs
- Original Request: `/Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md`
- Visual Mockup: `/Users/victormanuel/Desktop/123.png` and `/Users/victormanuel/.gemini/antigravity/brain/7bc6b881-49f2-492f-b654-3a4c515dc9b1/design_mockup.png`
- Working Directory: `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_2_gen2`
- Project Root: `/Users/victormanuel/discord-rpc`

## Scope
1. Analyze the reference mockup (`123.png` / `design_mockup.png`): layout, dimensions, colors, typography, UI components (header, gear button, mode cards/radio, switches, status indicator, action button, detailed settings view).
2. Detail the exact PyObjC AppKit architecture required: `NSStatusItem`, `NSPopover`, `NSViewController`, `NSView`, dark appearance (`NSAppearanceNameDarkAqua` / `NSAppearanceNameVibrantDark`), positioning relative to the status item button.
3. Determine how to implement interactive controls natively in Cocoa (NSSwitch or custom switch, NSButton styling, NSTextField, NSPopUpButton for champ/rank).
4. Specify menu bar dynamic icon rendering: 3 states (Normal logo, Active logo with blue badge/dot, Paused dimmed logo), pixel dimensions (e.g. 18x18 @1x / 36x36 @2x template/non-template), dynamic generation with PyObjC / PIL.

## Deliverable
Write a comprehensive report to `/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_survey_2_gen2/handoff.md`.
Report back via `send_message` to parent orchestrator when complete.
