# Architectural Survey & Codebase Analysis Report

**Agent**: `explorer_survey_1` (Codebase Architecture Explorer)  
**Project**: Discord RPC Redesign for League of Legends (macOS)  
**Target App**: `/Applications/League of Legends RPC.app`  
**Timestamp**: 2026-09-27T08:41:00Z  

---

## 1. Observation

### 1.1 Codebase File Map & Inventory

Inspection of `/Users/victormanuel/discord-rpc` revealed the following files and directories:

| Path | Size | Lines / Details | Purpose |
|---|---|---|---|
| `app_gui.py` | 12,612 B | 315 lines | Primary menubar application implementing `rumps.App` |
| `lol_rpc.py` | 3,204 B | 91 lines | Standalone CLI script testing Discord RPC presence |
| `start.sh` | 192 B | 6 lines | Shell script to terminate previous instances and launch `/Applications/League of Legends RPC.app` |
| `stop.sh` | 120 B | 5 lines | Shell script to terminate running instances (`pkill -f app_gui.py`) |
| `AppIcon.icns` | 2,901,770 B | Mac OS X icon (`ic12` format, 1024x1024 down to 16x16) | Application bundle dock/finder icon |
| `triangle_menubar.png` | 4,899 B | 44x44 PNG (Retina 22x22 pt) | Current menubar status icon (triangle logo) |
| `triangle_menubar_1x.png`| 1,863 B | 20x20 PNG | Standard resolution menubar icon |
| `triangle_logo.png` | 1,703,401 B | 1024x1024 PNG | High-res triangle logo asset |
| `triangle_logo_72.png` | 11,211 B | 72x72 PNG | Medium-res triangle logo asset |
| `lol_icon.png` | 81,820 B | 256x256 PNG | League of Legends logo asset |
| `lol_icon_512.png` | 81,820 B | 256x256 PNG | League of Legends logo asset |
| `lol_icon.svg` | 3,455 B | 21 lines | Vector wordmark for League of Legends |
| `venv/` | - | Directory | Python 3.9.6 virtual environment |
| `.agents/` | - | Directory | Teamwork metadata and agent workspaces |

### 1.2 Python Environment & Dependencies

Verification via `./venv/bin/python --version` and `./venv/bin/pip list`:
- **Python version**: `Python 3.9.6` (`/Library/Developer/CommandLineTools/usr/bin/python3`)
- **Installed packages**:
  - `pyobjc-core` (v11.1)
  - `pyobjc-framework-Cocoa` (v11.1) — Includes `AppKit`, `Foundation`, `CoreGraphics`
  - `pypresence` (v4.6.2) — Discord RPC IPC library
  - `pillow` (v11.3.0) — PIL image processing
  - `rumps` (v0.4.0) — Legacy menu bar library
  - `setuptools` (v58.0.4)
  - `pip` (v26.0.1)

Direct execution of PyObjC imports in the virtual environment was tested and verified:
```
AppKit & Foundation OK
objc OK
SF Symbol gearshape available: True
SF Symbol arrow.clockwise available: True
SF Symbol display available: True
NSSwitch state: 1
Popover configuration succeeded!
```

### 1.3 macOS Application Bundle Inspection (`/Applications/League of Legends RPC.app`)

Inspection of `/Applications/League of Legends RPC.app`:
- **Permissions**: Owned by `victormanuel:admin`, writable by the user without `sudo`.
- **Bundle Structure**:
  - `Contents/Info.plist`:
    - `CFBundleExecutable`: `League of Legends RPC`
    - `CFBundleIdentifier`: `com.victormanuel.lolrpc`
    - `CFBundleName`: `League of Legends RPC`
    - `CFBundleDisplayName`: `League of Legends`
    - `LSUIElement`: `<true/>` (Designates the app as an agent/menu bar item with no Dock icon)
  - `Contents/PkgInfo`: Contains `APPL????`
  - `Contents/MacOS/League of Legends RPC`: Executable shell script:
    ```bash
    #!/bin/bash
    DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    RESOURCES="$DIR/../Resources"
    export TK_SILENCE_DEPRECATION=1
    export PYTHONPATH="/Users/victormanuel/discord-rpc/venv/lib/python3.9/site-packages"
    exec /Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python "$RESOURCES/app_gui.py"
    ```
  - `Contents/Resources/`:
    - `AppIcon.icns`
    - `app_gui.py` (Currently byte-for-byte identical to `/Users/victormanuel/discord-rpc/app_gui.py`)
    - `triangle_logo.png`, `triangle_logo_72.png`, `triangle_menubar.png`
- **Active Process**: Verified that process PID 16603 was running `/Applications/League of Legends RPC.app/Contents/MacOS/../Resources/app_gui.py`.
- **Login Items (Auto-run)**: Verified via `osascript -e 'tell application "System Events" to get (exists login item "League of Legends RPC")'` that the app is already registered as an active macOS login item.

### 1.4 Discord Environment & IPC Status

- `/Applications/Discord.app` is installed and running (PID 3107).
- Active UNIX domain socket confirmed at `$TMPDIR/discord-ipc-0`.
- Client ID used: `1402418696126992445`.
- Discord app icon asset confirmed at `/Applications/Discord.app/Contents/Resources/electron.icns` (1024x1024 px).

### 1.5 Analysis of Existing Implementation Flaws

Detailed review of `app_gui.py` revealed several critical architectural shortcomings:

1. **`rumps` Limitation (`app_gui.py:8, 43`)**:  
   `rumps.App` only supports standard `NSMenu` dropdown textual lists. It cannot present a custom Cocoa view hierarchy, dark vibrant cards, sliders, or an `NSPopover` with an arrow pointing to the status bar item.
2. **Concurrency Race Conditions (`app_gui.py:150, 158, 164, 180, 188, 202`)**:  
   Every UI interaction (toggling active, switching modes, changing rank, changing champion, resetting match) triggers `threading.Thread(target=self._send_presence, daemon=True).start()`. These threads run concurrently with `_connection_worker` without any `threading.Lock`. Since `pypresence`'s underlying socket is not thread-safe, rapid user clicks or simultaneous timer ticks cause `BrokenPipeError`, `ConnectionResetError`, or invalid opcode errors.
3. **No Rate-Limiting or Debouncing**:  
   Discord enforces presence rate limits (maximum 1 update per 1–5 seconds). Burst clicks from the UI cause Discord IPC to reject or drop presence packets.
4. **Flawed Champion Name Resolution (`app_gui.py:266`)**:  
   Uses `f"https://ddragon.leagueoflegends.com/cdn/14.1.1/img/champion/{self.champion}.png"`.  
   Riot Data Dragon uses internal canonical IDs rather than plain character names (e.g., Wukong is `MonkeyKing`, Cho'Gath is `Chogath`, Kai'Sa is `Kaisa`, Dr. Mundo is `DrMundo`, etc.). User input without normalization yields 404 image errors on Discord.
5. **Flawed Rank Division Formatting (`app_gui.py:275`)**:  
   Hardcodes `f"{self.rank} II"`. This displays invalid text like "Challenger II", "Gran Maestro II", and "Maestro II" (tiers which do not have numbered divisions), and prevents users from selecting division I, III, or IV.
6. **Desynchronization Risk between Workspace and `/Applications`**:  
   Because `/Applications/League of Legends RPC.app` executes the script located in `Contents/Resources/app_gui.py`, edits made to `/Users/victormanuel/discord-rpc/app_gui.py` have zero effect on the running app unless synchronized into `Contents/Resources/`.

---

## 2. Logic Chain

```
Observation 1.1 & 1.5: app_gui.py uses rumps.App (NSMenu wrapper)
  -> NSMenu is fundamentally unable to host interactive custom UI (switches, cards, popovers)
  -> Replacement with native PyObjC AppKit (NSStatusItem + NSPopover) is strictly necessary.

Observation 1.2: pyobjc-core 11.1 and pyobjc-framework-Cocoa 11.1 are verified in ./venv
  -> All required classes (NSApplication, NSStatusItem, NSPopover, NSVisualEffectView,
     NSSwitch, NSButton, NSTextField, NSImage, NSOperationQueue) work out of the box.
  -> No external native compilers or additional pip packages are required.

Observation 1.4: Discord IPC socket is at $TMPDIR/discord-ipc-0 and uses synchronous I/O
  -> Direct calls on the AppKit main thread would block the Cocoa runloop, freezing UI.
  -> Background worker thread is mandatory.
  -> Concurrency locks (threading.Lock) and debouncing are required to prevent socket collision.

Observation 1.3: /Applications/League of Legends RPC.app launches Contents/Resources/app_gui.py
  -> The app bundle must be kept in sync with the project source file.
  -> An automated install/sync routine must be provided to keep the bundle up to date.

Observation 1.5: Mockup 123.png specifies 3 distinct menubar icon states
  -> Normal (neutral), Activo (with bright blue dot), Pausado (dimmed).
  -> Active icon MUST have setTemplate_(False) so macOS does not strip the blue dot color.
```

---

## 3. Architecture Specification for the Redesign

### 3.1 Component Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                   macOS Status Bar (NSStatusBar)                       │
│                        [ NSStatusItem ]                                │
│                  Dynamic Icon: Normal / Active / Paused                │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Click
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        NSPopover (Dark Aqua HUD)                       │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Header: Discord Icon (32x32) + Title/Subtitle + [⚙ Settings]     │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Mode Card 1: (•) Modo Oficial ("Solo LoL + Tiempo")             │  │
│  │ Mode Card 2: ( ) Modo Detallado ("Campeón, Rango y Modo")        │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Toggle Row 1: [🔄] Reiniciar partida (20-30 min)      [ NSSwitch ]│  │
│  │ Toggle Row 2: [💻] Iniciar automáticamente (Auto-run)  [ NSSwitch ]│  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Bottom Action: [ ⏹ DETENER EN DISCORD / ▶ INICIAR ]              │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │ Settings View (Expands or toggles via ⚙ or Detailed Mode):        │  │
│  │   - Champion input / selector (with Riot ID auto-normalization)  │  │
│  │   - Rank popup (Iron -> Challenger)                              │  │
│  │   - Division popup (I, II, III, IV — disabled for Master+)       │  │
│  │   - Game Mode selector ("Grieta del Invocador", "ARAM", etc.)    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ User Actions
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    DiscordRPCManager (Thread-Safe)                     │
│  - Dedicated background worker thread                                  │
│  - threading.Lock around socket connect() and update()                 │
│  - Debounce timer (prevents spamming updates < 2.0s)                  │
│  - Resilient auto-reconnect with exponential backoff                  │
│  - State notification dispatched to MainQueue via NSOperationQueue     │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Menubar Icon State Specifications

To match `123.png`:
1. **Normal**: Discord Clyde logo in monochrome/white. `setTemplate_(True)`.
2. **Activo**: Discord Clyde logo in white with a vivid circular blue dot (`#00A8FC` or `#5865F2`, diameter 6–7pt) placed in the lower-right corner. `setTemplate_(False)`.
3. **Pausado**: Discord Clyde logo rendered with 35% alpha / dim gray. `setTemplate_(False)`.

All icons should be generated at 44x44 px (Retina 22x22 pt) and 22x22 px (1x) using Pillow.

### 3.3 Champion Name Normalization Engine

A comprehensive dictionary mapping player-entered strings to Riot Data Dragon IDs:

| Input Pattern | Example Input | Data Dragon ID | CDN URL Image |
|---|---|---|---|
| Plain name | `Aatrox`, `Ahri`, `Zed` | `Aatrox`, `Ahri`, `Zed` | `.../Aatrox.png` |
| Alias / Special Riot ID | `Wukong` | `MonkeyKing` | `.../MonkeyKing.png` |
| Apostrophe champion | `Cho'Gath`, `chogath` | `Chogath` | `.../Chogath.png` |
| Apostrophe champion | `Kai'Sa`, `kaisa` | `Kaisa` | `.../Kaisa.png` |
| Apostrophe champion | `Kha'Zix`, `khazix` | `Khazix` | `.../Khazix.png` |
| Apostrophe champion | `Vel'Koz`, `velkoz` | `Velkoz` | `.../Velkoz.png` |
| Apostrophe champion | `Kog'Maw`, `kogmaw` | `KogMaw` | `.../KogMaw.png` |
| Apostrophe champion | `Bel'Veth`, `belveth` | `Belveth` | `.../Belveth.png` |
| Space / Title | `Dr. Mundo`, `Dr Mundo` | `DrMundo` | `.../DrMundo.png` |
| Roman numerals | `Jarvan IV`, `jarvan 4` | `JarvanIV` | `.../JarvanIV.png` |
| Multi-word | `Lee Sin`, `leesin` | `LeeSin` | `.../LeeSin.png` |
| Multi-word | `Master Yi`, `masteryi` | `MasterYi` | `.../MasterYi.png` |
| Multi-word | `Miss Fortune`, `mf` | `MissFortune` | `.../MissFortune.png` |
| Multi-word | `Tahm Kench`, `tahmkench` | `TahmKench` | `.../TahmKench.png` |
| Multi-word | `Twisted Fate`, `tf` | `TwistedFate` | `.../TwistedFate.png` |
| Multi-word | `Xin Zhao`, `xinzhao` | `XinZhao` | `.../XinZhao.png` |
| Multi-word | `Aurelion Sol`, `asol` | `AurelionSol` | `.../AurelionSol.png` |
| Companion name | `Nunu & Willump`, `nunu` | `Nunu` | `.../Nunu.png` |
| Title name | `Renata Glasc`, `renata` | `Renata` | `.../Renata.png` |

Algorithm:
1. Strip all non-alphanumeric characters (spaces, apostrophes, dots, hyphens, ampersands) and convert to lowercase.
2. Check alias map (e.g. `wukong` -> `MonkeyKing`, `nunu` -> `Nunu`, `renata` -> `Renata`, `chogath` -> `Chogath`).
3. If not found in alias map, capitalize first letter of each word or fallback to TitleCase.

### 3.4 Ranked Tier Division Rules

- **Apex Tiers (No divisions)**: `Master`, `Grandmaster`, `Challenger` (Spanish: `Maestro`, `Gran Maestro`, `Challenger`). Format: strictly `"{Rank}"` (never `"{Rank} II"`).
- **Standard Tiers (Divisions I–IV)**: `Hierro`, `Bronce`, `Plata`, `Oro`, `Platino`, `Esmeralda`, `Diamante`. Format: `"{Rank} {Division}"` (e.g. `Oro II`, `Plata I`, `Diamante IV`).

---

## 4. Caveats

1. **Active Process**: Process PID 16603 is currently running. When testing or deploying the new implementation, it must be terminated via `./stop.sh` or `pkill -f app_gui.py` before launching the new version.
2. **PyObjC RunLoop**: PyObjC apps using `NSApplication.sharedApplication().run()` block the main execution thread in the Cocoa event loop. Any non-UI initialization must take place before `.run()` or inside `applicationDidFinishLaunching_`.
3. **macOS Gatekeeper / Quarantine**: Because the app bundle at `/Applications/League of Legends RPC.app` is an ad-hoc wrapper running local Python scripts without an Apple Developer ID signature, it runs under development mode. The executable script in `Contents/MacOS/` must retain execute permissions (`chmod +x`).

---

## 5. Conclusion

1. **Feasibility**: 100% feasible with zero new pip dependencies. PyObjC (`AppKit`, `Foundation`) and Pillow are already installed and fully verified.
2. **Architecture Transition**:
   - Discard `rumps` completely.
   - Implement `LoLStatusItemController` managing an `NSStatusItem` with custom actions.
   - Implement `LoLPopoverViewController` hosting an `NSVisualEffectView` HUD containing the header, mode cards, switches, and action button matching `123.png`.
   - Implement a thread-safe `DiscordRPCService` with `threading.Lock`, debouncing, and main-queue dispatching.
   - Add asset generator script to produce Discord menubar icons (normal, active, paused).
   - Add `sync_app.sh` or update `start.sh` to ensure `/Applications/League of Legends RPC.app/Contents/Resources/app_gui.py` is synchronized with workspace changes.

---

## 6. Verification Method

To independently verify the findings in this report:

1. **Verify Python & PyObjC Dependencies**:
   ```bash
   cd /Users/victormanuel/discord-rpc
   ./venv/bin/python --version
   ./venv/bin/pip list
   ./venv/bin/python -c "import AppKit, Foundation, pypresence, PIL; print('All modules verified')"
   ```
2. **Verify App Bundle & Running Process**:
   ```bash
   ls -la "/Applications/League of Legends RPC.app/Contents/MacOS"
   cat "/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC"
   ps aux | grep -E "app_gui.py" | grep -v grep
   ```
3. **Verify Design Reference**:
   ```bash
   sips -g pixelWidth -g pixelHeight /Users/victormanuel/Desktop/123.png
   ```
4. **Verify Discord Socket**:
   ```bash
   ls -la "$TMPDIR/discord-ipc-0"
   ```
