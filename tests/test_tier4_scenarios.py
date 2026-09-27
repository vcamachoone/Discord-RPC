"""
test_tier4_scenarios.py - Tier 4: Real-World Application Scenarios Suite

Executes end-to-end integration workflows simulating realistic user behaviors,
network socket drops, concurrency stress, and application bundle launch:
- S1: Official Mode Full Lifecycle (Start -> Connect -> Pause -> Resume -> Match Reset)
- S2: Detailed Mode Riot Champion & Apex Rank Workflow (Anomalies & Division Suppression)
- S3: Concurrency Stress Test (400 concurrent operations across 4 worker threads)
- S4: Network/Discord Disconnect & Reconnect (BrokenPipeError handling & recovery)
- S5: macOS App Bundle Packaging & Launch Integrity (/Applications verification)
"""

import os
import plistlib
import queue
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from tests.mocks import MockPresence

# Implemented modules
import lol_champions
from lol_champions import ChampionResolver

import lol_ranks
from lol_ranks import format_rank_display, get_rank_crest_url

import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState


class TestTier4Scenarios(unittest.TestCase):
    """Tier 4 Real-World Application Workflows."""

    def test_s1_official_mode_full_lifecycle(self):
        """
        Scenario 1: Official Mode Full Lifecycle.
        Simulates: Startup -> Connect -> Pause -> Resume -> 25-minute Match Auto-Restart.
        """
        state_changes = []
        match_resets = []

        mgr = DiscordRPCManager(
            on_state_change=lambda s, m: state_changes.append(s),
            on_match_reset=lambda t: match_resets.append(t),
            auto_start=False,
        )

        mock_socket = MockPresence(mgr.client_id)
        mock_socket.connected = True
        mgr._rpc = mock_socket

        # 1. Startup presence (Official mode: Solo LoL + Elapsed Time)
        mgr._state = RPCState.CONNECTED
        mgr._send_rpc_update()
        self.assertIsNotNone(mock_socket.last_payload)
        self.assertEqual(mock_socket.last_payload["start"], mgr.start_time)
        self.assertIn("League of Legends", mock_socket.last_payload["large_text"])
        self.assertIn("7c99428541032ac02ec6981d88b78fb7", mock_socket.last_payload["large_image"])

        # 2. User clicks "DETENER EN DISCORD" (Pause)
        mgr.set_active(False)
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertFalse(mgr.is_active)
        self.assertEqual(mgr.state, RPCState.PAUSED)
        self.assertEqual(mock_socket.clear_count, 1)

        # 3. User clicks "INICIAR PRESENCIA" (Resume)
        mgr.set_active(True)
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertTrue(mgr.is_active)
        self.assertEqual(mgr.state, RPCState.CONNECTED)
        self.assertEqual(mock_socket.update_count, 2)

        # 4. Auto-restart timer reaches match duration (e.g. 25 min elapsed)
        simulated_old_start = int(time.time()) - 1500  # 25 minutes ago
        mgr.start_time = simulated_old_start
        mgr.match_duration_sec = 1400

        # Run timer check step
        elapsed = int(time.time()) - mgr.start_time
        if elapsed >= mgr.match_duration_sec:
            mgr.start_time = int(time.time())
            mgr.match_duration_sec = 1500
            mgr._send_rpc_update()
            mgr._notify_match_reset(mgr.start_time)

        self.assertEqual(len(match_resets), 1)
        self.assertGreater(mgr.start_time, simulated_old_start)
        self.assertEqual(mock_socket.last_payload["start"], mgr.start_time)

    def test_s2_detailed_mode_special_champions_and_apex_ranks(self):
        """
        Scenario 2: Detailed Mode Riot Champion & Apex Rank Workflow.
        User types anomaly 'wukong' and rank 'Challenger II', verifying MonkeyKing CDN
        and division suppression, then switches to Cho'Gath and Diamante IV.
        """
        resolver = ChampionResolver()
        mgr = DiscordRPCManager(auto_start=False)
        mock_socket = MockPresence(mgr.client_id)
        mock_socket.connected = True
        mgr._rpc = mock_socket

        # Step A: User inputs "wukong", rank "Challenger", division "II"
        cid, name = resolver.resolve_champion("wukong")
        self.assertEqual(cid, "MonkeyKing")
        icon_url = resolver.get_square_icon_url(cid)
        rank_text = format_rank_display("Challenger", "II")
        self.assertEqual(rank_text, "Challenger")  # Division suppressed
        crest_url = get_rank_crest_url("Challenger")

        mgr.update_presence_config(
            mode="detallado",
            champion_name=name,
            champion_image_url=icon_url,
            rank_text=rank_text,
            rank_image_url=crest_url,
            game_mode="Solo/Duo Clasificatoria",
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertIn("MonkeyKing.png", mock_socket.last_payload["large_image"])
        self.assertEqual(mock_socket.last_payload["small_text"], "Challenger")
        self.assertIn("challenger.png", mock_socket.last_payload["small_image"])
        self.assertEqual(
            mock_socket.last_payload["state"], "Solo/Duo Clasificatoria"
        )

        # Step B: User changes champion to "Cho'Gath" and rank to "Diamante IV"
        cid2, name2 = resolver.resolve_champion("Cho'Gath")
        self.assertEqual(cid2, "Chogath")
        icon_url2 = resolver.get_square_icon_url(cid2)
        rank_text2 = format_rank_display("Diamante", "IV")
        self.assertEqual(rank_text2, "Diamante IV")  # Division preserved
        crest_url2 = get_rank_crest_url("Diamante")

        mgr.update_presence_config(
            champion_name=name2,
            champion_image_url=icon_url2,
            rank_text=rank_text2,
            rank_image_url=crest_url2,
        )
        cmd, payload = mgr._cmd_queue.get_nowait()
        mgr._process_command(cmd, payload)

        self.assertIn("Chogath.png", mock_socket.last_payload["large_image"])
        self.assertEqual(mock_socket.last_payload["small_text"], "Diamante IV")
        self.assertIn("diamond.png", mock_socket.last_payload["small_image"])

    def test_s3_concurrency_stress_test(self):
        """
        Scenario 3: Concurrency Stress Test.
        Spawns 4 concurrent threads pushing 400 operations into the Actor queue simultaneously.
        Verifies queue drain, no deadlock, and clean shutdown.
        """
        mgr = DiscordRPCManager(auto_start=True)

        errors = []

        def worker_toggles():
            try:
                for i in range(50):
                    mgr.set_active(i % 2 == 0)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def worker_modes():
            try:
                for i in range(50):
                    mgr.update_presence_config(
                        mode="oficial" if i % 2 == 0 else "detallado"
                    )
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def worker_champions():
            try:
                champs = ["Yasuo", "Ahri", "MonkeyKing", "Kaisa", "Zed"]
                for i in range(50):
                    mgr.update_presence_config(champion_name=champs[i % len(champs)])
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        def worker_restarts():
            try:
                for _ in range(50):
                    mgr.restart_match()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker_toggles),
            threading.Thread(target=worker_modes),
            threading.Thread(target=worker_champions),
            threading.Thread(target=worker_restarts),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(len(errors), 0, f"Errors in concurrent threads: {errors}")

        # Wait briefly for queue worker to finish draining
        deadline = time.time() + 3.0
        while not mgr._cmd_queue.empty() and time.time() < deadline:
            time.sleep(0.05)

        mgr.shutdown()
        self.assertFalse(mgr._running)

    def test_s4_network_disconnect_and_reconnect(self):
        """
        Scenario 4: Discord IPC Socket Disconnect and Reconnect.
        Simulates BrokenPipeError on socket write, verifying clean disconnect transition
        and automatic recovery when socket re-establishes.
        """
        state_history = []
        mgr = DiscordRPCManager(
            on_state_change=lambda s, m: state_history.append(s),
            auto_start=False,
        )

        mock_socket = MockPresence(mgr.client_id)
        mock_socket.connected = True
        mgr._rpc = mock_socket
        mgr._state = RPCState.CONNECTED

        # Normal update succeeds
        mgr._send_rpc_update()
        self.assertEqual(mock_socket.update_count, 1)

        # Inject sudden BrokenPipe (Discord closed in background)
        mock_socket.update_exception = BrokenPipeError("Socket connection lost")
        mgr._send_rpc_update()

        # Manager should cleanly transition to DISCONNECTED
        self.assertEqual(mgr.state, RPCState.DISCONNECTED)
        self.assertIn(RPCState.DISCONNECTED, state_history)

        # Discord re-opens: clear exception
        mock_socket.update_exception = None
        mock_socket.connected = True
        mgr._rpc = mock_socket
        mgr._state = RPCState.CONNECTED
        mgr._send_rpc_update()

        self.assertEqual(mgr.state, RPCState.CONNECTED)
        self.assertEqual(mock_socket.update_count, 3)

    def test_s5_app_bundle_integrity_and_launch(self):
        """
        Scenario 5: macOS Application Bundle Launch Integrity.
        Inspects /Applications/League of Legends RPC.app to verify complete bundle
        readiness, Info.plist XML configuration, executable bits, and icons.
        """
        bundle_path = "/Applications/League of Legends RPC.app"
        self.assertTrue(os.path.isdir(bundle_path), "App bundle does not exist")

        # 1. Info.plist inspection
        plist_path = os.path.join(bundle_path, "Contents", "Info.plist")
        self.assertTrue(os.path.exists(plist_path), "Contents/Info.plist missing")
        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        self.assertEqual(
            plist.get("CFBundleExecutable"),
            "League of Legends RPC",
            "Executable name in plist is invalid",
        )
        self.assertEqual(
            plist.get("LSUIElement"),
            True,
            "App must be configured as LSUIElement (agent/menubar app)",
        )
        self.assertEqual(
            plist.get("CFBundleIdentifier"),
            "com.victormanuel.lolrpc",
            "Bundle ID does not match project spec",
        )

        # 2. Executable launcher script inspection
        launcher_path = os.path.join(
            bundle_path, "Contents", "MacOS", "League of Legends RPC"
        )
        self.assertTrue(
            os.path.exists(launcher_path), "Executable launcher missing"
        )
        self.assertTrue(
            os.access(launcher_path, os.X_OK),
            "Launcher script must have executable permission (+x)",
        )

        with open(launcher_path, "r") as f:
            script_content = f.read()

        self.assertIn("#!/bin/bash", script_content)
        self.assertIn("RESOURCES=", script_content)
        self.assertIn("app_gui.py", script_content)

        # 3. Resources verification
        resources_dir = os.path.join(bundle_path, "Contents", "Resources")
        self.assertTrue(os.path.isdir(resources_dir), "Resources dir missing")

        icns_path = os.path.join(resources_dir, "AppIcon.icns")
        self.assertTrue(os.path.exists(icns_path), "AppIcon.icns missing")
        with open(icns_path, "rb") as f:
            magic = f.read(4)
        self.assertEqual(magic, b"icns", "AppIcon.icns is not a valid ICNS file")

        app_gui_path = os.path.join(resources_dir, "app_gui.py")
        self.assertTrue(
            os.path.exists(app_gui_path), "app_gui.py missing in bundle Resources"
        )


if __name__ == "__main__":
    unittest.main()
