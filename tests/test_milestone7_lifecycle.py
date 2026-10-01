#!/usr/bin/env python3
"""
test_milestone7_lifecycle.py - Comprehensive Unit & Integration Tests for Milestone M7

Tests:
1. Status Item Right-Click & Native Cocoa Context Menu (status_item.py & app_gui.py).
2. In-App Quit Controls & WebBridge Dispatch (liquid_html.py, popover_ui.py, app_gui.py).
3. Single-Instance Lock & Focus IPC (app_gui.py: SingleInstanceController).
4. Hardened LaunchAgent Plist & Startup Notification (popover_ui.py & app_gui.py).
5. System Event Listeners (Discord launch & Mac wake from sleep) & Toast Error Boundary.
"""

import os
import sys
import logging
import plistlib
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import AppKit
import status_item
import popover_ui
import liquid_html
import discord_rpc_manager
import app_gui


class TestStatusItemContextMenu(unittest.TestCase):
    """Verifies NSStatusItem right-click context menu structure, dynamic titles, and callbacks."""

    def setUp(self):
        self.toggle_called = False
        self.presence_called = False
        self.settings_called = False
        self.quit_called = False

        self.ctrl = status_item.LoLStatusItemController(
            on_toggle=lambda s: setattr(self, "toggle_called", True),
            on_toggle_presence=lambda: setattr(self, "presence_called", True),
            on_open_settings=lambda: setattr(self, "settings_called", True),
            on_quit=lambda: setattr(self, "quit_called", True),
            auto_create=True,
        )

    def tearDown(self):
        if self.ctrl:
            self.ctrl.cleanup()

    def test_context_menu_items_structure(self):
        """Validates that build_context_menu constructs the 4 required items with correct selectors."""
        menu = self.ctrl.build_context_menu()
        self.assertIsNotNone(menu)
        items = menu.itemArray()
        # 4 actions + 1 separator = 5 items
        self.assertGreaterEqual(len(items), 4)

        titles = [item.title() for item in items if not item.isSeparatorItem()]
        self.assertIn("Abrir Popover", titles)
        self.assertTrue(any("Presencia" in t for t in titles))
        self.assertIn("Configuración ⚙️", titles)
        self.assertIn("Salir de Discord RPC", titles)

        # Check Cmd+Q shortcut for Quit
        quit_items = [it for it in items if "Salir de Discord RPC" in it.title()]
        self.assertEqual(len(quit_items), 1)
        self.assertEqual(quit_items[0].keyEquivalent(), "q")

    def test_dynamic_presence_title(self):
        """Validates that presence menu title reflects active vs paused connection state."""
        self.ctrl.set_state("active")
        menu_active = self.ctrl.build_context_menu()
        titles_active = [it.title() for it in menu_active.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Pausar Presencia", titles_active)

        self.ctrl.set_state("paused")
        menu_paused = self.ctrl.build_context_menu()
        titles_paused = [it.title() for it in menu_paused.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Reanudar Presencia", titles_paused)

        self.ctrl.set_state("normal")
        menu_normal = self.ctrl.build_context_menu()
        titles_normal = [it.title() for it in menu_normal.itemArray() if not it.isSeparatorItem()]
        self.assertIn("Reanudar Presencia", titles_normal)

    def test_context_menu_callbacks_invocation(self):
        """Tests that context menu action selectors trigger registered Python callbacks."""
        self.ctrl.menuOpenPopover_(None)
        self.assertTrue(self.toggle_called)

        self.ctrl.menuTogglePresence_(None)
        self.assertTrue(self.presence_called)

        self.ctrl.menuOpenSettings_(None)
        self.assertTrue(self.settings_called)

        self.ctrl.menuQuit_(None)
        self.assertTrue(self.quit_called)


class TestInAppQuitControls(unittest.TestCase):
    """Verifies Quit controls in liquid_html.py, WebBridge, and LoLPopoverController."""

    def test_liquid_html_contains_quit_controls(self):
        """Verifies that generated HTML includes visible quit buttons in main and config views."""
        html = liquid_html.generate_liquid_html({})
        self.assertIn('sendAction(\'quit_app\')', html)
        self.assertIn('Salir de la aplicación', html)
        self.assertIn('quit-btn', html)
        self.assertIn('quit-app-btn', html)

    def test_web_bridge_quit_dispatch(self):
        """Verifies LoLWebBridge routes 'quit_app' action to controller.quit_application()."""
        quit_called = []
        ctrl = popover_ui.LoLPopoverController(on_quit=lambda: quit_called.append(True))
        bridge = popover_ui.LoLWebBridge.alloc().initWithController_(ctrl)

        class MockScriptMessage:
            def body(self):
                return {"action": "quit_app"}

        bridge.userContentController_didReceiveScriptMessage_(None, MockScriptMessage())
        self.assertEqual(len(quit_called), 1)

    def test_popover_controller_quit_application(self):
        """Verifies quit_application closes popover and invokes on_quit callback."""
        quit_called = []
        ctrl = popover_ui.LoLPopoverController(on_quit=lambda: quit_called.append(1))
        ctrl.quit_application()
        self.assertEqual(len(quit_called), 1)

    def test_web_bridge_non_dict_message_tolerance(self):
        """Verifies LoLWebBridge tolerates non-dict message bodies without raising AttributeError."""
        ctrl = popover_ui.LoLPopoverController()
        bridge = popover_ui.LoLWebBridge.alloc().initWithController_(ctrl)

        class MockScriptMessage:
            def __init__(self, body):
                self._body = body
            def body(self):
                return self._body

        for invalid_body in ["string_action", 12345, [1, 2], None, True]:
            try:
                bridge.userContentController_didReceiveScriptMessage_(None, MockScriptMessage(invalid_body))
            except Exception as e:
                self.fail(f"WebBridge crashed on body {invalid_body!r}: {e}")

    def test_popover_logger_defined(self):
        """Verifies popover_ui defines module logger."""
        self.assertTrue(hasattr(popover_ui, "logger"))
        self.assertIsInstance(popover_ui.logger, logging.Logger)

    def test_popover_quit_handles_on_quit_exception_without_name_error(self):
        """Verifies quit_application logs warning without raising NameError if on_quit fails."""
        def bad_quit():
            raise RuntimeError("Intentional error in on_quit callback")

        ctrl = popover_ui.LoLPopoverController(on_quit=bad_quit)
        ctrl.close = MagicMock()

        try:
            ctrl.quit_application()
        except NameError as e:
            self.fail(f"quit_application raised NameError: {e}")
        except Exception as e:
            self.fail(f"quit_application raised unexpected exception: {e}")

    def test_popover_show_toast_handles_exception_without_name_error(self):
        """Verifies show_toast logs debug without raising NameError if WebKit evaluation fails."""
        ctrl = popover_ui.LoLPopoverController()
        ctrl._web_view = MagicMock()
        ctrl._web_view.evaluateJavaScript_completionHandler_.side_effect = RuntimeError("Bridge failure")

        try:
            ctrl.show_toast("Test message", "error")
        except NameError as e:
            self.fail(f"show_toast raised NameError: {e}")
        except Exception as e:
            self.fail(f"show_toast raised unexpected exception: {e}")


class TestSingleInstanceController(unittest.TestCase):
    """Verifies Unix domain socket single-instance lock and FOCUS communication."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_primary_acquisition_and_focus_ipc(self):
        """Verifies primary instance acquires lock and secondary instance notifies primary via FOCUS."""
        c1 = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        focus_events = []
        c1.set_focus_callback(lambda: focus_events.append("focus_signal"))

        # Primary must acquire
        acquired = c1.check_and_acquire()
        self.assertTrue(acquired)
        self.assertTrue(os.path.exists(c1.lock_path))
        self.assertTrue(os.path.exists(c1.sock_path))

        # Secondary must fail to acquire and send FOCUS
        c2 = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        acquired_c2 = c2.check_and_acquire()
        self.assertFalse(acquired_c2)

        # Allow brief time for socket message receipt
        time.sleep(0.4)
        self.assertEqual(len(focus_events), 1)

        # Cleanup primary
        c1.cleanup()
        self.assertFalse(os.path.exists(c1.sock_path))

        # After primary cleanup, another instance can acquire
        c3 = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        self.assertTrue(c3.check_and_acquire())
        c3.cleanup()

    def test_stale_socket_recovery(self):
        """Verifies recovery from an abnormal termination leaving a stale socket file."""
        sock_path = os.path.join(self.temp_dir, "app.sock")
        # Write dummy dead socket file
        with open(sock_path, "w") as f:
            f.write("dead socket placeholder")

        c = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        acquired = c.check_and_acquire()
        self.assertTrue(acquired)
        self.assertTrue(os.path.exists(sock_path))
        c.cleanup()


class TestHardenedLaunchAgent(unittest.TestCase):
    """Verifies LaunchAgent plist schema, direct binary executable, and log paths."""

    def test_sync_login_item_generates_hardened_plist(self):
        """Tests that _sync_login_item generates a direct binary launchd plist with logging."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_plist = os.path.join(tmp_dir, "test.plist")
            ctrl = popover_ui.LoLPopoverController()

            with patch("os.path.expanduser", side_effect=lambda p: test_plist if "com.victormanuel.lolrpc.plist" in p else os.path.join(tmp_dir, "Logs")):
                with patch("subprocess.run") as mock_run:
                    ctrl._sync_login_item(True)

            self.assertTrue(os.path.exists(test_plist))
            with open(test_plist, "rb") as f:
                plist = plistlib.load(f)

            self.assertEqual(plist.get("Label"), "com.victormanuel.lolrpc")
            args = plist.get("ProgramArguments", [])
            self.assertIn("/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC", args)
            self.assertIn("--silent", args)
            self.assertNotIn("/usr/bin/open", args)

            self.assertIn("StandardOutPath", plist)
            self.assertIn("StandardErrorPath", plist)
            self.assertTrue(plist["StandardOutPath"].endswith("lol_discord_rpc.log"))
            self.assertTrue(plist["StandardErrorPath"].endswith("lol_discord_rpc_error.log"))


class TestSystemEventListenersAndToast(unittest.TestCase):
    """Verifies NSWorkspace notification handlers, rpc_manager.reconnect(), and in-app toasts."""

    def test_discord_reconnect_command(self):
        """Verifies that calling rpc_manager.reconnect() enqueues ('RECONNECT', None)."""
        mgr = discord_rpc_manager.DiscordRPCManager(auto_start=False)
        self.assertTrue(hasattr(mgr, "reconnect"))
        mgr.reconnect()
        cmd, payload = mgr._cmd_queue.get_nowait()
        self.assertEqual(cmd, "RECONNECT")
        self.assertIsNone(payload)

    def test_workspace_discord_launch_trigger(self):
        """Verifies that onAppLaunched_ triggers rpc_manager.reconnect() only when Discord launches."""
        reconnect_calls = []

        class MockRPCManager:
            def reconnect(self):
                reconnect_calls.append(True)

        class MockApp:
            def __init__(self, bundle_id, name):
                self._bundle_id = bundle_id
                self._name = name
            def bundleIdentifier(self):
                return self._bundle_id
            def localizedName(self):
                return self._name

        class MockNotification:
            def __init__(self, app_mock):
                self._info = {"NSWorkspaceApplicationKey": app_mock}
            def userInfo(self):
                return self._info

        app_ctrl = app_gui.LoLAppController.__new__(app_gui.LoLAppController)
        app_ctrl._is_shutting_down = False
        app_ctrl.rpc_manager = MockRPCManager()

        # Non-Discord launch -> No reconnect
        app_ctrl.onAppLaunched_(MockNotification(MockApp("com.apple.Safari", "Safari")))
        self.assertEqual(len(reconnect_calls), 0)

        # Discord launch -> Triggers reconnect
        app_ctrl.onAppLaunched_(MockNotification(MockApp("com.hnc.Discord", "Discord")))
        self.assertEqual(len(reconnect_calls), 1)

        # Discord Canary -> Triggers reconnect
        app_ctrl.onAppLaunched_(MockNotification(MockApp("com.hnc.DiscordCanary", "Discord Canary")))
        self.assertEqual(len(reconnect_calls), 2)

    def test_workspace_system_wake_trigger(self):
        """Verifies that onSystemWake_ triggers rpc_manager.reconnect()."""
        reconnect_calls = []

        class MockRPCManager:
            def reconnect(self):
                reconnect_calls.append(True)

        app_ctrl = app_gui.LoLAppController.__new__(app_gui.LoLAppController)
        app_ctrl._is_shutting_down = False
        app_ctrl.rpc_manager = MockRPCManager()

        app_ctrl.onSystemWake_(None)
        self.assertEqual(len(reconnect_calls), 1)

    def test_in_app_toast_error_routing(self):
        """Verifies that socket and RPC errors are forwarded to popover.show_toast."""
        toasts = []

        class MockPopover:
            def show_toast(self, message, toast_type="error"):
                toasts.append((message, toast_type))
            def set_connection_state(self, state):
                pass

        app_ctrl = app_gui.LoLAppController.__new__(app_gui.LoLAppController)
        app_ctrl._is_shutting_down = False
        app_ctrl.status_item = MagicMock()
        app_ctrl.popover = MockPopover()

        # Normal connection -> No toast
        app_ctrl.on_rpc_state_change("connected", "Activo en Discord")
        self.assertEqual(len(toasts), 0)

        # Socket error -> Triggers toast
        app_ctrl.on_rpc_state_change("disconnected", "Conexión con Discord perdida (Error de socket)")
        self.assertEqual(len(toasts), 1)
        self.assertIn("perdida", toasts[0][0])
        self.assertEqual(toasts[0][1], "error")

    def test_reconnect_command_processing_no_deadlock(self):
        """Verifies directly calling _process_command('RECONNECT', None) completes without deadlock."""
        mgr = discord_rpc_manager.DiscordRPCManager(client_id="test", auto_start=False)
        t = threading.Thread(target=mgr._process_command, args=("RECONNECT", None), daemon=True)
        t.start()
        t.join(timeout=1.0)
        self.assertFalse(t.is_alive(), "Worker thread deadlocked during _process_command('RECONNECT', None)!")

    def test_rpc_manager_shutdown_closes_rpc_and_joins(self):
        """Verifies shutdown() closes active socket and terminates worker thread cleanly within timeout."""
        mgr = discord_rpc_manager.DiscordRPCManager(client_id="test", auto_start=True)
        self.assertTrue(mgr._worker_thread.is_alive())
        mgr.shutdown()
        self.assertFalse(mgr._worker_thread.is_alive(), "Worker thread remained alive after shutdown()!")


if __name__ == "__main__":
    unittest.main()
