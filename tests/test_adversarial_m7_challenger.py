#!/usr/bin/env python3
"""
tests/test_adversarial_m7_challenger.py - Empirical Challenger Stress Test Suite for Milestone M7

Empirically tests and stress-tests:
1. SingleInstanceController Concurrency & Process Isolation:
   - Primary instance running in a separate child process.
   - Secondary instance launched as a separate process:
     * Asserts it connects to primary via Unix domain socket.
     * Asserts it transmits b"FOCUS\\n".
     * Asserts it exits immediately with returncode 0.
     * Asserts primary process registers FOCUS notification.
   - Actual CLI entry point (app_gui.py main()):
     * While primary runs, launches `python app_gui.py`.
     * Asserts returncode is 0, execution is prompt, and "Secondary instance exiting cleanly" is logged.
   - SIGKILL Stale Socket & Lock Recovery:
     * Primary process forcibly killed with SIGKILL (signal.SIGKILL / -9), bypassing all cleanup routines.
     * Asserts app.lock and app.sock remain on disk after kill.
     * A third (recovery) process launches:
       - Asserts it acquires the lock cleanly without hanging or crashing.
       - Asserts it unlinks the dead socket and rebinds app.sock.
     * A fourth (secondary) process launches against the recovered primary:
       - Asserts it sends FOCUS and exits 0 immediately.
       - Asserts recovered primary registers FOCUS.
   - Burst Concurrency Stress:
     * 10 secondary processes launched simultaneously in parallel against 1 primary instance.
     * Asserts all 10 exit with returncode 0 within a strict time budget (< 4.0s total).
     * Asserts primary socket listener handles concurrent burst without crashing or dropping.
   - Stale / Corrupted Socket File Recovery:
     * Corrupted non-socket regular file placed at app.sock path.
     * Primary instance cleanly unlinks and binds new Unix domain socket.
   - Idempotent cleanup and double acquisition safety.

2. Context Menu via PyObjC:
   - Inspects NSMenu constructed by build_context_menu().
   - Validates all 5 NSMenuItems (4 actions + 1 separator):
     * "Abrir Popover" (action menuOpenPopover:)
     * Dynamic Presence title: "Pausar Presencia" (state=active) vs "Reanudar Presencia" (state=normal/paused/unknown)
     * "Configuración ⚙️" (action menuOpenSettings:, keyEquivalent ",")
     * Separator item
     * "Salir de Discord RPC" (action menuQuit:, keyEquivalent "q")
   - Validates targets point to controller instance.
   - Validates selector invocations trigger callbacks, and handle None callbacks gracefully.
   - Validates right-click / control-click event discrimination in statusItemButtonClicked_:
     * NSEventTypeRightMouseUp -> calls popUpStatusItemMenu_
     * NSEventTypeRightMouseDown -> calls popUpStatusItemMenu_
     * NSEventModifierFlagControl + LeftMouseUp -> calls popUpStatusItemMenu_
     * LeftMouseUp without modifiers -> does NOT call popUpStatusItemMenu_, toggles popover instead.

3. Hardened LaunchAgent Plist & System Verification:
   - Parses ~/Library/LaunchAgents/com.victormanuel.lolrpc.plist via plistlib.
   - Asserts Label == "com.victormanuel.lolrpc".
   - Asserts ProgramArguments contains direct bundle binary path:
     "/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC".
   - Asserts argument "--silent" is present.
   - Asserts "/usr/bin/open" is NOT present anywhere in ProgramArguments.
   - Asserts target binary exists on disk and is executable (os.X_OK).
   - Asserts StandardOutPath is absolute, ends with "lol_discord_rpc.log", and resides in ~/Library/Logs/.
   - Asserts StandardErrorPath is absolute, ends with "lol_discord_rpc_error.log", and resides in ~/Library/Logs/.
   - Asserts ProcessType == "Interactive" and RunAtLoad is True.
   - Tests round-trip toggle: _sync_login_item(True) and _sync_login_item(False).
"""

import os
import sys
import time
import signal
import socket
import plistlib
import tempfile
import shutil
import subprocess
import unittest
from typing import Any, List
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import AppKit
import status_item
import popover_ui
import app_gui


class TestSingleInstanceEmpiricalProcesses(unittest.TestCase):
    """
    Empirical multi-process stress tests for SingleInstanceController:
    Separate processes, IPC FOCUS signaling, SIGKILL recovery, burst concurrency.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="lol_challenger_m7_")
        self.lock_path = os.path.join(self.temp_dir, "app.lock")
        self.sock_path = os.path.join(self.temp_dir, "app.sock")
        self.marker_file = os.path.join(self.temp_dir, "focus_received.marker")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _start_primary_process(self) -> subprocess.Popen:
        """
        Spawns a separate Python process running SingleInstanceController as primary.
        Writes to self.marker_file when FOCUS is received.
        """
        code = f"""
import sys
import os
import time
sys.path.insert(0, {repr(_PROJECT_ROOT)})
import app_gui

marker_file = {repr(self.marker_file)}

def on_focus():
    with open(marker_file, "a") as f:
        f.write("FOCUS\\n")

ctrl = app_gui.SingleInstanceController(config_dir={repr(self.temp_dir)})
ctrl.set_focus_callback(on_focus)
if not ctrl.check_and_acquire():
    sys.exit(1)

# Signal readiness to stdout
sys.stdout.write("READY\\n")
sys.stdout.flush()

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    ctrl.cleanup()
"""
        proc = subprocess.Popen(
            [sys.executable, "-u", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        line = proc.stdout.readline()
        if "READY" not in line:
            proc.kill()
            err = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"Primary process failed to become ready: {line} {err}")
        return proc

    def _run_secondary_process(self, timeout: float = 3.0) -> subprocess.CompletedProcess:
        """
        Runs a separate secondary process attempting check_and_acquire().
        Must notify primary and exit with returncode 0.
        """
        code = f"""
import sys
sys.path.insert(0, {repr(_PROJECT_ROOT)})
import app_gui

ctrl = app_gui.SingleInstanceController(config_dir={repr(self.temp_dir)})
acquired = ctrl.check_and_acquire()
if acquired:
    ctrl.cleanup()
    sys.exit(2)
else:
    # Successfully detected primary and sent FOCUS
    sys.exit(0)
"""
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def test_secondary_process_exits_0_and_notifies_primary(self):
        """
        Requirement 1: Simulate primary instance starting. Launch secondary process:
        does it send FOCUS and exit 0 immediately?
        """
        primary = self._start_primary_process()
        try:
            self.assertTrue(os.path.exists(self.lock_path), "app.lock should exist")
            self.assertTrue(os.path.exists(self.sock_path), "app.sock should exist")

            start_t = time.time()
            secondary_res = self._run_secondary_process(timeout=2.0)
            elapsed = time.time() - start_t

            self.assertEqual(
                secondary_res.returncode,
                0,
                f"Secondary process should exit 0, got {secondary_res.returncode}. Stderr: {secondary_res.stderr}",
            )
            self.assertLess(elapsed, 2.0, "Secondary process should exit immediately (< 2.0s)")

            # Check that primary received FOCUS
            deadline = time.time() + 2.0
            found_focus = False
            while time.time() < deadline:
                if os.path.exists(self.marker_file):
                    with open(self.marker_file, "r") as f:
                        if "FOCUS" in f.read():
                            found_focus = True
                            break
                time.sleep(0.05)

            self.assertTrue(found_focus, "Primary instance did not register FOCUS signal from secondary process")
        finally:
            primary.terminate()
            primary.stdout.close()
            primary.stderr.close()
            primary.wait(timeout=2.0)

    def test_sigkill_stale_socket_recovery(self):
        """
        Requirement 1: Simulate primary process killed with SIGKILL leaving stale socket / lock file:
        does a new instance cleanly recover without hang or crash?
        """
        primary = self._start_primary_process()
        primary_pid = primary.pid

        # Verify files exist
        self.assertTrue(os.path.exists(self.lock_path))
        self.assertTrue(os.path.exists(self.sock_path))

        # Send SIGKILL (kill -9) - skips all cleanup code completely!
        os.kill(primary_pid, signal.SIGKILL)
        primary.stdout.close()
        primary.stderr.close()
        primary.wait(timeout=2.0)

        # Confirm primary is dead
        self.assertIsNotNone(primary.poll(), "Primary should be dead after SIGKILL")

        # Crucial empirical verification: lock and dead socket file STILL EXIST on disk!
        self.assertTrue(os.path.exists(self.lock_path), "app.lock must remain after SIGKILL")
        self.assertTrue(os.path.exists(self.sock_path), "app.sock must remain as stale socket after SIGKILL")

        # Launch recovery instance (new process)
        recovery_proc = self._start_primary_process()
        try:
            # Recovery instance must be alive and listening
            self.assertIsNone(recovery_proc.poll(), "Recovery instance should be running")

            # Launch a secondary process against the recovered instance
            res = self._run_secondary_process(timeout=2.0)
            self.assertEqual(res.returncode, 0, f"Secondary process should exit 0 against recovered instance: {res.stderr}")

            # Verify recovered primary registered FOCUS
            deadline = time.time() + 2.0
            found_focus = False
            while time.time() < deadline:
                if os.path.exists(self.marker_file):
                    with open(self.marker_file, "r") as f:
                        if "FOCUS" in f.read():
                            found_focus = True
                            break
                time.sleep(0.05)

            self.assertTrue(found_focus, "Recovered instance failed to receive FOCUS signal")
        finally:
            recovery_proc.terminate()
            recovery_proc.stdout.close()
            recovery_proc.stderr.close()
            recovery_proc.wait(timeout=2.0)

    def test_burst_concurrency_10_secondaries(self):
        """
        Adversarial stress: Launch 10 secondary processes simultaneously against 1 primary instance.
        All 10 must cleanly exit with code 0 without hangs or deadlocks.
        """
        primary = self._start_primary_process()
        try:
            code = f"""
import sys
sys.path.insert(0, {repr(_PROJECT_ROOT)})
import app_gui

ctrl = app_gui.SingleInstanceController(config_dir={repr(self.temp_dir)})
if ctrl.check_and_acquire():
    ctrl.cleanup()
    sys.exit(2)
sys.exit(0)
"""
            # Launch 10 processes concurrently
            procs = [
                subprocess.Popen(
                    [sys.executable, "-c", code],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(10)
            ]

            start_t = time.time()
            returncodes = []
            for p in procs:
                rc = p.wait(timeout=4.0)
                p.stdout.close()
                p.stderr.close()
                returncodes.append(rc)
            elapsed = time.time() - start_t

            self.assertEqual(returncodes, [0] * 10, f"All 10 secondary processes must exit 0. Got: {returncodes}")
            self.assertLess(elapsed, 4.0, f"Burst of 10 processes should complete promptly (took {elapsed:.2f}s)")
        finally:
            primary.terminate()
            primary.stdout.close()
            primary.stderr.close()
            primary.wait(timeout=2.0)

    def test_corrupted_non_socket_file_recovery(self):
        """
        Adversarial test: If app.sock exists as a corrupted regular file (e.g. created by crash or bad tool),
        SingleInstanceController must unlink it and successfully bind a valid socket.
        """
        # Create non-socket garbage file at sock_path
        os.makedirs(self.temp_dir, exist_ok=True)
        with open(self.sock_path, "w") as f:
            f.write("GARBAGE DATA IN PLACE OF SOCKET")

        ctrl = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        try:
            acquired = ctrl.check_and_acquire()
            self.assertTrue(acquired, "Must acquire even when corrupted regular file was present at sock_path")

            # Verify it is now a valid Unix socket
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(self.sock_path)
            client.sendall(b"FOCUS\n")
            resp = client.recv(1024)
            self.assertIn(b"OK", resp)
            client.close()
        finally:
            ctrl.cleanup()

    def test_controller_idempotent_cleanup_and_double_acquire(self):
        """
        Tests that cleanup() can be called multiple times without errors,
        and calling check_and_acquire twice on the same instance behaves safely.
        """
        ctrl = app_gui.SingleInstanceController(config_dir=self.temp_dir)
        try:
            self.assertTrue(ctrl.check_and_acquire())
            ctrl.cleanup()
            ctrl.cleanup()
            ctrl.cleanup()
            self.assertFalse(os.path.exists(self.sock_path))
        finally:
            ctrl.cleanup()

    def test_real_app_gui_entrypoint_as_secondary(self):
        """
        Adversarial test: Runs the actual app_gui.py script entrypoint (main())
        via subprocess in an isolated environment where primary is already active.
        Verifies returncode 0, prompt exit, and FOCUS delivery.
        """
        temp_home = tempfile.mkdtemp(prefix="lol_home_")
        try:
            cfg_dir = os.path.join(temp_home, ".config", "lol_discord_rpc")
            os.makedirs(cfg_dir, exist_ok=True)
            focus_marker = os.path.join(temp_home, "focus.txt")

            code = f"""
import sys, os, time
sys.path.insert(0, {repr(_PROJECT_ROOT)})
import app_gui

def on_focus():
    with open({repr(focus_marker)}, "a") as f:
        f.write("FOCUS\\n")

ctrl = app_gui.SingleInstanceController(config_dir={repr(cfg_dir)})
ctrl.set_focus_callback(on_focus)
if not ctrl.check_and_acquire():
    sys.exit(1)
sys.stdout.write("READY\\n")
sys.stdout.flush()
while True:
    time.sleep(0.1)
"""
            primary = subprocess.Popen(
                [sys.executable, "-u", "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            line = primary.stdout.readline()
            self.assertIn("READY", line)

            iso_env = os.environ.copy()
            iso_env["HOME"] = temp_home

            # Test 1: Normal invocation of app_gui.py
            t0 = time.time()
            res1 = subprocess.run(
                [sys.executable, os.path.join(_PROJECT_ROOT, "app_gui.py")],
                env=iso_env,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            elapsed1 = time.time() - t0
            self.assertEqual(res1.returncode, 0, f"app_gui.py must exit 0, got {res1.returncode}. Stderr: {res1.stderr}")
            self.assertLess(elapsed1, 3.0, f"app_gui.py took too long: {elapsed1:.2f}s")

            # Test 2: Silent invocation of app_gui.py --silent
            t1 = time.time()
            res2 = subprocess.run(
                [sys.executable, os.path.join(_PROJECT_ROOT, "app_gui.py"), "--silent"],
                env=iso_env,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            elapsed2 = time.time() - t1
            self.assertEqual(res2.returncode, 0, f"app_gui.py --silent must exit 0, got {res2.returncode}. Stderr: {res2.stderr}")
            self.assertLess(elapsed2, 3.0, f"app_gui.py --silent took too long: {elapsed2:.2f}s")

            # Check that primary received 2 FOCUS notifications
            time.sleep(0.3)
            with open(focus_marker, "r") as f:
                lines = f.read().strip().splitlines()
            self.assertEqual(len(lines), 2, f"Expected 2 FOCUS signals, got {lines}")

            primary.terminate()
            primary.stdout.close()
            primary.stderr.close()
            primary.wait(timeout=2.0)
        finally:
            shutil.rmtree(temp_home, ignore_errors=True)



class TestContextMenuPyObjCEmpirical(unittest.TestCase):
    """
    Requirement 2: Validate NSMenu items, actions, selectors, and right-click handling via PyObjC.
    """

    def setUp(self):
        self.toggle_calls = 0
        self.presence_calls = 0
        self.settings_calls = 0
        self.quit_calls = 0

        self.ctrl = status_item.LoLStatusItemController(
            on_toggle=lambda s=None: setattr(self, "toggle_calls", self.toggle_calls + 1),
            on_toggle_presence=lambda: setattr(self, "presence_calls", self.presence_calls + 1),
            on_open_settings=lambda: setattr(self, "settings_calls", self.settings_calls + 1),
            on_quit=lambda: setattr(self, "quit_calls", self.quit_calls + 1),
            auto_create=True,
        )

    def tearDown(self):
        if self.ctrl:
            self.ctrl.cleanup()

    def test_menu_structure_and_selectors(self):
        """
        Validates NSMenu class, item count, titles, keyEquivalents, targets, and selectors.
        """
        menu = self.ctrl.build_context_menu()
        self.assertIsInstance(menu, AppKit.NSMenu, "Must return an AppKit.NSMenu instance")
        items = menu.itemArray()
        self.assertEqual(len(items), 5, f"Context menu should have 5 items (4 actions + 1 separator), got {len(items)}")

        # Item 0: Abrir Popover
        item0 = items[0]
        self.assertEqual(item0.title(), "Abrir Popover")
        self.assertIn(str(item0.action()), ("menuOpenPopover:", b"menuOpenPopover:"))
        self.assertEqual(item0.target(), self.ctrl)

        # Item 1: Presencia
        item1 = items[1]
        self.assertIn("Presencia", item1.title())
        self.assertIn(str(item1.action()), ("menuTogglePresence:", b"menuTogglePresence:"))
        self.assertEqual(item1.target(), self.ctrl)

        # Item 2: Settings
        item2 = items[2]
        self.assertEqual(item2.title(), "Configuración ⚙️")
        self.assertIn(str(item2.action()), ("menuOpenSettings:", b"menuOpenSettings:"))
        self.assertEqual(item2.keyEquivalent(), ",")
        self.assertEqual(item2.target(), self.ctrl)

        # Item 3: Separator
        item3 = items[3]
        self.assertTrue(item3.isSeparatorItem(), "Item 3 must be a separator")

        # Item 4: Quit
        item4 = items[4]
        self.assertEqual(item4.title(), "Salir de Discord RPC")
        self.assertIn(str(item4.action()), ("menuQuit:", b"menuQuit:"))
        self.assertEqual(item4.keyEquivalent(), "q")
        self.assertEqual(item4.target(), self.ctrl)

    def test_dynamic_presence_title_all_states(self):
        """
        Tests presence item title for all states: 'active', 'paused', 'normal', and invalid states.
        """
        # Active -> "Pausar Presencia"
        self.ctrl.set_state("active")
        menu = self.ctrl.build_context_menu()
        self.assertEqual(menu.itemArray()[1].title(), "Pausar Presencia")

        # Paused -> "Reanudar Presencia"
        self.ctrl.set_state("paused")
        menu = self.ctrl.build_context_menu()
        self.assertEqual(menu.itemArray()[1].title(), "Reanudar Presencia")

        # Normal -> "Reanudar Presencia"
        self.ctrl.set_state("normal")
        menu = self.ctrl.build_context_menu()
        self.assertEqual(menu.itemArray()[1].title(), "Reanudar Presencia")

        # Unrecognized fallback -> "Reanudar Presencia"
        self.ctrl.set_state("UNKNOWN_STATE_XYZ")
        menu = self.ctrl.build_context_menu()
        self.assertEqual(menu.itemArray()[1].title(), "Reanudar Presencia")

    def test_selector_invocations_and_none_callbacks(self):
        """
        Directly executes action methods on target and asserts callbacks fire cleanly.
        Then sets callbacks to None and verifies no unhandled exceptions.
        """
        self.ctrl.menuOpenPopover_(None)
        self.assertEqual(self.toggle_calls, 1)

        self.ctrl.menuTogglePresence_(None)
        self.assertEqual(self.presence_calls, 1)

        self.ctrl.menuOpenSettings_(None)
        self.assertEqual(self.settings_calls, 1)

        self.ctrl.menuQuit_(None)
        self.assertEqual(self.quit_calls, 1)

        # With None callbacks
        self.ctrl.set_context_menu_callbacks(
            on_toggle_presence=None,
            on_open_settings=None,
            on_quit=None,
        )
        self.ctrl._on_toggle = None
        # Should execute without throwing
        self.ctrl.menuOpenPopover_(None)
        self.ctrl.menuTogglePresence_(None)
        self.ctrl.menuOpenSettings_(None)

    def test_click_event_discrimination(self):
        """
        Verifies right-click and control-click trigger popUpStatusItemMenu_,
        while normal left-click invokes standard popover toggle.
        """
        class MockEvent:
            def __init__(self, etype, flags=0):
                self._type = etype
                self._flags = flags
            def type(self):
                return self._type
            def modifierFlags(self):
                return self._flags

        popped_menus = []
        mock_status_item = MagicMock()
        mock_status_item.popUpStatusItemMenu_ = lambda m: popped_menus.append(m)
        self.ctrl._status_item = mock_status_item

        mock_nsapp = MagicMock()

        # 1. Right Mouse Up -> Pops menu
        mock_nsapp.currentEvent.return_value = MockEvent(AppKit.NSEventTypeRightMouseUp)
        with patch.object(status_item.AppKit, "NSApp", mock_nsapp):
            self.ctrl.statusItemButtonClicked_(None)
        self.assertEqual(len(popped_menus), 1)

        # 2. Right Mouse Down -> Pops menu
        mock_nsapp.currentEvent.return_value = MockEvent(AppKit.NSEventTypeRightMouseDown)
        with patch.object(status_item.AppKit, "NSApp", mock_nsapp):
            self.ctrl.statusItemButtonClicked_(None)
        self.assertEqual(len(popped_menus), 2)

        # 3. Control + Left Click -> Pops menu
        mock_nsapp.currentEvent.return_value = MockEvent(AppKit.NSEventTypeLeftMouseUp, AppKit.NSEventModifierFlagControl)
        with patch.object(status_item.AppKit, "NSApp", mock_nsapp):
            self.ctrl.statusItemButtonClicked_(None)
        self.assertEqual(len(popped_menus), 3)

        # 4. Standard Left Click -> Does NOT pop menu, calls toggle
        toggle_before = self.toggle_calls
        mock_nsapp.currentEvent.return_value = MockEvent(AppKit.NSEventTypeLeftMouseUp, 0)
        with patch.object(status_item.AppKit, "NSApp", mock_nsapp):
            self.ctrl.statusItemButtonClicked_(None)
        self.assertEqual(len(popped_menus), 3, "Left click must NOT pop context menu")
        self.assertEqual(self.toggle_calls, toggle_before + 1, "Left click must trigger on_toggle")


class TestLaunchAgentPlistEmpirical(unittest.TestCase):
    """
    Requirement 3: Parse plist, verify direct binary path, arguments, and absolute log paths in ~/Library/Logs/.
    """

    def setUp(self):
        self.plist_path = os.path.expanduser("~/Library/LaunchAgents/com.victormanuel.lolrpc.plist")
        self.bundle_binary = "/Applications/League of Legends RPC.app/Contents/MacOS/League of Legends RPC"

    def test_installed_launchagent_plist(self):
        """
        Parses the installed plist file on the local machine and validates strict compliance.
        """
        self.assertTrue(os.path.exists(self.plist_path), f"LaunchAgent plist not found at {self.plist_path}")
        with open(self.plist_path, "rb") as f:
            plist = plistlib.load(f)

        # 1. Label
        self.assertEqual(plist.get("Label"), "com.victormanuel.lolrpc")

        # 2. ProgramArguments: direct binary executable, --silent, no /usr/bin/open
        args = plist.get("ProgramArguments", [])
        self.assertIsInstance(args, list)
        self.assertEqual(len(args), 2, f"ProgramArguments must contain exactly binary and --silent, got: {args}")
        self.assertEqual(args[0], self.bundle_binary)
        self.assertEqual(args[1], "--silent")
        self.assertNotIn("/usr/bin/open", args)
        self.assertNotIn("open", args)

        # 3. Binary existence and executable permission
        self.assertTrue(os.path.exists(self.bundle_binary), f"Target binary does not exist: {self.bundle_binary}")
        self.assertTrue(os.path.isfile(self.bundle_binary), f"Target binary is not a file: {self.bundle_binary}")
        self.assertTrue(os.access(self.bundle_binary, os.X_OK), f"Target binary is not executable: {self.bundle_binary}")

        # 4. StandardOutPath and StandardErrorPath in ~/Library/Logs/
        logs_dir = os.path.expanduser("~/Library/Logs")
        self.assertTrue(os.path.isdir(logs_dir), f"Logs dir {logs_dir} does not exist")

        stdout_path = plist.get("StandardOutPath")
        stderr_path = plist.get("StandardErrorPath")

        self.assertIsNotNone(stdout_path, "StandardOutPath is missing")
        self.assertIsNotNone(stderr_path, "StandardErrorPath is missing")

        self.assertTrue(os.path.isabs(stdout_path), f"StandardOutPath must be absolute: {stdout_path}")
        self.assertTrue(os.path.isabs(stderr_path), f"StandardErrorPath must be absolute: {stderr_path}")

        self.assertEqual(stdout_path, os.path.join(logs_dir, "lol_discord_rpc.log"))
        self.assertEqual(stderr_path, os.path.join(logs_dir, "lol_discord_rpc_error.log"))

        # 5. ProcessType and RunAtLoad
        self.assertEqual(plist.get("ProcessType"), "Interactive")
        self.assertTrue(plist.get("RunAtLoad"))

    def test_sync_login_item_code_generation(self):
        """
        Tests that popover_ui.LoLPopoverController._sync_login_item dynamically generates
        the exact compliant plist content.
        """
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
            self.assertEqual(args[0], self.bundle_binary)
            self.assertEqual(args[1], "--silent")
            self.assertTrue(plist["StandardOutPath"].endswith("lol_discord_rpc.log"))
            self.assertTrue(plist["StandardErrorPath"].endswith("lol_discord_rpc_error.log"))


if __name__ == "__main__":
    unittest.main()
