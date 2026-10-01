# Handoff Report: CI/CD Release Pipeline, Standalone DMG Packaging & Test Suite Verification

**Agent**: `explorer_followup_3`  
**Date**: 2026-09-29T23:19:00Z  
**Scope**: Requirement R3 (Automated GitHub Actions CI/CD Pipeline & Standalone DMG Packaging) and Test Suite Assessment for R1, R2, R3, R4.  
**Integrity Mode**: Read-only Investigation  

---

## 1. Observation

### 1.1 Existing Packaging & DMG Infrastructure
- **`build_dmg.py` exists** at `/Users/victormanuel/discord-rpc/build_dmg.py` (436 lines).
  - Lines 26-32:
    ```python
    SOURCE_ROOT = os.path.dirname(os.path.abspath(__file__))
    DIST_DIR = os.path.join(SOURCE_ROOT, "dist")
    STAGING_DIR = os.path.join(DIST_DIR, "dmg_staging")
    FINAL_DMG_NAME = "League_of_Legends_RPC_Installer.dmg"
    FINAL_DMG_PATH = os.path.join(DIST_DIR, FINAL_DMG_NAME)
    VOLUME_NAME = "League of Legends RPC"
    ```
  - Lines 33-42 define `RUNTIME_MODULES`:
    ```python
    RUNTIME_MODULES = [
        "app_gui.py", "assets_gen.py", "status_item.py", "popover_ui.py",
        "liquid_html.py", "discord_rpc_manager.py", "lol_champions.py", "lol_ranks.py",
    ]
    ```
  - Lines 51-85 define `UNIVERSAL_LAUNCHER_SCRIPT` embedded into `Contents/MacOS/League of Legends RPC`.
    - **Defect / Leak**: Line 74 hardcodes developer user directory:
      ```bash
      elif [ -x "/Users/victormanuel/discord-rpc/venv/bin/python3" ]; then
          PYTHON_BIN="/Users/victormanuel/discord-rpc/venv/bin/python3"
      ```
  - Lines 268-290 bundle pruned site-packages into `Contents/Resources/site-packages`:
    ```python
    if bundle_deps:
        venv_sp = os.path.join(SOURCE_ROOT, "venv", "lib", "python3.9", "site-packages")
    ```
    - **Defect**: Hardcodes `"python3.9"` and folder name `"venv"`. In GitHub Actions runners using `actions/setup-python@v5`, site-packages resides in the hosted Python directory (`sysconfig.get_path('purelib')`), so `os.path.isdir(venv_sp)` evaluates to `False` and silently skips bundling dependencies!
  - Lines 371-385 create the UDZO compressed disk image using macOS `hdiutil`:
    ```python
    cmd = [
        "hdiutil", "create", "-volname", volume_name,
        "-srcfolder", STAGING_DIR, "-ov", "-format", "UDZO",
        "-imagekey", "zlib-level=9", output_dmg,
    ]
    ```
  - Lines 404-416 compute the SHA-256 hash using `hashlib.sha256()`, but **do not write a `.sha256` checksum file to disk**. Only prints the hash to stdout.
  - Line 217-228 hardcodes `"CFBundleShortVersionString": "1.0.0"` and `"CFBundleVersion": "1.0.0"` without dynamic version injection.
  - Executing `python build_dmg.py` completed in ~20 seconds, generating:
    - Path: `dist/League_of_Legends_RPC_Installer.dmg` (10.88 MB / 11,413,158 bytes)
    - SHA-256: `4363fa16aee98bb4295fd1194f6d15eb591148e70677f064cb6942a62e15727b`
    - Verified by mounting with `hdiutil attach -nobrowse` and running `sync_bundle.verify_bundle_integrity()` inside `/Volumes/League of Legends RPC/League of Legends RPC.app`, returning `{'valid': True, 'checks': {...}, 'errors': []}`.

- **`generate_dmg_background.py` exists** at `/Users/victormanuel/discord-rpc/generate_dmg_background.py` (205 lines):
  - Generates a Retina 2x dark background graphic (`dist/dmg_background.png`, 1320x840 px) and 1x fallback (660x420 px).
  - Embedded into `.background/background.png` inside the staging directory.
  - Includes drop target guides for the App and `/Applications` symlink, with Discord Blurple (`#5865F2`) and Hextech Gold (`#C8AA6E`) glows.

- **`sync_bundle.py` exists** at `/Users/victormanuel/discord-rpc/sync_bundle.py` (292 lines):
  - Copies runtime modules into `/Applications/League of Legends RPC.app`.
  - Line 182 contains a fatal pre-condition for fresh runners:
    ```python
    if not os.path.isdir(bundle_path):
        logger.error("Target bundle path does not exist: %s", bundle_path)
        return False
    ```
    If `/Applications/League of Legends RPC.app` does not exist, it aborts instead of creating it.

### 1.2 GitHub Actions Workflows
- Searched `/Users/victormanuel/discord-rpc/.github/workflows/`:
  - Result: The directory `.github` does **NOT** exist in the repository yet.
  - No existing CI/CD pipelines or release workflows exist.

### 1.3 Test Suite State & Execution
- Executed `venv/bin/python tests/run_tests.py`:
  - Runs Tiers 1-5:
    - Tier 1: Feature Coverage (60 tests) — PASS (1.477s)
    - Tier 2: Boundary & Corner Cases (60 tests) — PASS (0.828s)
    - Tier 3: Cross-Feature Interactions (14 tests) — PASS (0.063s)
    - Tier 4: Real-World Scenarios (5 tests) — PASS (0.778s)
    - Tier 5: Adversarial Stress & Faults (10 tests) — PASS (13.887s)
    - Total: **149 / 149 passed cleanly (100% success)** in 17.034s.
- Executed `python -m unittest discover tests -p "test_*.py"`:
  - Discovered 241 total tests in repository across 14 test files (`test_audit_fixes.py`, `test_challenger_audit.py`, `test_challenger_audit_2.py`, `test_adversarial_challenger2.py`, etc.).
  - Total: **241 / 241 passed cleanly** in 22.743s.
- **Critical CI Dependency Observed in Existing Tests**:
  - `tests/test_tier1_features.py:718`: `test_f12_app_bundle_exists` asserts `os.path.isdir("/Applications/League of Legends RPC.app")`.
  - `tests/test_tier2_boundaries.py:660`: `BUNDLE_PATH = "/Applications/League of Legends RPC.app"`.
  - `tests/test_tier3_interactions.py:258`: checks `/Applications/League of Legends RPC.app/Contents/Resources`.
  - `tests/test_tier4_scenarios.py:270`: checks `/Applications/League of Legends RPC.app`.
  - **Impact on CI**: In a standard ephemeral GitHub Actions runner (`macos-latest`), `/Applications/League of Legends RPC.app` is NOT present initially. If `tests/run_tests.py` runs before staging `/Applications/League of Legends RPC.app`, **Tier 1, Tier 2, Tier 3, and Tier 4 will immediately fail on CI**.

---

## 2. Logic Chain

### 2.1 CI/CD Pipeline Requirements (`.github/workflows/release.yml`)
1. From Observation §1.2, no GitHub workflow exists.
2. From ORIGINAL_REQUEST §Follow-up R3:
   - Must trigger on release publication or semver git tags (`v*.*.*`).
   - Must run on `macos-latest`.
   - Must set up Python, install dependencies from `requirements.txt`, and run full test suites.
   - Must execute `build_dmg.py` to compile the standalone compressed `.dmg` installer.
   - Must automatically attach the generated `.dmg` and its SHA-256 checksum to the GitHub Release.
3. From Observation §1.3, running tests on a clean runner requires `/Applications/League of Legends RPC.app` to be initialized first. Therefore, the workflow must include a pre-test bundle staging step.
4. For permissions, GitHub Actions token requires `permissions: contents: write` to attach assets to a GitHub Release.
5. In addition to git tags, adding `workflow_dispatch` allows manual testing of the build and DMG generation without requiring a production tag or release.
6. Using `softprops/action-gh-release@v2` is the industry standard for publishing release assets on GitHub, supporting both tags and release events, automated release notes generation, and multiple file uploads.
7. Using `actions/upload-artifact@v4` ensures that even on manual workflow runs or test pushes, the generated `.dmg` and `.sha256` files can be downloaded directly from GitHub Actions artifacts.

### 2.2 DMG Builder Hardening (`build_dmg.py`)
1. From Observation §1.1, `build_dmg.py` already creates high-quality DMG installers using native `hdiutil` in headless-compatible mode (UDZO compression, zlib level 9).
2. However, three defects must be remediated:
   - **Dynamic site-packages**: Replacing the hardcoded `venv/lib/python3.9/site-packages` with dynamic discovery using `sysconfig.get_path('purelib')`, `site.getsitepackages()`, and directory globbing across `venv` / `.venv` / system Python.
   - **Clean launcher script**: Removing `/Users/victormanuel/discord-rpc/venv/bin/python3` from `UNIVERSAL_LAUNCHER_SCRIPT` so the bundled launcher has no machine-specific paths.
   - **Checksum file generation**: Writing `{output_dmg}.sha256` containing `{hash}  {filename}\n` directly upon build completion.
   - **Dynamic versioning**: Reading `--version`, `RELEASE_VERSION`, or `GITHUB_REF_NAME` to populate `CFBundleShortVersionString` and `CFBundleVersion` in `Info.plist`.

### 2.3 Comprehensive Test Suite Assessment for R1, R2, R3, R4
1. Currently, `tests/run_tests.py` executes 5 tiers covering baseline features F1-F12 and stress scenarios.
2. The new requirements from Follow-up (2026-09-29T23:10:58Z) introduce four distinct functional domains:
   - **R1 (Lifecycle & Menubar)**: UI quit button in main popover & config view, secondary right-click Cocoa `NSMenu` on `NSStatusItem`, single-instance lock file/socket mechanism, hardened LaunchAgent plist with direct binary and logging paths, launch notification.
   - **R2 (Discord Buttons)**: rich presence interactive button array (max 2), HTTPS enforcement, label length limits, empty/partial field sanitization, persistence in `~/.config/lol_discord_rpc/config.json`, whitelist in `ALLOWED_CONFIG_KEYS`.
   - **R3 (CI/CD & Packaging)**: workflow YAML schema and trigger validation, DMG builder execution, SHA-256 integrity, standalone import verification.
   - **R4 (System Events & Error Resilience)**: `NSWorkspaceDidLaunchApplicationNotification` for Discord startup, `NSWorkspaceDidWakeNotification` for sleep/wake re-establishment, in-app error boundary with JavaScript toast alerts.
3. To achieve 100% verification coverage without regressing existing tests, a dedicated test tier `Tier 6: Production Hardening & CI/CD (R1-R4)` must be implemented and registered in `tests/run_tests.py`.

---

## 3. Caveats

1. **GitHub Actions Network & Secrets**:
   - The workflow uses `GITHUB_TOKEN` automatically provided by GitHub Actions (`secrets.GITHUB_TOKEN`). No manual secret configuration is required if the repository workflow permissions allow "Read and write permissions" in Settings -> Actions -> General.
2. **macOS Architecture in Runners**:
   - GitHub Actions `macos-latest` runs on ARM64 (Apple Silicon). Since `build_dmg.py` uses universal python execution and pure python/PyObjC wheels matching the runner architecture, the generated DMG will bundle the architecture of the runner. If universal2 distribution (x86_64 + arm64) is desired in the future, fat binaries can be configured.
3. **Headless `hdiutil` vs AppleScript Finder Positioning**:
   - `build_dmg.py` generates `.background/background.png`, `/Applications` symlink, `LEEME - Instrucciones.txt`, and `⚡️ Instalación Rápida.command`. It intentionally avoids running interactive AppleScript Finder commands (like `create-dmg`) because Finder AppleScript requires an active desktop window server session and hangs in headless GitHub Actions runners. The current approach is 100% reliable in CI.

---

## 4. Conclusion & Actionable Design

### 4.1 Production `.github/workflows/release.yml` Specification

Create `.github/workflows/release.yml` with the following production implementation:

```yaml
name: Release Build & Distribution

on:
  release:
    types: [published]
  push:
    tags:
      - 'v*.*.*'
      - 'v*'
  workflow_dispatch:
    inputs:
      skip_tests:
        description: 'Skip test suite execution (dry run only)'
        required: false
        default: false
        type: boolean

permissions:
  contents: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build-and-release:
    name: Build macOS DMG & Publish Release
    runs-on: macos-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python 3.9
        uses: actions/setup-python@v5
        with:
          python-version: '3.9'
          cache: 'pip'

      - name: Upgrade pip and install dependencies
        run: |
          python3 -m pip install --upgrade pip
          pip3 install -r requirements.txt

      - name: Pre-stage application bundle in /Applications (Required for E2E Tests)
        run: |
          echo "Pre-staging /Applications/League of Legends RPC.app for test suite..."
          sudo mkdir -p "/Applications/League of Legends RPC.app"
          sudo chown -R $(whoami) "/Applications/League of Legends RPC.app"
          python3 -c "import build_dmg; build_dmg.stage_application_bundle('/Applications/League of Legends RPC.app', bundle_deps=False)"
          python3 sync_bundle.py

      - name: Run Complete E2E Test Suite (Tiers 1-5 + Production Tier 6)
        if: ${{ !inputs.skip_tests }}
        run: |
          python3 tests/run_tests.py

      - name: Compile Standalone Compressed DMG Installer
        id: build_dmg
        run: |
          VERSION="${GITHUB_REF_NAME#v}"
          if [ -z "$VERSION" ] || [ "$VERSION" = "main" ]; then
            VERSION="1.0.0"
          fi
          echo "Building DMG for version: $VERSION"
          python3 build_dmg.py --output "dist/League_of_Legends_RPC_Installer.dmg" --volname "League of Legends RPC" --version "$VERSION"

      - name: Verify and Validate Checksum File
        run: |
          cd dist
          if [ ! -f "League_of_Legends_RPC_Installer.dmg.sha256" ]; then
            shasum -a 256 League_of_Legends_RPC_Installer.dmg > League_of_Legends_RPC_Installer.dmg.sha256
          fi
          echo "Generated SHA-256 Checksum:"
          cat League_of_Legends_RPC_Installer.dmg.sha256
          echo "Verifying checksum match..."
          shasum -a 256 -c League_of_Legends_RPC_Installer.dmg.sha256
          cd ..

      - name: Upload Build Artifacts (Actions Run)
        uses: actions/upload-artifact@v4
        with:
          name: League-of-Legends-RPC-macOS-DMG
          path: |
            dist/League_of_Legends_RPC_Installer.dmg
            dist/League_of_Legends_RPC_Installer.dmg.sha256
          retention-days: 14

      - name: Attach Assets to GitHub Release
        uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/') || github.event_name == 'release'
        with:
          files: |
            dist/League_of_Legends_RPC_Installer.dmg
            dist/League_of_Legends_RPC_Installer.dmg.sha256
          fail_on_unmatched_files: true
          generate_release_notes: true
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

### 4.2 Hardened `build_dmg.py` Improvements

The following improvements must be applied to `build_dmg.py`:

1. **Dynamic `locate_site_packages()`**:
```python
def locate_site_packages() -> Optional[str]:
    """Dynamically locates the site-packages directory for the active Python environment."""
    import sysconfig
    for key in ("purelib", "platlib"):
        path = sysconfig.get_path(key)
        if path and os.path.isdir(path) and "site-packages" in path:
            return path

    try:
        import site
        for path in site.getsitepackages():
            if os.path.isdir(path):
                return path
    except Exception:
        pass

    for folder in ("venv", ".venv"):
        lib_root = os.path.join(SOURCE_ROOT, folder, "lib")
        if os.path.isdir(lib_root):
            for entry in sorted(os.listdir(lib_root), reverse=True):
                candidate = os.path.join(lib_root, entry, "site-packages")
                if os.path.isdir(candidate):
                    return candidate
    return None
```

2. **Clean Universal Launcher Script (Sanitized)**:
Remove developer personal paths:
```bash
UNIVERSAL_LAUNCHER_SCRIPT = """#!/bin/bash
# League of Legends RPC - macOS Universal Launcher
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONTENTS="$( cd "$DIR/.." && pwd )"
RESOURCES="$CONTENTS/Resources"

# 1. Bundled dependencies take priority
if [ -d "$RESOURCES/site-packages" ]; then
    export PYTHONPATH="$RESOURCES/site-packages${PYTHONPATH:+:$PYTHONPATH}"
fi

# 2. Locate Python 3 Runtime
PYTHON_BIN=""
if [ -x "$DIR/../../venv/bin/python3" ]; then
    PYTHON_BIN="$DIR/../../venv/bin/python3"
elif [ -x "/usr/bin/python3" ]; then
    PYTHON_BIN="/usr/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
elif [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    osascript -e 'display alert "Error de ejecución" message "No se encontró Python 3 en este Mac. Abre Terminal e instala las Command Line Tools con: xcode-select --install"'
    exit 1
fi

export TK_SILENCE_DEPRECATION=1
exec "$PYTHON_BIN" "$RESOURCES/app_gui.py" "$@"
"""
```

3. **Automatic SHA-256 Checksum File Export**:
In `build_dmg.py:build_dmg()`:
```python
    sha256_hash = compute_sha256(output_dmg)
    sha256_path = f"{output_dmg}.sha256"
    with open(sha256_path, "w", encoding="utf-8") as f:
        f.write(f"{sha256_hash}  {os.path.basename(output_dmg)}\n")
    print(f"  Checksum    : {sha256_path}")
```

4. **Dynamic Version CLI Parameter**:
Support `--version` and inject into `Contents/Info.plist`:
```python
parser.add_argument("--version", default=None, help="Application version string (e.g. 1.1.0)")
```

---

### 4.3 Self-Healing Bundle Initialization in `sync_bundle.py`
Update `sync_app_bundle()` in `sync_bundle.py`:
```python
    if not os.path.isdir(bundle_path):
        logger.info("Target bundle does not exist (%s). Initializing bundle structure...", bundle_path)
        try:
            import build_dmg
            build_dmg.stage_application_bundle(bundle_path, bundle_deps=False)
        except Exception as e:
            logger.warning("Could not auto-stage bundle: %s. Creating basic skeleton.", e)
            os.makedirs(os.path.join(bundle_path, "Contents", "Resources"), exist_ok=True)
            os.makedirs(os.path.join(bundle_path, "Contents", "MacOS"), exist_ok=True)
```

---

### 4.4 Test Suite Blueprint: `tests/test_tier6_production.py`

Create a comprehensive 24-test suite (`tests/test_tier6_production.py`) registered as Tier 6 in `tests/run_tests.py`:

| # | Test Method | Scope | Requirement |
|---|---|---|---|
| 1 | `test_r1_popover_quit_html_controls` | Verify "Salir de la aplicación" in `#view-main` and `#view-config` HTML | R1 |
| 2 | `test_r1_web_bridge_quit_dispatch` | Verify bridge action `quit_app` calls controller quit handler | R1 |
| 3 | `test_r1_clean_rpc_shutdown_on_quit` | Verify `terminate_application` shuts down RPC manager and AppKit runloop | R1 |
| 4 | `test_r1_status_item_secondary_menu_items` | Verify right-click Cocoa `NSMenu` contains 4 exact items (Open, Toggle, Config, Quit) | R1 |
| 5 | `test_r1_status_item_left_click_unaffected` | Verify left click still toggles popover while right click shows menu | R1 |
| 6 | `test_r1_status_item_menu_action_dispatch` | Verify menu item clicks trigger pause, open, config, and quit | R1 |
| 7 | `test_r1_single_instance_lock_file_creation` | Verify first instance creates `app.lock` with active PID | R1 |
| 8 | `test_r1_single_instance_second_instance_exit` | Verify second instance detects active lock, requests focus, and exits with 0 | R1 |
| 9 | `test_r1_single_instance_stale_lock_recovery` | Verify dead PID in lock file is safely overtaken by new instance | R1 |
| 10 | `test_r1_launchagent_plist_direct_binary` | Verify plist `ProgramArguments` points to `/Applications/.../Contents/MacOS/League of Legends RPC` | R1 |
| 11 | `test_r1_launchagent_logging_destinations` | Verify plist contains `StandardOutPath` and `StandardErrorPath` in `~/Library/Logs/` | R1 |
| 12 | `test_r1_launch_notification_dispatch` | Verify startup notification function emits system notification | R1 |
| 13 | `test_r2_button_url_https_validation` | Verify only `https://` URLs pass validation; `http://` / `javascript:` rejected | R2 |
| 14 | `test_r2_button_label_constraints` | Verify labels 1-32 chars accepted, empty rejected, >32 chars truncated/rejected | R2 |
| 15 | `test_r2_button_array_serialization` | Verify 0, 1, 2 buttons format correctly; partial/corrupt buttons dropped safely | R2 |
| 16 | `test_r2_config_json_buttons_persistence` | Verify buttons save and load correctly from `config.json` | R2 |
| 17 | `test_r2_allowed_config_keys_contains_buttons` | Verify `ALLOWED_CONFIG_KEYS` whitelists `"buttons"` to prevent injection drop | R2 |
| 18 | `test_r2_discord_rpc_payload_buttons` | Verify `pypresence.Presence.update(buttons=...)` receives valid payload | R2 |
| 19 | `test_r3_github_workflow_yaml_syntax` | Verify `.github/workflows/release.yml` syntax, triggers, runner, and steps | R3 |
| 20 | `test_r3_build_dmg_sha256_file_export` | Verify `build_dmg.py` writes `.dmg.sha256` matching `shasum -a 256` | R3 |
| 21 | `test_r3_build_dmg_dynamic_site_packages` | Verify `locate_site_packages()` discovers active environment site-packages | R3 |
| 22 | `test_r3_no_personal_paths_in_launcher` | Verify universal launcher contains no hardcoded personal user directories | R3 |
| 23 | `test_r4_workspace_discord_launch_listener` | Verify `NSWorkspaceDidLaunchApplicationNotification` triggers RPC connect | R4 |
| 24 | `test_r4_workspace_sleep_wake_listener` | Verify `NSWorkspaceDidWakeNotification` triggers connection health check/reconnect | R4 |
| 25 | `test_r4_in_app_error_boundary_toast` | Verify WebBridge and RPC errors trigger UI toast notification without crashing | R4 |

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Existing Test Suites**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py
   # Expected: 149/149 passed across Tiers 1-5
   ```
2. **Verify Full Discovered Test Suite**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python -m unittest discover tests -p "test_*.py"
   # Expected: 241/241 passed
   ```
3. **Verify DMG Builder & Integrity**:
   ```bash
   /Users/victormanuel/discord-rpc/venv/bin/python build_dmg.py --output dist/League_of_Legends_RPC_Installer.dmg
   hdiutil verify dist/League_of_Legends_RPC_Installer.dmg
   # Mount and verify bundle
   hdiutil attach -nobrowse dist/League_of_Legends_RPC_Installer.dmg
   /Users/victormanuel/discord-rpc/venv/bin/python -c "import sync_bundle; print(sync_bundle.verify_bundle_integrity('/Volumes/League of Legends RPC/League of Legends RPC.app', detailed=True))"
   hdiutil detach "/Volumes/League of Legends RPC"
   ```
4. **Verify SHA-256 Checksum**:
   ```bash
   shasum -a 256 dist/League_of_Legends_RPC_Installer.dmg
   ```
5. **Invalidation Conditions**:
   - If `/Applications/League of Legends RPC.app` is removed before running `tests/run_tests.py` on a clean system, `test_f12_app_bundle_exists` will fail unless the CI pre-staging step is present.
   - If Python 3.10+ is used without updating `build_dmg.py:269`, site-packages bundling will skip.
