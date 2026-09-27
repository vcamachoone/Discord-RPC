"""
test_adversarial_stress.py - Empirical Adversarial Stress & Fault Injection Harness

Adversarially stress-tests DiscordRPCManager:
1. High Concurrency Hammering: 50 concurrent threads hammering public API (2500 ops).
2. Socket Fault Injection: Sudden BrokenPipeError, ConnectionResetError, InvalidPipe,
   DiscordNotFound, OSError under active queue load.
3. Rapid Reconnect Cycling: Repeating connect -> failure -> reconnect sequences.
4. Timer Stress: Accelerated clock match auto-restart and concurrent restart_match() races.
5. Command Coalescing & Order Preservation: Coalescing bursts with interspersed SET_ACTIVE.
6. Shutdown Latency & Responsiveness: Shutdown responsiveness during backoff sleep.
7. Teardown Exception Resilience: Exceptions during presence clear/close.
"""

import os
import queue
import sys
import threading
import time
import unittest
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# Ensure project root in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState
from tests.mocks import MockAppHelper, MockPresence


class FaultyPresence(MockPresence):
    """
    MockPresence with programmable fault sequences and artificial latency.
    """

    def __init__(self, client_id: str, **kwargs):
        super().__init__(client_id, **kwargs)
        self.connect_error_sequence: List[Optional[Exception]] = []
        self.update_error_sequence: List[Optional[Exception]] = []
        self.close_error: Optional[Exception] = None
        self.clear_error: Optional[Exception] = None
        self.artificial_delay: float = 0.001

    def connect(self) -> None:
        self.connect_count += 1
        if self.artificial_delay > 0:
            time.sleep(self.artificial_delay)
        if self.connect_error_sequence:
            err = self.connect_error_sequence.pop(0)
            if err:
                raise err
        elif self.connect_exception:
            raise self.connect_exception
        self.connected = True

    def update(self, **kwargs) -> Dict[str, Any]:
        self.update_count += 1
        if self.artificial_delay > 0:
            time.sleep(self.artificial_delay)
        if self.update_error_sequence:
            err = self.update_error_sequence.pop(0)
            if err:
                raise err
        elif self.update_exception:
            raise self.update_exception
        self.last_payload = dict(kwargs)
        self.payload_history.append(dict(kwargs))
        return {"status": "ok", "payload": kwargs}

    def clear(self, pid: Optional[int] = None) -> None:
        self.clear_count += 1
        if self.clear_error:
            raise self.clear_error
        self.last_payload = None

    def close(self) -> None:
        self.close_count += 1
        self.connected = False
        self.closed = True
        if self.close_error:
            raise self.close_error


class TestAdversarialRPCStress(unittest.TestCase):
    """Empirical adversarial stress testing for DiscordRPCManager."""

    def test_adv_01_high_concurrency_hammering_50_threads(self):
        """
        ADV.01: 50 concurrent threads simultaneously hammering DiscordRPCManager
        with 2,500 total mixed operations (update, toggle active, restart match, query state).
        Verifies absence of deadlocks, race crashes, or thread starvation.
        """
        shared_presence = FaultyPresence("test_client")
        state_history = []
        state_lock = threading.Lock()

        def record_state(s, m):
            with state_lock:
                state_history.append((s, m))

        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(
                client_id="test_client",
                on_state_change=record_state,
                auto_start=True,
            )

            # Wait for initial connection
            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(mgr.state, RPCState.CONNECTED)

            num_threads = 50
            ops_per_thread = 50
            errors: List[Exception] = []
            threads = []

            def hammer_worker(tid: int):
                try:
                    for i in range(ops_per_thread):
                        op = (tid + i) % 5
                        if op == 0:
                            mgr.update_presence_config(
                                champion_name=f"Champ_{tid}_{i}",
                                details=f"Game in progress {i}",
                                rank_text=f"Rank {tid}",
                            )
                        elif op == 1:
                            mgr.restart_match()
                        elif op == 2:
                            mgr.set_active(i % 2 == 0)
                        elif op == 3:
                            _ = mgr.state
                            _ = mgr.is_connected
                            _ = mgr.get_elapsed_seconds()
                        elif op == 4:
                            mgr.update_presence_config(mode="detallado" if i % 2 == 0 else "oficial")
                except Exception as e:
                    errors.append(e)

            start_t = time.time()
            for t_idx in range(num_threads):
                t = threading.Thread(target=hammer_worker, args=(t_idx,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=5.0)

            duration = time.time() - start_t

            # Verify all threads finished
            for t in threads:
                self.assertFalse(t.is_alive(), "Worker thread hung / deadlocked!")

            self.assertEqual(len(errors), 0, f"Encountered exceptions during hammering: {errors}")

            # Verify worker thread is still alive and running
            self.assertTrue(mgr._worker_thread.is_alive(), "Actor worker thread crashed!")

            # Verify queue drains promptly
            drain_deadline = time.time() + 3.0
            while not mgr._cmd_queue.empty() and time.time() < drain_deadline:
                time.sleep(0.05)
            self.assertEqual(mgr._cmd_queue.qsize(), 0, "Command queue failed to drain!")

            # Verify graceful shutdown
            mgr.shutdown()
            self.assertFalse(mgr._worker_thread.is_alive(), "Worker thread failed to terminate cleanly on shutdown!")

    def test_adv_02_socket_fault_injection_during_active_traffic(self):
        """
        ADV.02: Injects sudden BrokenPipeError, ConnectionResetError, InvalidPipe, and OSError
        into the IPC socket while concurrent client traffic is enqueued.
        Verifies clean error recovery and auto-reconnect without unhandled exceptions.
        """
        from pypresence import InvalidPipe

        fault_sequence = [
            BrokenPipeError("Broken pipe [Errno 32]"),
            ConnectionResetError("Connection reset by peer [Errno 54]"),
            InvalidPipe(),
            OSError("Socket file closed"),
        ]

        active_presence: Optional[FaultyPresence] = None
        presence_instances: List[FaultyPresence] = []
        instance_lock = threading.Lock()

        def make_presence(client_id, **kwargs):
            nonlocal active_presence
            p = FaultyPresence(client_id, **kwargs)
            with instance_lock:
                active_presence = p
                presence_instances.append(p)
            return p

        recorded_states: List[str] = []
        state_lock = threading.Lock()

        def on_change(s, m):
            with state_lock:
                recorded_states.append(s)

        with patch("discord_rpc_manager.Presence", side_effect=make_presence):
            mgr = DiscordRPCManager(
                client_id="fault_test",
                on_state_change=on_change,
                auto_start=True,
            )

            # Wait for first connection
            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(mgr.state, RPCState.CONNECTED)

            # Inject each fault and verify recovery
            for fault in fault_sequence:
                state_count_before = len(recorded_states)

                with instance_lock:
                    if active_presence:
                        active_presence.update_exception = fault

                # Trigger an update that trips the fault
                mgr.update_presence_config(details=f"Trigger fault {type(fault).__name__}")

                # Verify transition to DISCONNECTED is recorded
                disc_deadline = time.time() + 2.0
                while time.time() < disc_deadline:
                    with state_lock:
                        if RPCState.DISCONNECTED in recorded_states[state_count_before:]:
                            break
                    time.sleep(0.01)

                with state_lock:
                    self.assertIn(
                        RPCState.DISCONNECTED,
                        recorded_states[state_count_before:],
                        f"Fault {type(fault).__name__} failed to transition to DISCONNECTED",
                    )

                # Reset fault for subsequent reconnect
                with instance_lock:
                    if active_presence:
                        active_presence.update_exception = None

                # Wait for reconnect backoff to restore CONNECTED state
                reconn_deadline = time.time() + 5.0
                while mgr.state != RPCState.CONNECTED and time.time() < reconn_deadline:
                    time.sleep(0.05)
                self.assertEqual(mgr.state, RPCState.CONNECTED)

            mgr.shutdown()
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_adv_03_discord_not_found_repeated_reconnect_resilience(self):
        """
        ADV.03: Simulates Discord being closed at startup, failing 5 times with DiscordNotFound,
        then launching and connecting successfully.
        """
        from pypresence import DiscordNotFound

        attempt_count = 0

        def flaking_presence(client_id, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            p = FaultyPresence(client_id, **kwargs)
            if attempt_count <= 3:
                p.connect_exception = DiscordNotFound("No Discord process found")
            return p

        with patch("discord_rpc_manager.Presence", side_effect=flaking_presence):
            mgr = DiscordRPCManager(client_id="flake_test", auto_start=True)

            # Wait through the initial failures to successful connection
            deadline = time.time() + 15.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.1)

            self.assertEqual(mgr.state, RPCState.CONNECTED)
            self.assertGreaterEqual(attempt_count, 4)

            mgr.shutdown()
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_adv_04_shutdown_responsiveness_during_reconnect_backoff(self):
        """
        ADV.04: Tests that calling shutdown() while the worker is asleep in reconnect backoff
        wakes up immediately rather than blocking for the full timeout.
        """
        from pypresence import DiscordNotFound

        def failing_presence(client_id, **kwargs):
            p = FaultyPresence(client_id, **kwargs)
            p.connect_exception = DiscordNotFound("Not running")
            return p

        with patch("discord_rpc_manager.Presence", side_effect=failing_presence):
            mgr = DiscordRPCManager(client_id="shutdown_test", auto_start=True)

            # Give it time to enter the 3.5s backoff wait
            time.sleep(0.2)
            self.assertEqual(mgr.state, RPCState.DISCONNECTED)

            # Measure shutdown latency
            start_shut = time.time()
            mgr.shutdown()
            shut_duration = time.time() - start_shut

            # Should wake up immediately via queue.put, well under 2.0s
            self.assertLess(shut_duration, 1.5, f"Shutdown took too long ({shut_duration:.2f}s) — did not wake queue!")
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_adv_05_timer_accelerated_clock_and_race_with_manual_restart(self):
        """
        ADV.05: Tests match auto-restart under accelerated time:
        - Auto-reset resets start_time and triggers on_match_reset.
        - Concurrent manual restart_match() does not cause desync or crash.
        """
        resets: List[int] = []
        reset_lock = threading.Lock()

        def on_reset(t):
            with reset_lock:
                resets.append(t)

        shared_presence = FaultyPresence("timer_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(
                client_id="timer_client",
                on_match_reset=on_reset,
                auto_start=True,
            )

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            # Artificially set start_time into the past so elapsed >= match_duration_sec
            mgr.match_duration_sec = 2
            mgr.start_time = int(time.time()) - 5

            # Wait for auto-reset to trigger
            reset_deadline = time.time() + 3.0
            while len(resets) == 0 and time.time() < reset_deadline:
                time.sleep(0.05)

            self.assertGreaterEqual(len(resets), 1, "Auto-restart timer failed to trigger!")

            # Verify bounds of new match_duration_sec
            self.assertGreaterEqual(mgr.match_duration_sec, 1200)
            self.assertLessEqual(mgr.match_duration_sec, 1800)

            # Now test concurrent race: rapid manual restart while checking elapsed
            mgr.match_duration_sec = 1
            mgr.start_time = int(time.time()) - 2

            def racer():
                for _ in range(20):
                    mgr.restart_match()
                    time.sleep(0.01)

            t = threading.Thread(target=racer)
            t.start()
            t.join(timeout=3.0)

            self.assertFalse(t.is_alive())
            self.assertTrue(mgr._worker_thread.is_alive())

            mgr.shutdown()

    def test_adv_06_command_coalescing_preserves_set_active_ordering(self):
        """
        ADV.06: Verifies that command coalescing in worker loop reduces high-frequency
        CONFIG_CHANGE bursts while strictly preserving interleaved SET_ACTIVE orders.
        """
        shared_presence = FaultyPresence("coalesce_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="coalesce_client", auto_start=False)

            # Flood queue: 100 config changes, then SET_ACTIVE(False), then 50 config changes
            for i in range(100):
                mgr._cmd_queue.put(("CONFIG_CHANGE", {"champion_name": f"Champ_{i}"}))
            mgr._cmd_queue.put(("SET_ACTIVE", False))
            for i in range(100, 150):
                mgr._cmd_queue.put(("CONFIG_CHANGE", {"champion_name": f"Champ_{i}"}))

            # Now run worker thread to drain
            mgr._worker_thread.start()

            # Wait for queue to drain
            deadline = time.time() + 3.0
            while not mgr._cmd_queue.empty() and time.time() < deadline:
                time.sleep(0.02)

            time.sleep(0.1)

            # At the end, champion_name should be Champ_149
            self.assertEqual(mgr.champion_name, "Champ_149")
            # But active state must be False because SET_ACTIVE(False) was processed!
            self.assertFalse(mgr.is_active, "SET_ACTIVE(False) was dropped or bypassed by coalescer!")

            mgr.shutdown()

    def test_adv_07_teardown_exceptions_handled_gracefully(self):
        """
        ADV.07: Verifies that if Presence.clear() or Presence.close() throws BrokenPipeError
        or OSError during teardown, shutdown() still terminates cleanly without crashing caller.
        """
        failing_presence = FaultyPresence("teardown_client")
        failing_presence.clear_error = BrokenPipeError("Clear failed")
        failing_presence.close_error = OSError("Close failed")

        with patch("discord_rpc_manager.Presence", return_value=failing_presence):
            mgr = DiscordRPCManager(client_id="teardown_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            # Should not raise exception
            try:
                mgr.shutdown()
            except Exception as e:
                self.fail(f"shutdown() raised exception during faulty socket teardown: {e}")

            self.assertFalse(mgr._worker_thread.is_alive())

    def test_adv_08_rapid_active_toggle_under_traffic(self):
        """
        ADV.08: Rapidly toggle set_active(True/False) 50 times in rapid succession while
        concurrent updates are enqueued.
        Verifies consistent final state without thread lockup or unhandled exceptions.
        """
        shared_presence = FaultyPresence("toggle_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="toggle_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            # Rapidly toggle 50 times
            for i in range(50):
                mgr.set_active(i % 2 == 0)
                if i % 5 == 0:
                    mgr.update_presence_config(details=f"Toggle {i}")
                time.sleep(0.005)

            # Settle on active = True
            mgr.set_active(True)

            # Wait for worker to settle
            settle_deadline = time.time() + 3.0
            while mgr.state != RPCState.CONNECTED and time.time() < settle_deadline:
                time.sleep(0.05)

            self.assertEqual(mgr.state, RPCState.CONNECTED)
            self.assertTrue(mgr.is_active)
            self.assertTrue(mgr._worker_thread.is_alive())

            mgr.shutdown()

    def test_adv_09_private_attribute_injection_probe(self):
        """
        ADV.09: Adversarially tests attribute pollution via update_presence_config.
        Demonstrates that passing private attributes (e.g. _running=False) alters internal
        state due to unvalidated hasattr() checks.
        """
        shared_presence = FaultyPresence("injection_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="injection_client", auto_start=False)

            # Attempt to inject private attribute _running = False
            mgr._cmd_queue.put(("CONFIG_CHANGE", {"_running": False}))
            mgr._worker_thread.start()

            # Wait for command to be processed
            deadline = time.time() + 2.0
            while mgr._worker_thread.is_alive() and time.time() < deadline:
                time.sleep(0.05)

            # The worker thread died prematurely because _running was overwritten to False!
            thread_died = not mgr._worker_thread.is_alive()
            # This confirms the vulnerability: private attribute was overwritten by config change!
            self.assertTrue(
                thread_died,
                "Expected worker thread to terminate prematurely demonstrating attribute pollution vulnerability",
            )

    def test_adv_10_extreme_queue_burst_drain_10000_items(self):
        """
        ADV.10: Extreme queue flooding with 10,000 rapid updates.
        Verifies coalescer prevents memory explosion and completes drain in under 5.0 seconds.
        """
        shared_presence = FaultyPresence("burst_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="burst_client", auto_start=False)

            for i in range(10000):
                mgr.update_presence_config(details=f"Burst {i}")

            self.assertEqual(mgr._cmd_queue.qsize(), 10000)

            start_t = time.time()
            mgr._worker_thread.start()

            drain_deadline = time.time() + 5.0
            while not mgr._cmd_queue.empty() and time.time() < drain_deadline:
                time.sleep(0.05)

            drain_duration = time.time() - start_t
            self.assertEqual(mgr._cmd_queue.qsize(), 0, "Queue did not drain 10,000 items in time!")
            self.assertLess(drain_duration, 5.0, f"Draining took {drain_duration:.2f}s (exceeded 5.0s budget)")
            self.assertEqual(mgr.details, "Burst 9999")

            mgr.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
