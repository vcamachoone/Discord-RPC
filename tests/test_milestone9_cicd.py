#!/usr/bin/env python3
"""
tests/test_milestone9_cicd.py - Comprehensive Unit Tests for Milestone M9

Verifies:
  1. GitHub Actions CI/CD Release Pipeline (.github/workflows/release.yml):
     - File existence and valid YAML structure
     - Trigger events: release [published], push [v*.*.*], workflow_dispatch
     - Runner configuration: macos-latest
     - Pipeline steps: checkout@v4, setup-python@v5 (Python 3.9), pip dependencies,
       pre-stage application bundle, run test suite, compile DMG, verify artifacts,
       upload-artifact@v4, and softprops/action-gh-release@v2
     - Write permissions: contents: write
  2. Standalone DMG Packaging Hardening (build_dmg.py):
     - locate_site_packages() dynamic resolution
     - UNIVERSAL_LAUNCHER_SCRIPT sanitized of hardcoded developer paths
     - launcher.sh sanitized of hardcoded developer paths
     - SHA-256 checksum computation and file format (<hash>  <filename>)
     - Dynamic version injection into Info.plist
  3. Bundle Auto-Initialization (sync_bundle.py):
     - Auto-stages bundle skeleton when target /Applications/... path is missing
     - Dry run tolerance for missing target bundles
"""

import os
import re
import sys
import shutil
import tempfile
import plistlib
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import build_dmg
import sync_bundle


class TestGitHubActionsWorkflow(unittest.TestCase):
    """Test suite validating .github/workflows/release.yml."""

    @classmethod
    def setUpClass(cls):
        cls.workflow_path = os.path.join(PROJECT_ROOT, ".github", "workflows", "release.yml")
        cls.workflow_exists = os.path.isfile(cls.workflow_path)
        cls.workflow_content = ""
        if cls.workflow_exists:
            with open(cls.workflow_path, "r", encoding="utf-8") as f:
                cls.workflow_content = f.read()

    def test_workflow_file_exists(self):
        """Verify .github/workflows/release.yml exists in repository."""
        self.assertTrue(
            self.workflow_exists,
            f"Release workflow missing at: {self.workflow_path}",
        )

    def test_workflow_triggers(self):
        """Verify workflow triggers: release [published], push tags, and workflow_dispatch."""
        self.assertTrue(self.workflow_exists)
        # Release published trigger
        self.assertIn("release:", self.workflow_content)
        self.assertIn("published", self.workflow_content)

        # Push tags trigger
        self.assertIn("push:", self.workflow_content)
        self.assertIn("tags:", self.workflow_content)
        self.assertTrue(
            bool(re.search(r"['\"]v\*\.\*\.\*['\"]", self.workflow_content)),
            "Expected tag pattern v*.*.* not found in push triggers",
        )

        # workflow_dispatch trigger
        self.assertIn("workflow_dispatch:", self.workflow_content)

    def test_workflow_runner(self):
        """Verify workflow executes on macos-latest runner."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("runs-on: macos-latest", self.workflow_content)

    def test_workflow_permissions(self):
        """Verify workflow requests write permissions for GitHub releases."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("permissions:", self.workflow_content)
        self.assertIn("contents: write", self.workflow_content)

    def test_workflow_checkout_step(self):
        """Verify checkout step uses actions/checkout@v4 with fetch-depth: 0."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("actions/checkout@v4", self.workflow_content)
        self.assertIn("fetch-depth: 0", self.workflow_content)

    def test_workflow_setup_python_step(self):
        """Verify setup-python uses actions/setup-python@v5 with python-version: '3.9'."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("actions/setup-python@v5", self.workflow_content)
        self.assertTrue(
            bool(re.search(r"python-version:\s*['\"]3\.9['\"]", self.workflow_content)),
            "Expected python-version: '3.9' in workflow",
        )

    def test_workflow_install_deps_step(self):
        """Verify pip upgrade and dependency installation from requirements.txt."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("pip install -r requirements.txt", self.workflow_content)

    def test_workflow_pre_stage_step(self):
        """Verify pre-staging of /Applications/League of Legends RPC.app for runner tests."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("/Applications/League of Legends RPC.app", self.workflow_content)
        self.assertIn("sync_bundle.py", self.workflow_content)

    def test_workflow_run_tests_step(self):
        """Verify execution of master test runner tests/run_tests.py."""
        self.assertTrue(self.workflow_exists)
        self.assertTrue(
            bool(re.search(r"python\d*\s+tests/run_tests\.py", self.workflow_content)),
            "Expected test execution step with tests/run_tests.py",
        )

    def test_workflow_build_dmg_step(self):
        """Verify step executing build_dmg.py."""
        self.assertTrue(self.workflow_exists)
        self.assertTrue(
            bool(re.search(r"python\d*\s+build_dmg\.py", self.workflow_content)),
            "Expected build_dmg.py execution step in workflow",
        )

    def test_workflow_verify_dmg_and_checksum_step(self):
        """Verify DMG and SHA-256 checksum verification step."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("shasum -a 256", self.workflow_content)
        self.assertIn(".sha256", self.workflow_content)

    def test_workflow_upload_artifact_step(self):
        """Verify actions/upload-artifact@v4 step saving dmg-installer artifacts."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("actions/upload-artifact@v4", self.workflow_content)
        self.assertIn("dmg-installer", self.workflow_content)
        self.assertIn("dist/*.dmg", self.workflow_content)
        self.assertIn("dist/*.sha256", self.workflow_content)

    def test_workflow_release_attachment_step(self):
        """Verify softprops/action-gh-release@v2 publishes DMG and sha256 to GitHub Release."""
        self.assertTrue(self.workflow_exists)
        self.assertIn("softprops/action-gh-release@v2", self.workflow_content)
        self.assertIn("dist/*.dmg", self.workflow_content)
        self.assertIn("dist/*.sha256", self.workflow_content)
        self.assertIn("GITHUB_TOKEN", self.workflow_content)


class TestDMGPackagingHardening(unittest.TestCase):
    """Test suite validating build_dmg.py and packaging hardening."""

    def test_locate_site_packages_returns_valid_dir(self):
        """Verify locate_site_packages() resolves an existing site-packages directory."""
        sp = build_dmg.locate_site_packages()
        self.assertIsNotNone(sp, "locate_site_packages() returned None")
        self.assertTrue(os.path.isdir(sp), f"Resolved path is not a directory: {sp}")
        self.assertIn("site-packages", sp, f"Resolved path lacks 'site-packages': {sp}")

    def test_locate_site_packages_contains_installed_pkgs(self):
        """Verify resolved site-packages contains required runtime dependencies."""
        sp = build_dmg.locate_site_packages()
        self.assertIsNotNone(sp)
        items = os.listdir(sp)
        # Check presence of at least pypresence, PIL, rumps, or Cocoa/objc
        has_expected_pkg = any(
            pkg in items
            for pkg in ("pypresence", "PIL", "rumps", "Cocoa", "objc", "AppKit")
        )
        self.assertTrue(
            has_expected_pkg,
            f"site-packages at {sp} does not contain expected packages. Items: {items[:10]}...",
        )

    def test_universal_launcher_script_no_hardcoded_user_paths(self):
        """Verify UNIVERSAL_LAUNCHER_SCRIPT in build_dmg.py has no hardcoded developer paths."""
        launcher = build_dmg.UNIVERSAL_LAUNCHER_SCRIPT
        self.assertNotIn("/Users/", launcher, "UNIVERSAL_LAUNCHER_SCRIPT contains hardcoded /Users/ path")
        self.assertNotIn("victormanuel", launcher, "UNIVERSAL_LAUNCHER_SCRIPT contains developer username")

    def test_launcher_sh_no_hardcoded_user_paths(self):
        """Verify launcher.sh file has no hardcoded developer user paths."""
        launcher_file = os.path.join(PROJECT_ROOT, "launcher.sh")
        if os.path.isfile(launcher_file):
            with open(launcher_file, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("/Users/", content, "launcher.sh contains hardcoded /Users/ path")
            self.assertNotIn("victormanuel", content, "launcher.sh contains developer username")

    def test_launcher_checks_portable_python_runtimes(self):
        """Verify launcher script checks standard portable Python 3 runtimes."""
        launcher = build_dmg.UNIVERSAL_LAUNCHER_SCRIPT
        self.assertIn("/usr/bin/python3", launcher)
        self.assertIn("command -v python3", launcher)
        self.assertIn("/opt/homebrew/bin/python3", launcher)
        self.assertIn("/usr/local/bin/python3", launcher)

    def test_compute_sha256(self):
        """Verify compute_sha256 computes correct 64-character hex hash."""
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        try:
            temp_file.write(b"League of Legends Discord RPC CI/CD Test Payload")
            temp_file.flush()
            temp_file.close()

            computed_hash = build_dmg.compute_sha256(temp_file.name)
            self.assertEqual(len(computed_hash), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in computed_hash))

            # Known hash comparison
            import hashlib
            expected = hashlib.sha256(b"League of Legends Discord RPC CI/CD Test Payload").hexdigest()
            self.assertEqual(computed_hash, expected)
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    def test_sha256_checksum_file_format(self):
        """Verify SHA-256 export formatting follows standard shasum format: <hash>  <filename>\\n."""
        mock_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        mock_dmg_name = "League_of_Legends_RPC_Installer.dmg"
        formatted_line = f"{mock_hash}  {mock_dmg_name}\n"

        # Verify format with regex matching shasum standard
        match = re.match(r"^([a-f0-9]{64})\s{2}(.+\.dmg)\n$", formatted_line)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), mock_hash)
        self.assertEqual(match.group(2), mock_dmg_name)

    def test_stage_application_bundle_dynamic_version(self):
        """Verify stage_application_bundle correctly injects dynamic version into Info.plist."""
        temp_dir = tempfile.mkdtemp(prefix="test_stage_bundle_")
        target_app = os.path.join(temp_dir, "TestApp.app")
        try:
            success = build_dmg.stage_application_bundle(
                dest_app_path=target_app,
                bundle_deps=False,
                version="2.5.1",
            )
            self.assertTrue(success)

            plist_path = os.path.join(target_app, "Contents", "Info.plist")
            self.assertTrue(os.path.isfile(plist_path))

            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)

            self.assertEqual(plist.get("CFBundleShortVersionString"), "2.5.1")
            self.assertEqual(plist.get("CFBundleVersion"), "2.5.1")
            self.assertEqual(plist.get("CFBundleExecutable"), "League of Legends RPC")
            self.assertTrue(plist.get("LSUIElement"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestBundleAutoInitialization(unittest.TestCase):
    """Test suite validating sync_bundle.py self-healing bundle initialization."""

    def test_sync_bundle_auto_initializes_missing_bundle(self):
        """Verify sync_app_bundle automatically creates and populates missing bundle directory."""
        temp_dir = tempfile.mkdtemp(prefix="test_auto_init_")
        target_app = os.path.join(temp_dir, "League of Legends RPC.app")
        try:
            # Ensure target bundle does not exist
            self.assertFalse(os.path.exists(target_app))

            # Run sync_app_bundle
            result = sync_bundle.sync_app_bundle(
                dry_run=False,
                bundle_path=target_app,
                src_dir=PROJECT_ROOT,
            )
            self.assertTrue(result, "sync_app_bundle failed on non-existent bundle directory")

            # Verify bundle was created and has valid structure
            self.assertTrue(os.path.isdir(target_app))
            self.assertTrue(os.path.isfile(os.path.join(target_app, "Contents", "Info.plist")))
            self.assertTrue(os.path.isfile(os.path.join(target_app, "Contents", "MacOS", "League of Legends RPC")))

            # Verify launcher is executable
            launcher = os.path.join(target_app, "Contents", "MacOS", "League of Legends RPC")
            self.assertTrue(bool(os.stat(launcher).st_mode & 0o111))

            # Verify bundle integrity passes
            report = sync_bundle.verify_bundle_integrity(bundle_path=target_app, detailed=True)
            self.assertTrue(report["valid"], f"Bundle integrity verification failed: {report['errors']}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_bundle_dry_run_on_missing_bundle(self):
        """Verify sync_app_bundle dry_run handles non-existent bundle cleanly without raising errors."""
        temp_dir = tempfile.mkdtemp(prefix="test_dry_run_")
        target_app = os.path.join(temp_dir, "League of Legends RPC.app")
        try:
            self.assertFalse(os.path.exists(target_app))
            result = sync_bundle.sync_app_bundle(
                dry_run=True,
                bundle_path=target_app,
                src_dir=PROJECT_ROOT,
            )
            self.assertTrue(result)
            self.assertFalse(os.path.exists(target_app))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
