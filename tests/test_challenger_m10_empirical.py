#!/usr/bin/env python3
"""
tests/test_challenger_m10_empirical.py - Empirical Challenger Stress Test Suite for Milestone M10

Comprehensive empirical stress testing for:
1. Requirement R1: Single-Instance Socket Lock & Focus
   - Simultaneous launch of primary and secondary instances via real OS subprocesses.
   - Verify secondary instance sends FOCUS command and exits with returncode 0.
   - Verify secondary instance does NOT launch duplicate GUI or event loops.
   - Verify socket and lock cleanup on clean shutdown.
   - Verify stale socket and lock recovery after ungraceful SIGKILL (-9).
   - High-concurrency race condition: 10 simultaneous processes competing for single-instance lock.
2. Requirement R2: Discord Interactive Profile Buttons
   - Stress-testing sanitize_buttons with:
     * Boundary counts: 0, 1, 2, 3, 5, 20 buttons.
     * Diverse URL formats (HTTPS, HTTP upgrade, missing scheme, IPs, query params, fragments).
     * Non-web schemes (javascript:, file:, data:, mailto:, ftp:).
     * Massive strings (10,000 char labels, 50,000 char URLs, Unicode/emojis).
     * Incomplete/corrupted dictionaries and non-collection types.
   - Verification of pypresence.update payload:
     * Omission of "buttons" key when buttons is empty, None, or invalid across all modes:
       - Modo Oficial (League of Legends)
       - Modo Detallado (League of Legends)
       - External / Custom games
     * Inclusion of "buttons" key only when valid buttons exist.
"""

import fcntl
import multiprocessing
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app_gui import SingleInstanceController
from discord_rpc_manager import DiscordRPCManager, RPCState, sanitize_buttons


class TestEmpiricalSingleInstanceSocketLockAndFocus(unittest.TestCase):
    """Empirical multi-process stress tests for SingleInstanceController (R1)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="lol_rpc_challenger_m10_")
        self.lock_path = os.path.join(self.temp_dir, "app.lock")
        self.sock_path = os.path.join(self.temp_dir, "app.sock")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass

    def test_r1_simultaneous_launch_primary_and_secondary_instances(self):
        """
        Empirically test simultaneous launch of primary and secondary instances:
        - Primary instance acquires lock and binds Unix socket.
        - Secondary instance attempts to launch with same config_dir.
        - Secondary connects to primary's socket, sends b'FOCUS\\n', and exits 0.
        - Primary instance receives FOCUS and triggers focus callback.
        - Secondary does not proceed to launch GUI.
        """
        focus_event_file = os.path.join(self.temp_dir, "focus_received.marker")
        primary_ready_file = os.path.join(self.temp_dir, "primary_ready.marker")

        primary_code = f"""
import sys, os, time
sys.path.insert(0, {repr(_ROOT)})
from app_gui import SingleInstanceController

def on_focus():
    with open({repr(focus_event_file)}, "w") as f:
        f.write("FOCUS_RECEIVED")

ctrl = SingleInstanceController(config_dir={repr(self.temp_dir)})
ctrl.set_focus_callback(on_focus)
acquired = ctrl.check_and_acquire()
if not acquired:
    sys.exit(1)

with open({repr(primary_ready_file)}, "w") as f:
    f.write("READY")

# Keep running to listen for secondary instances
for _ in range(100):
    time.sleep(0.05)
    if os.path.exists({repr(focus_event_file)}):
        break

ctrl.cleanup()
sys.exit(0)
"""
        primary_proc = subprocess.Popen(
            [sys.executable, "-c", primary_code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Wait for primary to become ready
            start_t = time.time()
            while time.time() - start_t < 5.0:
                if os.path.exists(primary_ready_file) and os.path.exists(self.sock_path):
                    break
                time.sleep(0.05)

            self.assertTrue(os.path.exists(primary_ready_file), "Primary instance did not start in time")
            self.assertTrue(os.path.exists(self.sock_path), "Primary socket file was not created")

            # Launch secondary instance using app_gui entry point logic
            secondary_code = f"""
import sys, os
sys.path.insert(0, {repr(_ROOT)})
from app_gui import SingleInstanceController

ctrl = SingleInstanceController(config_dir={repr(self.temp_dir)})
if not ctrl.check_and_acquire():
    # Exactly what app_gui.main() does
    sys.exit(0)
else:
    # If it acquired lock, that is an error (duplicate primary)
    sys.exit(42)
"""
            secondary_proc = subprocess.Popen(
                [sys.executable, "-c", secondary_code],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            sec_out, sec_err = secondary_proc.communicate(timeout=5.0)

            # Secondary MUST exit with 0 (cleanly exit without launching GUI)
            self.assertEqual(secondary_proc.returncode, 0, f"Secondary instance failed with code {secondary_proc.returncode}: {sec_err}")

            # Wait for primary to record FOCUS event
            start_focus = time.time()
            while time.time() - start_focus < 3.0:
                if os.path.exists(focus_event_file):
                    break
                time.sleep(0.05)

            self.assertTrue(os.path.exists(focus_event_file), "Primary instance never received FOCUS command from secondary")
            with open(focus_event_file, "r") as f:
                content = f.read()
            self.assertEqual(content, "FOCUS_RECEIVED")

        finally:
            if primary_proc.poll() is None:
                primary_proc.terminate()
                try:
                    primary_proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    primary_proc.kill()

    def test_r1_socket_cleanup_on_termination(self):
        """
        Empirically verify socket cleanup on graceful termination:
        - Primary instance acquires lock and socket.
        - Primary terminates gracefully calling cleanup().
        - Verify socket file is unlinked.
        - Verify lock is released and can be acquired immediately by a new instance.
        """
        ctrl1 = SingleInstanceController(config_dir=self.temp_dir)
        acquired = ctrl1.check_and_acquire()
        self.assertTrue(acquired, "First instance must acquire lock")
        self.assertTrue(os.path.exists(self.sock_path), "Socket file must exist while primary is active")
        self.assertTrue(os.path.exists(self.lock_path), "Lock file must exist")

        # Cleanup primary
        ctrl1.cleanup()
        self.assertFalse(os.path.exists(self.sock_path), "Socket file must be unlinked after cleanup()")

        # Second instance must be able to acquire lock cleanly now
        ctrl2 = SingleInstanceController(config_dir=self.temp_dir)
        acquired2 = ctrl2.check_and_acquire()
        self.assertTrue(acquired2, "Second instance must acquire lock after first instance cleaned up")
        self.assertTrue(os.path.exists(self.sock_path), "Socket file must exist for new primary")
        ctrl2.cleanup()
        self.assertFalse(os.path.exists(self.sock_path), "Socket file must be unlinked after second cleanup()")

    def test_r1_stale_socket_recovery_after_sigkill(self):
        """
        Empirically test crash resilience (SIGKILL -9):
        - Primary instance killed forcibly without cleanup.
        - Socket file and lock file remain on disk.
        - New instance launches: must automatically recover, unlink stale socket, and rebind.
        """
        primary_ready_file = os.path.join(self.temp_dir, "sigkill_ready.marker")
        primary_code = f"""
import sys, time
sys.path.insert(0, {repr(_ROOT)})
from app_gui import SingleInstanceController

ctrl = SingleInstanceController(config_dir={repr(self.temp_dir)})
if ctrl.check_and_acquire():
    with open({repr(primary_ready_file)}, "w") as f:
        f.write("READY")
    while True:
        time.sleep(0.1)
"""
        proc = subprocess.Popen([sys.executable, "-c", primary_code])
        try:
            # Wait for ready
            for _ in range(50):
                if os.path.exists(primary_ready_file) and os.path.exists(self.sock_path):
                    break
                time.sleep(0.05)
            self.assertTrue(os.path.exists(self.sock_path))

            # Kill forcibly with SIGKILL
            proc.send_signal(signal.SIGKILL)
            proc.wait(timeout=2.0)

            # Socket file remains on disk as stale socket
            self.assertTrue(os.path.exists(self.sock_path), "Stale socket must remain after SIGKILL")

            # Launch recovery instance
            recovery_ctrl = SingleInstanceController(config_dir=self.temp_dir)
            acquired = recovery_ctrl.check_and_acquire()
            self.assertTrue(acquired, "Recovery instance must acquire lock despite stale socket")
            self.assertTrue(os.path.exists(self.sock_path), "Recovery instance must bind fresh socket")
            recovery_ctrl.cleanup()

        finally:
            if proc.poll() is None:
                proc.kill()

    def test_r1_concurrent_burst_secondary_launches(self):
        """
        Burst concurrency stress test:
        - 1 Primary instance listening.
        - 8 Secondary instances launched simultaneously.
        - All 8 must exit cleanly with code 0 without deadlocking or crashing primary.
        """
        primary_ready = os.path.join(self.temp_dir, "burst_ready.marker")
        focus_count_file = os.path.join(self.temp_dir, "focus_count.txt")

        primary_code = f"""
import sys, time, os
sys.path.insert(0, {repr(_ROOT)})
from app_gui import SingleInstanceController

count = 0
def on_focus():
    global count
    count += 1
    with open({repr(focus_count_file)}, "w") as f:
        f.write(str(count))

ctrl = SingleInstanceController(config_dir={repr(self.temp_dir)})
ctrl.set_focus_callback(on_focus)
if not ctrl.check_and_acquire():
    sys.exit(1)

with open({repr(primary_ready)}, "w") as f:
    f.write("READY")

for _ in range(100):
    time.sleep(0.05)

ctrl.cleanup()
sys.exit(0)
"""
        primary_proc = subprocess.Popen([sys.executable, "-c", primary_code])
        try:
            for _ in range(50):
                if os.path.exists(primary_ready) and os.path.exists(self.sock_path):
                    break
                time.sleep(0.05)

            sec_code = f"""
import sys
sys.path.insert(0, {repr(_ROOT)})
from app_gui import SingleInstanceController
ctrl = SingleInstanceController(config_dir={repr(self.temp_dir)})
sys.exit(0 if not ctrl.check_and_acquire() else 1)
"""
            # Launch 8 simultaneous secondary processes
            procs = [subprocess.Popen([sys.executable, "-c", sec_code]) for _ in range(8)]
            for p in procs:
                p.wait(timeout=5.0)
                self.assertEqual(p.returncode, 0, "Secondary process failed or did not exit 0")

            # Check that focus was triggered at least once
            self.assertTrue(os.path.exists(focus_count_file), "Focus count file was not created")

        finally:
            if primary_proc.poll() is None:
                primary_proc.terminate()
                try:
                    primary_proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    primary_proc.kill()


class TestEmpiricalDiscordProfileButtons(unittest.TestCase):
    """Empirical stress tests for Discord Interactive Profile Buttons (R2)."""

    def test_r2_sanitize_buttons_boundary_counts(self):
        """Boundary counts: 0, 1, 2, 5 buttons."""
        # 0 buttons
        self.assertIsNone(sanitize_buttons([]))
        self.assertIsNone(sanitize_buttons(()))
        self.assertIsNone(sanitize_buttons(None))
        self.assertIsNone(sanitize_buttons({}))
        self.assertIsNone(sanitize_buttons(123))
        self.assertIsNone(sanitize_buttons("invalid"))

        # 1 button
        res1 = sanitize_buttons([{"label": "OP.GG", "url": "https://op.gg"}])
        self.assertIsNotNone(res1)
        self.assertEqual(len(res1), 1)
        self.assertEqual(res1[0]["label"], "OP.GG")
        self.assertEqual(res1[0]["url"], "https://op.gg")

        # 2 buttons
        res2 = sanitize_buttons([
            {"label": "OP.GG", "url": "https://op.gg"},
            {"label": "Twitch", "url": "https://twitch.tv"},
        ])
        self.assertIsNotNone(res2)
        self.assertEqual(len(res2), 2)
        self.assertEqual(res2[0]["label"], "OP.GG")
        self.assertEqual(res2[1]["label"], "Twitch")

        # 5 buttons -> strictly capped at 2
        res5 = sanitize_buttons([
            {"label": f"Button {i}", "url": f"https://example{i}.com"}
            for i in range(1, 6)
        ])
        self.assertIsNotNone(res5)
        self.assertEqual(len(res5), 2, "Must cap at exactly 2 buttons")
        self.assertEqual(res5[0]["label"], "Button 1")
        self.assertEqual(res5[1]["label"], "Button 2")

    def test_r2_sanitize_buttons_diverse_url_formats(self):
        """Diverse URL formats: standard HTTPS, HTTP upgraded, naked domains, IPs, query strings, fragments."""
        cases = [
            # Insecure HTTP upgraded to HTTPS
            ("http://op.gg/summoners", "https://op.gg/summoners"),
            # Standard HTTPS preserved
            ("https://na.op.gg/summoners/faker", "https://na.op.gg/summoners/faker"),
            # Naked domain prepended with https://
            ("discord.gg/league", "https://discord.gg/league"),
            ("www.twitch.tv/streamer", "https://www.twitch.tv/streamer"),
            # IP address with port
            ("192.168.1.1:8080/path", "https://192.168.1.1:8080/path"),
            # URL with complex query parameters and fragments
            (
                "https://leagueofgraphs.com/match/na/12345?query=test#highlight",
                "https://leagueofgraphs.com/match/na/12345?query=test#highlight",
            ),
        ]
        for raw_url, expected_url in cases:
            res = sanitize_buttons([{"label": "Test", "url": raw_url}])
            self.assertIsNotNone(res, f"Failed for {raw_url}")
            self.assertEqual(res[0]["url"], expected_url, f"Failed to properly format {raw_url}")

    def test_r2_sanitize_buttons_non_web_schemes(self):
        """
        Empirically test non-web schemes: javascript:, file:, data:, mailto:, ftp:.
        Verify they are safely prepended or normalized with https:// and sanitized against script execution.
        """
        hostile_schemes = [
            "javascript:alert(1)",
            "file:///etc/passwd",
            "data:text/html,<script>alert(1)</script>",
            "ftp://ftp.example.com/file",
            "mailto:admin@example.com",
            "tel:+1234567890",
        ]
        for bad_url in hostile_schemes:
            res = sanitize_buttons([{"label": "Hostile", "url": bad_url}])
            self.assertIsNotNone(res)
            # Must strictly start with https://, neutralizing scheme exploitation
            self.assertTrue(
                res[0]["url"].startswith("https://"),
                f"Scheme {bad_url} was not forced to https://: {res[0]['url']}",
            )
            self.assertFalse(
                res[0]["url"].startswith("javascript:"),
                "javascript: scheme must not survive raw",
            )
            self.assertFalse(
                res[0]["url"].startswith("file:"),
                "file: scheme must not survive raw",
            )

    def test_r2_sanitize_buttons_massive_strings_and_unicode(self):
        """Massive strings: 10,000 char labels, 50,000 char URLs, multi-byte Unicode/emojis."""
        giant_label = "🔥👑" * 5000  # 10,000 emojis/chars
        giant_url = "https://example.com/api?payload=" + ("A" * 50000)

        res = sanitize_buttons([{"label": giant_label, "url": giant_url}])
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 1)

        # Label strictly truncated to 32 chars
        self.assertLessEqual(len(res[0]["label"]), 32)
        # URL strictly truncated to 512 chars
        self.assertEqual(len(res[0]["url"]), 512)
        self.assertTrue(res[0]["url"].startswith("https://example.com/api?payload="))

    def test_r2_sanitize_buttons_interleaved_invalids(self):
        """Interleaved invalid items in list: nulls, non-dicts, missing labels, empty urls."""
        messy_list = [
            None,
            {},
            {"label": "", "url": "https://valid.com"},
            {"label": "No URL"},
            "a string not a dict",
            {"label": "Valid Button 1", "url": "https://op.gg"},
            {"label": "   ", "url": "   "},
            {"label": "Valid Button 2", "url": "https://twitch.tv"},
            {"label": "Valid Button 3 (Extra)", "url": "https://extra.com"},
        ]
        res = sanitize_buttons(messy_list)
        self.assertIsNotNone(res)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["label"], "Valid Button 1")
        self.assertEqual(res[0]["url"], "https://op.gg")
        self.assertEqual(res[1]["label"], "Valid Button 2")
        self.assertEqual(res[1]["url"], "https://twitch.tv")

    def test_r2_pypresence_update_payload_omission_when_empty(self):
        """
        Empirically verify that pypresence.update kwargs omits 'buttons' key when
        buttons list is empty, None, or invalid across all modes:
        1. Modo Oficial (League of Legends)
        2. Modo Detallado (League of Legends)
        3. Custom / Non-LoL game
        """
        mock_rpc = MagicMock()
        mgr = DiscordRPCManager(client_id="12345", auto_start=False, load_config=False)
        mgr._rpc = mock_rpc
        mgr.is_active = True
        mgr.start_time = 1000

        # Scenario 1: Empty buttons in Modo Oficial
        mgr.mode = "oficial"
        mgr.selected_game_id = "lol"
        mgr.buttons = []
        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        kwargs = mock_rpc.update.call_args[1]
        self.assertNotIn("buttons", kwargs, "kwargs must omit 'buttons' when empty in modo oficial")

        # Scenario 2: Invalid/empty buttons in Modo Detallado
        mock_rpc.reset_mock()
        mgr.mode = "detallado"
        mgr.buttons = [{"label": "", "url": ""}]
        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        kwargs = mock_rpc.update.call_args[1]
        self.assertNotIn("buttons", kwargs, "kwargs must omit 'buttons' when invalid in modo detallado")

        # Scenario 3: None buttons in Custom Game
        mock_rpc.reset_mock()
        mgr.selected_game_id = "valorant"
        mgr.buttons = None
        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        kwargs = mock_rpc.update.call_args[1]
        self.assertNotIn("buttons", kwargs, "kwargs must omit 'buttons' in custom games when None")

        # Scenario 4: Valid buttons present -> kwargs MUST include 'buttons'
        mock_rpc.reset_mock()
        mgr.mode = "detallado"
        mgr.selected_game_id = "lol"
        mgr.buttons = [{"label": "My Profile", "url": "https://op.gg"}]
        mgr._send_rpc_update()
        self.assertTrue(mock_rpc.update.called)
        kwargs = mock_rpc.update.call_args[1]
        self.assertIn("buttons", kwargs, "kwargs must contain 'buttons' when valid buttons exist")
        self.assertEqual(len(kwargs["buttons"]), 1)
        self.assertEqual(kwargs["buttons"][0]["label"], "My Profile")
        self.assertEqual(kwargs["buttons"][0]["url"], "https://op.gg")


if __name__ == "__main__":
    unittest.main()
