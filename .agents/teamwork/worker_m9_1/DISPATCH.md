## 2026-09-30T04:46:48Z
From: 6be08381-ce37-4c0e-a1fe-5103a58e1ab8
Priority: MESSAGE_PRIORITY_HIGH

You are worker_m9_1.
Your working directory is: /Users/victormanuel/discord-rpc/.agents/teamwork/worker_m9_1
Project root: /Users/victormanuel/discord-rpc
Authoritative requirements: /Users/victormanuel/discord-rpc/.agents/teamwork/ORIGINAL_REQUEST.md (specifically section ## Follow-up — 2026-09-29T23:10:58Z, Requirement R3).
Read the comprehensive survey blueprint at:
/Users/victormanuel/discord-rpc/.agents/teamwork/explorer_followup_3/handoff.md
Also consult /Users/victormanuel/discord-rpc/.agents/teamwork/PROJECT.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

SCOPE OF MILESTONE M9 (Requirement R3: Automated GitHub Actions CI/CD Release Pipeline & Standalone DMG Packaging):
1. GitHub Actions Workflow (.github/workflows/release.yml):
   - Create .github/workflows/release.yml.
   - Triggers: release (types: [published]), push (tags: ['v*.*.*']), and workflow_dispatch.
   - Runner: macos-latest.
   - Steps:
     * actions/checkout@v4 (fetch-depth: 0)
     * actions/setup-python@v5 with python-version: '3.9', cache: 'pip'
     * Install dependencies: python -m pip install --upgrade pip; pip install -r requirements.txt
     * Pre-stage Application Bundle: initialize /Applications/League of Legends RPC.app skeleton and sync so that existing test assertions (e.g. test_f12_app_bundle_exists) and sync_bundle.py pass cleanly on fresh ephemeral GitHub runners.
     * Run full test suite: python tests/run_tests.py across all tiers (149 tests).
     * Compile DMG: python build_dmg.py.
     * Verify DMG and SHA-256 artifacts exist in dist/.
     * Upload build artifacts: actions/upload-artifact@v4 (name: dmg-installer, path: dist/*.dmg and dist/*.sha256).
     * Attach release assets: softprops/action-gh-release@v2 with files dist/*.dmg and dist/*.sha256.
2. DMG Packaging Hardening (build_dmg.py & sync_bundle.py):
   - In build_dmg.py:
     * Replace hardcoded 'venv/lib/python3.9/site-packages' with dynamic locate_site_packages() using sysconfig.get_path('purelib') with fallback paths.
     * Clean UNIVERSAL_LAUNCHER_SCRIPT: remove developer path /Users/victormanuel/discord-rpc/venv/bin/python3. Use portable dynamic resolution (command -v python3, /usr/bin/python3, framework python).
     * Automatically write dist/League_of_Legends_RPC_Installer.dmg.sha256 file alongside the DMG.
     * Support bundle initialization in sync_bundle.py if /Applications/League of Legends RPC.app does not already exist.
3. Testing & Verification:
   - Add tests/test_milestone9_cicd.py:
     * Validate .github/workflows/release.yml syntax, trigger events, macos-latest runner, test step, build_dmg step, and release upload.
     * Validate build_dmg.py: locate_site_packages() resolves correctly, launcher has no hardcoded developer paths, SHA-256 file export format.
   - Run tests:
     * /Users/victormanuel/discord-rpc/venv/bin/python -m unittest tests/test_milestone9_cicd.py
     * /Users/victormanuel/discord-rpc/venv/bin/python tests/run_tests.py (149/149 pass)
     * Execute build_dmg.py and verify resulting DMG and SHA-256 checksum file in dist/.
   - Synchronize bundle using sync_bundle.py.

Produce a detailed handoff report in your working directory at:
/Users/victormanuel/discord-rpc/.agents/teamwork/worker_m9_1/handoff.md
Send a message when finished.
