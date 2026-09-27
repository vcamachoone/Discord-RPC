#!/usr/bin/env python3
"""
test_milestone4.py - Dedicated Unit Tests for Milestone 4 (app_gui.py & sync_bundle.py)
"""

import os
import shutil
import tempfile
import unittest
import plistlib
from unittest.mock import MagicMock, patch

import sync_bundle
import app_gui
from discord_rpc_manager import RPCState


class TestSyncBundle(unittest.TestCase):
    """Deep verification of sync_bundle module functions and integrity checks."""

    def test_verify_bundle_integrity_on_real_bundle(self):
        """Verify that the real /Applications bundle passes integrity check."""
        self.assertTrue(sync_bundle.verify_bundle_integrity())

    def test_verify_bundle_integrity_detailed(self):
        """Verify detailed integrity report contents."""
        report = sync_bundle.verify_bundle_integrity(detailed=True)
        self.assertIsInstance(report, dict)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])
        self.assertTrue(report["checks"]["bundle_exists"])
        self.assertTrue(report["checks"]["info_plist"])
        self.assertTrue(report["checks"]["launcher_executable"])
        self.assertTrue(report["checks"]["app_icon"])
        self.assertTrue(report["checks"]["resources_present"])

    def test_verify_bundle_integrity_nonexistent_path(self):
        """Verify that a nonexistent bundle path returns False and reports error."""
        nonexistent = "/tmp/non_existent_bundle_12345.app"
        self.assertFalse(sync_bundle.verify_bundle_integrity(bundle_path=nonexistent))
        report = sync_bundle.verify_bundle_integrity(bundle_path=nonexistent, detailed=True)
        self.assertFalse(report["valid"])
        self.assertIn("does not exist", report["errors"][0])

    def test_verify_bundle_integrity_missing_plist(self):
        """Verify failure when Info.plist is missing."""
        temp_bundle = tempfile.mkdtemp(prefix="test_bundle_")
        try:
            os.makedirs(os.path.join(temp_bundle, "Contents", "Resources"), exist_ok=True)
            report = sync_bundle.verify_bundle_integrity(bundle_path=temp_bundle, detailed=True)
            self.assertFalse(report["valid"])
            self.assertFalse(report["checks"]["info_plist"])
        finally:
            shutil.rmtree(temp_bundle, ignore_errors=True)

    def test_sync_app_bundle_dry_run(self):
        """Verify dry run mode does not fail and returns True."""
        result = sync_bundle.sync_app_bundle(dry_run=True)
        self.assertTrue(result)

    def test_sync_to_applications_alias(self):
        """Verify sync_to_applications is a functioning alias."""
        result = sync_bundle.sync_to_applications(dry_run=True)
        self.assertTrue(result)

    def test_sync_app_bundle_to_temp_dir(self):
        """Verify full synchronization into a mock bundle directory."""
        temp_dir = tempfile.mkdtemp(prefix="mock_bundle_")
        try:
            # Create minimal bundle structure
            contents = os.path.join(temp_dir, "Contents")
            macos = os.path.join(contents, "MacOS")
            resources = os.path.join(contents, "Resources")
            os.makedirs(macos, exist_ok=True)
            os.makedirs(resources, exist_ok=True)

            # Create mock Info.plist
            plist_data = {
                "CFBundleExecutable": "League of Legends RPC",
                "CFBundleIdentifier": "com.victormanuel.lolrpc",
                "LSUIElement": True,
            }
            with open(os.path.join(contents, "Info.plist"), "wb") as f:
                plistlib.dump(plist_data, f)

            # Create mock launcher
            launcher = os.path.join(macos, "League of Legends RPC")
            with open(launcher, "w") as f:
                f.write("#!/bin/bash\nexit 0\n")
            os.chmod(launcher, 0o644)  # non-executable initially

            # Create mock AppIcon.icns
            with open(os.path.join(resources, "AppIcon.icns"), "wb") as f:
                f.write(b"icns\x00\x00\x00\x00")

            # Run sync
            success = sync_bundle.sync_app_bundle(dry_run=False, bundle_path=temp_dir)
            self.assertTrue(success)

            # Verify permissions updated to 0o755
            mode = os.stat(launcher).st_mode
            self.assertTrue(bool(mode & 0o111), "Launcher should be executable after sync")

            # Verify files copied
            for mod in sync_bundle.RUNTIME_MODULES:
                self.assertTrue(
                    os.path.isfile(os.path.join(resources, mod)),
                    f"Module {mod} was not copied to bundle Resources",
                )

            # Verify assets directory copied
            assets_dir = os.path.join(resources, "assets")
            self.assertTrue(os.path.isdir(assets_dir))
            self.assertTrue(os.path.isfile(os.path.join(assets_dir, "menubar_normal.png")))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestAppGuiController(unittest.TestCase):
    """Deep verification of LoLAppController and UI coordination logic."""

    def setUp(self):
        self.controller = app_gui.LoLAppController(auto_start=False)

    def tearDown(self):
        if self.controller:
            self.controller.quit()

    def test_controller_initialization(self):
        """Verify that controller initializes status item, popover, and RPC manager."""
        self.assertIsNotNone(self.controller.status_item)
        self.assertIsNotNone(self.controller.rpc_manager)
        self.assertIsNotNone(self.controller.popover)
        self.assertEqual(self.controller.status_item.get_current_state(), "normal")

    def test_initial_config_synced_to_rpc_manager(self):
        """Verify that popover initial state was sent to rpc_manager command queue."""
        # Check command queue contains CONFIG_CHANGE
        cmd, payload = self.controller.rpc_manager._cmd_queue.get_nowait()
        self.assertEqual(cmd, "CONFIG_CHANGE")
        self.assertEqual(payload["mode"], "oficial")
        self.assertEqual(payload["champion_name"], "Malzahar")
        self.assertEqual(payload["rank_text"], "Oro II")
        self.assertTrue(payload["autoreset"])

    def test_rpc_state_connected_updates_menubar_and_popover(self):
        """Verify that RPC connected state changes status item to 'active'."""
        self.controller.on_rpc_state_change(RPCState.CONNECTED, "Activo en Discord")
        self.assertEqual(self.controller.status_item.get_current_state(), "active")
        self.assertTrue(self.controller.popover.is_presence_active())

    def test_rpc_state_paused_updates_menubar_and_popover(self):
        """Verify that RPC paused state changes status item to 'paused'."""
        self.controller.on_rpc_state_change(RPCState.PAUSED, "Presencia pausada")
        self.assertEqual(self.controller.status_item.get_current_state(), "paused")
        self.assertFalse(self.controller.popover.is_presence_active())

    def test_rpc_state_disconnected_updates_menubar_normal(self):
        """Verify that RPC disconnected state changes status item to 'normal'."""
        self.controller.on_rpc_state_change(RPCState.DISCONNECTED, "Esperando a Discord...")
        self.assertEqual(self.controller.status_item.get_current_state(), "normal")

    def test_toggle_popover_call(self):
        """Verify toggle_popover delegates to popover controller safely."""
        with patch.object(self.controller.popover, "toggle") as mock_toggle:
            self.controller.toggle_popover()
            mock_toggle.assert_called_once()

    def test_match_reset_callback(self):
        """Verify on_match_reset does not raise exceptions."""
        try:
            self.controller.on_match_reset(123456789)
        except Exception as e:
            self.fail(f"on_match_reset raised exception: {e}")

    def test_mode_and_action_callbacks(self):
        """Verify mode, action, and autorun callbacks execute safely."""
        self.controller.on_mode_change("detallado")
        self.controller.on_action_toggle(False)
        self.controller.on_autorun_toggle(True)

    def test_clean_shutdown_idempotent(self):
        """Verify quit() is idempotent and handles multiple invocations safely."""
        self.controller.quit()
        self.assertTrue(self.controller._is_shutting_down)
        # Second invocation should be a no-op
        self.controller.quit()

    def test_get_asset_path(self):
        """Verify get_asset_path resolves existing files and fallbacks."""
        path = app_gui.get_asset_path("menubar_normal.png")
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
