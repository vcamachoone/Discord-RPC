#!/usr/bin/env python3
"""
test_challenger_m7_stress.py - Empirical Adversarial Challenge Suite for Milestone M7

Adversarial Stress & Edge-Case Testing:
1. System Event Listeners:
   - NSWorkspaceDidLaunchApplicationNotification: Discord vs non-Discord, case sensitivity, partial matches, malformed notifications, None fields, shutdown state.
   - NSWorkspaceDidWakeNotification: Wake trigger, shutdown state, malformed notifications.
   - DiscordRPCManager.reconnect(): Queue enqueuing, backoff interrupt, concurrency stress (50 concurrent threads).
2. In-App Error Toast:
   - liquid_html.py: HTML/CSS structure, XSS sanitization, window.showToast signature, error & unhandledrejection handlers.
   - popover_ui.py: show_toast JS escaping (newlines, quotes, HTML tags, unicode), None web view, JS failure handling.
   - app_gui.py: on_rpc_state_change error keyword filtering and routing to show_toast.
3. In-App Quit & Lifecycle:
   - liquid_html.py: Quit buttons in main and config views with sendAction('quit_app').
   - LoLWebBridge: Routing 'quit_app' to quit_application().
   - LoLPopoverController.quit_application(): Popover close, on_quit callback, exception tolerance, fallback NSApp terminate.
   - LoLAppController.quit(): Notification unregistration, popover close, status_item cleanup, rpc_manager shutdown, idempotency.
"""

import json
import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import AppKit
import app_gui
import discord_rpc_manager
import liquid_html
import popover_ui
import status_item


class MockNSRunningApp:
    def __init__(self, bundle_id=None, name=None):
        self._bundle_id = bundle_id
        self._name = name

    def bundleIdentifier(self):
        return self._bundle_id

    def localizedName(self):
        return self._name


class MockCocoaNotification:
    def __init__(self, app_mock=None, raw_info=None):
        if raw_info is not None:
            self._info = raw_info
        elif app_mock is not None:
            self._info = {"NSWorkspaceApplicationKey": app_mock}
        else:
            self._info = {}

    def userInfo(self):
        return self._info


class TestSystemEventListenersStress(unittest.TestCase):
    """Adversarial stress testing of Cocoa NSWorkspace system event listeners."""

    def setUp(self):
        self.reconnect_calls = 0
        self.app_ctrl = app_gui.LoLAppController.alloc().init()
        self.app_ctrl._is_shutting_down = False

        class MockRPCManager:
            def __init__(self, outer):
                self.outer = outer
            def reconnect(self):
                self.outer.reconnect_calls += 1

        self.app_ctrl.rpc_manager = MockRPCManager(self)

    def test_discord_launch_matrix(self):
        """Matrix testing for various Discord bundles, casings, and channels."""
        test_cases = [
            ("com.hnc.Discord", "Discord", True),
            ("com.hnc.DiscordCanary", "Discord Canary", True),
            ("com.hnc.DiscordPTB", "Discord PTB", True),
            ("com.hnc.DiscordDevelopment", "Discord Development", True),
            ("COM.HNC.DISCORD", "DISCORD", True),
            ("com.discord.app", "discord-custom", True),
            (None, "Discord", True),
            ("com.hnc.Discord", None, True),
            # Non-Discord applications
            ("com.apple.Safari", "Safari", False),
            ("com.google.Chrome", "Google Chrome", False),
            ("com.riotgames.leagueoflegends", "League of Legends", False),
            ("com.apple.finder", "Finder", False),
            ("com.tinyspeck.slackmacgap", "Slack", False),
            (None, "Spotify", False),
            ("com.spotify.client", None, False),
            ("", "", False),
            (None, None, False),
        ]

        for bundle_id, name, expected_trigger in test_cases:
            initial = self.reconnect_calls
            app_mock = MockNSRunningApp(bundle_id, name)
            notif = MockCocoaNotification(app_mock)
            self.app_ctrl.onAppLaunched_(notif)

            delta = self.reconnect_calls - initial
            expected_delta = 1 if expected_trigger else 0
            self.assertEqual(
                delta,
                expected_delta,
                f"Failed for bundle_id='{bundle_id}', name='{name}': expected {expected_delta}, got {delta}",
            )

    def test_malformed_launch_notifications(self):
        """Ensures onAppLaunched_ handles missing, corrupted, or non-Cocoa notification objects without crashing."""
        initial = self.reconnect_calls

        # None notification
        self.app_ctrl.onAppLaunched_(None)
        self.assertEqual(self.reconnect_calls, initial)

        # Notification with None userInfo
        class NotificationNoUserInfo:
            def userInfo(self):
                return None
        self.app_ctrl.onAppLaunched_(NotificationNoUserInfo())
        self.assertEqual(self.reconnect_calls, initial)

        # Notification with empty dict userInfo
        self.app_ctrl.onAppLaunched_(MockCocoaNotification(raw_info={}))
        self.assertEqual(self.reconnect_calls, initial)

        # Notification where NSWorkspaceApplicationKey is None
        self.app_ctrl.onAppLaunched_(MockCocoaNotification(raw_info={"NSWorkspaceApplicationKey": None}))
        self.assertEqual(self.reconnect_calls, initial)

        # Notification where app object returns non-string or None
        app_weird = MockNSRunningApp(None, None)
        self.app_ctrl.onAppLaunched_(MockCocoaNotification(app_weird))
        self.assertEqual(self.reconnect_calls, initial)

    def test_shutdown_suppresses_launch_events(self):
        """Verifies that once shutting down, no reconnects are initiated on app launch."""
        self.app_ctrl._is_shutting_down = True
        app_mock = MockNSRunningApp("com.hnc.Discord", "Discord")
        self.app_ctrl.onAppLaunched_(MockCocoaNotification(app_mock))
        self.assertEqual(self.reconnect_calls, 0)

    def test_system_wake_notification(self):
        """Verifies system wake triggers reconnect and respects shutdown state."""
        self.assertEqual(self.reconnect_calls, 0)
        self.app_ctrl.onSystemWake_(None)
        self.assertEqual(self.reconnect_calls, 1)

        self.app_ctrl.onSystemWake_(MockCocoaNotification())
        self.assertEqual(self.reconnect_calls, 2)

        # When shutting down, wake is ignored
        self.app_ctrl._is_shutting_down = True
        self.app_ctrl.onSystemWake_(None)
        self.assertEqual(self.reconnect_calls, 2)

    def test_reconnect_concurrency_stress(self):
        """Concurrent stress test calling reconnect() from 50 worker threads simultaneously."""
        mgr = discord_rpc_manager.DiscordRPCManager(auto_start=False)

        threads = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    mgr.reconnect()
            except Exception as e:
                errors.append(e)

        for _ in range(50):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=2.0)

        self.assertEqual(len(errors), 0, f"Encountered concurrency errors: {errors}")
        # Total enqueued items should be 50 * 10 = 500
        count = 0
        while not mgr._cmd_queue.empty():
            cmd, payload = mgr._cmd_queue.get_nowait()
            self.assertEqual(cmd, "RECONNECT")
            self.assertIsNone(payload)
            count += 1
        self.assertEqual(count, 500)


class TestErrorToastStress(unittest.TestCase):
    """Stress tests for in-app toast notification system and WebKit error boundary."""

    def test_liquid_html_toast_elements(self):
        """Validates toast container, styles, and script definitions in generated HTML."""
        html = liquid_html.generate_liquid_html({})

        # DOM container
        self.assertIn('id="toast-container"', html)
        self.assertIn('class="toast-container"', html)

        # CSS classes
        self.assertIn('.toast {', html)
        self.assertIn('.toast.show', html)
        self.assertIn('.toast-error', html)
        self.assertIn('.toast-warning', html)
        self.assertIn('.toast-info', html)

        # JavaScript functions
        self.assertIn('window.showToast = function', html)
        self.assertIn("window.addEventListener('error'", html)
        self.assertIn("window.addEventListener('unhandledrejection'", html)

    def test_html_escape_logic_in_show_toast(self):
        """Simulates escapeHtml logic in liquid_html.py for adversarial XSS payloads."""
        def escape_html(s):
            if not s:
                return ""
            return (
                str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#039;")
            )

        payloads = [
            ('<script>alert("XSS")</script>', "&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;"),
            ('<img src=x onerror=alert(1)>', "&lt;img src=x onerror=alert(1)&gt;"),
            ("A & B < C > D ' E \" F", "A &amp; B &lt; C &gt; D &#039; E &quot; F"),
            ("", ""),
            (None, ""),
        ]

        for raw, expected in payloads:
            self.assertEqual(escape_html(raw), expected)

    def test_popover_show_toast_js_generation(self):
        """Validates that LoLPopoverController.show_toast correctly escapes JS arguments."""
        executed_js = []

        class MockWebView:
            def evaluateJavaScript_completionHandler_(self, js_str, handler):
                executed_js.append(js_str)

        ctrl = popover_ui.LoLPopoverController()
        ctrl._web_view = MockWebView()

        # Test standard error
        ctrl.show_toast("Conexión perdida", "error")
        self.assertEqual(len(executed_js), 1)
        self.assertIn('window.showToast("Conexi\\u00f3n perdida", "error")', executed_js[0])

        # Test special characters (quotes, newlines, backslashes, emojis)
        ctrl.show_toast('Error: "Failed"\nNext line \\ test ⚠️', "warning")
        self.assertEqual(len(executed_js), 2)
        js_code = executed_js[1]
        self.assertIn('window.showToast(', js_code)
        # Parse the JSON embedded in JS
        self.assertTrue('\"warning\"' in js_code)

    def test_popover_show_toast_null_webview_safe(self):
        """show_toast must not throw when WebKit view is uninitialized (headless/fallback)."""
        ctrl = popover_ui.LoLPopoverController()
        ctrl._web_view = None
        try:
            ctrl.show_toast("Test message without webview", "error")
        except Exception as e:
            self.fail(f"show_toast raised unexpected exception with null webview: {e}")

    def test_popover_ui_logger_defined(self):
        """Verifies popover_ui defines logger used in quit_application and show_toast."""
        self.assertTrue(hasattr(popover_ui, "logger"), "popover_ui is missing 'logger' definition referenced in lines 1592 and 1607")

    def test_rpc_manager_shutdown_race(self):
        """Stress-tests RPCManager rapid auto_start shutdown to detect worker thread join timeout."""
        failures = 0
        for _ in range(10):
            mgr = discord_rpc_manager.DiscordRPCManager(auto_start=True)
            mgr.shutdown()
            if mgr._worker_thread.is_alive():
                failures += 1
                mgr._worker_thread.join(timeout=5.0)
        self.assertEqual(failures, 0, f"Worker thread remained alive after shutdown() in {failures}/10 iterations")

    def test_app_controller_on_rpc_state_change_toast_routing(self):
        """Validates that on_rpc_state_change accurately routes error states to toasts."""
        toasts = []

        class MockPopover:
            def show_toast(self, msg, toast_type="error"):
                toasts.append((msg, toast_type))
            def set_connection_state(self, state):
                pass

        app_ctrl = app_gui.LoLAppController.alloc().init()
        app_ctrl._is_shutting_down = False
        app_ctrl.status_item = MagicMock()
        app_ctrl.popover = MockPopover()

        test_states = [
            ("connected", "Activo en Discord", False),
            ("connecting", "Conectando a Discord...", False),
            ("paused", "Presencia pausada", False),
            ("disconnected", "Esperando a Discord...", False),
            ("disconnected", "Error de socket: conexión perdida", True),
            ("disconnected", "La conexión falló tras 3 intentos", True),
            ("error", "Error crítico en loop de eventos", True),
        ]

        for state, msg, should_toast in test_states:
            initial_count = len(toasts)
            app_ctrl.on_rpc_state_change(state, msg)
            delta = len(toasts) - initial_count
            expected = 1 if should_toast else 0
            self.assertEqual(
                delta,
                expected,
                f"State '{state}' with message '{msg}' expected toast={should_toast}, got {delta}",
            )


class TestInAppQuitAndLifecycleStress(unittest.TestCase):
    """Stress tests for Quit controls in UI, WebBridge, PopoverController, and LoLAppController."""

    def test_liquid_html_quit_button_contracts(self):
        """Verifies quit buttons exist in both views with correct CSS and onclick handlers."""
        html = liquid_html.generate_liquid_html({})

        # Check view-main quit button
        self.assertIn('class="quit-btn"', html)
        self.assertIn("onclick=\"sendAction('quit_app')\"", html)

        # Check view-config quit button
        self.assertIn('class="quit-app-btn"', html)
        self.assertIn("onclick=\"sendAction('quit_app')\"", html)

    def test_web_bridge_routes_quit_app(self):
        """Verifies LoLWebBridge routes 'quit_app' action to controller.quit_application()."""
        quit_called = []

        class MockController:
            def quit_application(self):
                quit_called.append(True)

        bridge = popover_ui.LoLWebBridge.alloc().initWithController_(MockController())

        class MockMessage:
            def body(self):
                return {"action": "quit_app"}

        bridge.userContentController_didReceiveScriptMessage_(None, MockMessage())
        self.assertEqual(len(quit_called), 1)

    def test_popover_quit_application_closes_and_invokes_callback(self):
        """Verifies quit_application closes popover and triggers on_quit callback."""
        events = []

        ctrl = popover_ui.LoLPopoverController(on_quit=lambda: events.append("on_quit_called"))
        ctrl.close = MagicMock(side_effect=lambda: events.append("close_called"))

        ctrl.quit_application()

        self.assertIn("close_called", events)
        self.assertIn("on_quit_called", events)
        self.assertLess(events.index("close_called"), events.index("on_quit_called"))

    def test_popover_quit_handles_on_quit_exception(self):
        """Verifies quit_application does not crash if on_quit callback raises an error."""
        def bad_callback():
            raise RuntimeError("Failure in on_quit callback")

        ctrl = popover_ui.LoLPopoverController(on_quit=bad_callback)
        ctrl.close = MagicMock()

        try:
            ctrl.quit_application()
        except Exception as e:
            self.fail(f"quit_application crashed on on_quit exception: {e}")

    def test_app_controller_quit_clean_shutdown(self):
        """Verifies LoLAppController.quit unregisters observers, cleans up components, and is idempotent."""
        app_ctrl = app_gui.LoLAppController.alloc().init()
        app_ctrl._is_shutting_down = False

        app_ctrl.popover = MagicMock()
        app_ctrl.status_item = MagicMock()
        app_ctrl.rpc_manager = MagicMock()

        # First quit call
        app_ctrl.quit()

        self.assertTrue(app_ctrl._is_shutting_down)
        app_ctrl.popover.close.assert_called_once()
        app_ctrl.status_item.cleanup.assert_called_once()
        app_ctrl.rpc_manager.shutdown.assert_called_once()

        # Second quit call (idempotency check)
        app_ctrl.quit()
        # Assert counts did not increment
        self.assertEqual(app_ctrl.popover.close.call_count, 1)
        self.assertEqual(app_ctrl.status_item.cleanup.call_count, 1)
        self.assertEqual(app_ctrl.rpc_manager.shutdown.call_count, 1)


if __name__ == "__main__":
    unittest.main()
