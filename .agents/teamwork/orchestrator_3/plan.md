# Orchestrator 3 Execution Plan

## Mission
Transform League of Legends Discord RPC macOS into a commercial-grade production product with complete lifecycle management, interactive Discord profile buttons, system event resilience, and automated CI/CD distribution.

## Requirements Breakdown
- **R1: Native App Lifecycle, Menubar Controls & Hardened Auto-Start**
  - "Salir de la aplicación" (Quit App) control within popover UI & config view.
  - Secondary right-click on status bar icon (`NSStatusItem`) displaying native Cocoa `NSMenu`: Open Popover, Toggle Presence (Pause/Resume), Settings (⚙️), Quit (Cmd+Q).
  - Single-instance lock ensuring launching when already running brings existing popover to front without spawning duplicate processes.
  - Hardened Auto-start LaunchAgent pointing directly to bundle binary (`/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC`), logging to `~/Library/Logs/`, brief system notification upon launch.
- **R2: Discord Interactive Profile Buttons (Clickable Buttons)**
  - Up to two interactive clickable buttons in Discord Rich Presence payload configured in `#view-config`.
  - Sanitize and validate button URLs (HTTPS enforcement, length limits).
  - Dispatch button array cleanly to `pypresence` without crashing on empty/partial fields.
  - Persist button configuration in `~/.config/lol_discord_rpc/config.json`.
- **R3: Automated GitHub Actions CI/CD Release Pipeline**
  - Production `.github/workflows/release.yml` triggering on release or semver tags (`v*.*.*`) on `macos-latest`.
  - Setup Python, install dependencies, run full test suite across all 5 tiers.
  - Execute `build_dmg.py` to compile standalone compressed `.dmg` installer and attach `.dmg` and SHA-256 to GitHub Release.
- **R4: System Event Listeners (Discord Launch & Sleep/Wake Resilience)**
  - Cocoa `NSWorkspaceDidLaunchApplicationNotification` to connect when Discord launches.
  - Cocoa `NSWorkspaceDidWakeNotification` to re-establish Discord IPC connection on sleep wake.
  - In-app error boundary toast for WebKit or socket exceptions.

## Phases
1. **Phase 0: Survey Phase (Parallel Explorers)**
   - Spawn 3 Explorers (`teamwork_preview_explorer`):
     - Explorer 1: Menubar icon event dispatch, right-click NSMenu, NSWorkspace notifications (launch & wake), single-instance lock, LaunchAgent plist hardening.
     - Explorer 2: UI controls (Quit App button in popover/config), Discord profile buttons configuration in `#view-config`, WebKit bridge, and pypresence button payload schema & URL validation.
     - Explorer 3: GitHub Actions workflow (`release.yml`), DMG builder (`build_dmg.py`), existing test infrastructure and new test coverage requirements.
2. **Phase 1: Implementation Milestones**
   - **Milestone M7**: App Lifecycle, Menubar NSMenu, Single-Instance Lock, Hardened Auto-Start, and System Event Listeners (R1 & R4).
   - **Milestone M8**: Interactive Profile Buttons in Discord RPC payload, URL Sanitizer, Config UI in popover, and JSON persistence (R2).
   - **Milestone M9**: GitHub Actions CI/CD Release Pipeline (`release.yml`) & DMG Build packaging (R3).
3. **Phase 2: Milestone M10 - Full Verification, Adversarial Hardening & Forensic Audit**
   - Explorer analysis -> Worker test execution & sync -> Reviewers (2) -> Challengers (2) -> Auditor (1) -> Gate.
