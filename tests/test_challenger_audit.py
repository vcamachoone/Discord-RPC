#!/usr/bin/env python3
"""
test_challenger_audit.py - Empirical Challenger Stress Test Suite

Adversarial stress harness for DiscordRPCManager:
1. High-concurrency stress test with 60+ threads hammering all 6 public methods simultaneously:
   set_active, state, is_connected, get_elapsed_seconds, update_presence_config, restart_match.
2. Malicious and invalid CONFIG_CHANGE payloads (attribute injection attempts:
   _running, _cmd_queue, _rpc, __class__, __dict__, _lock, _loop, shutdown, set_active,
   arbitrary keys, huge payload sizes, type confusion, non-dict payloads).
3. Socket teardown and reconnection under rapid disconnect storms (25+ drops,
   alternating socket errors, teardown under heavy traffic, shutdown during reconnect backoff).
"""

import os
import queue
import random
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
from discord_rpc_manager import ALLOWED_CONFIG_KEYS, DiscordRPCManager, RPCState
from tests.mocks import MockPresence


class AdversarialFaultyPresence(MockPresence):
    """
    MockPresence equipped with programmable fault sequences, artificial jitter,
    and telemetry tracking for close() / sock_writer.close() calls.
    """

    def __init__(self, client_id: str, **kwargs):
        super().__init__(client_id, **kwargs)
        self.connect_error_sequence: List[Optional[Exception]] = []
        self.update_error_sequence: List[Optional[Exception]] = []
        self.clear_error: Optional[Exception] = None
        self.close_error: Optional[Exception] = None
        self.jitter_sec: float = 0.0005
        self.sock_writer = MagicMock()
        self.sock_writer_close_count = 0

        def sock_close_side_effect():
            self.sock_writer_close_count += 1

        self.sock_writer.close.side_effect = sock_close_side_effect

    def connect(self) -> None:
        self.connect_count += 1
        if self.jitter_sec > 0:
            time.sleep(random.uniform(0.0, self.jitter_sec))
        if self.connect_error_sequence:
            err = self.connect_error_sequence.pop(0)
            if err:
                raise err
        elif self.connect_exception:
            raise self.connect_exception
        self.connected = True

    def update(self, **kwargs) -> Dict[str, Any]:
        self.update_count += 1
        if self.jitter_sec > 0:
            time.sleep(random.uniform(0.0, self.jitter_sec))
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


class TestChallengerConcurrencyStress(unittest.TestCase):
    """
    Empirical Challenge 1: 50+ concurrent threads hammering all DiscordRPCManager
    methods protected by threading.Lock.
    """

    def test_challenger_01_60_threads_simultaneous_hammering(self):
        """
        Simulate 60 concurrent threads simultaneously hammering:
        - set_active(bool)
        - state (property)
        - is_connected (property)
        - get_elapsed_seconds()
        - update_presence_config(...)
        - restart_match()
        Verifies absence of race conditions, deadlocks, data corruptions, and worker crashes.
        """
        shared_presence = AdversarialFaultyPresence("stress_client")
        state_changes = []
        state_lock = threading.Lock()

        def on_state(s, m):
            with state_lock:
                state_changes.append((s, m))

        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(
                client_id="stress_client",
                on_state_change=on_state,
                auto_start=True,
            )

            # Wait for connected state
            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(mgr.state, RPCState.CONNECTED)

            num_threads = 60
            ops_per_thread = 80  # 4,800 total operations under heavy concurrency
            errors = []
            threads = []
            stop_event = threading.Event()

            def worker_hammer(tid: int):
                try:
                    for i in range(ops_per_thread):
                        if stop_event.is_set():
                            break
                        action = (tid + i) % 6
                        if action == 0:
                            mgr.set_active(i % 2 == 0)
                        elif action == 1:
                            s = mgr.state
                            self.assertIn(s, [RPCState.CONNECTED, RPCState.CONNECTING, RPCState.DISCONNECTED, RPCState.PAUSED])
                        elif action == 2:
                            c = mgr.is_connected
                            self.assertIsInstance(c, bool)
                        elif action == 3:
                            elapsed = mgr.get_elapsed_seconds()
                            self.assertGreaterEqual(elapsed, 0)
                        elif action == 4:
                            mgr.update_presence_config(
                                champion_name=f"Champ_{tid}_{i}",
                                details=f"Wave {i}",
                                rank_text=f"Tier {tid % 9}",
                                mode="detallado" if i % 2 == 0 else "oficial",
                            )
                        elif action == 5:
                            mgr.restart_match()

                        # Small micro-pause to interleave context switches
                        if i % 10 == 0:
                            time.sleep(0.0001)
                except Exception as ex:
                    errors.append((tid, ex))

            start_t = time.time()
            for t_idx in range(num_threads):
                t = threading.Thread(target=worker_hammer, args=(t_idx,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=8.0)

            duration = time.time() - start_t

            # Verify NO thread hung or deadlocked
            alive_threads = [t for t in threads if t.is_alive()]
            if alive_threads:
                stop_event.set()
                self.fail(f"{len(alive_threads)} threads deadlocked / hung after {duration:.2f}s!")

            self.assertEqual(errors, [], f"Encountered concurrency errors: {errors}")

            # Verify background worker thread survived the onslaught
            self.assertTrue(mgr._worker_thread.is_alive(), "DiscordRPCManager worker thread crashed during hammering!")

            # Verify queue drains cleanly
            drain_deadline = time.time() + 4.0
            while not mgr._cmd_queue.empty() and time.time() < drain_deadline:
                time.sleep(0.02)
            self.assertEqual(mgr._cmd_queue.qsize(), 0, "Queue did not drain completely!")

            # Verify final shutdown is clean and non-blocking
            shut_start = time.time()
            mgr.shutdown()
            self.assertLess(time.time() - shut_start, 2.0, "Shutdown hung after concurrency hammering!")
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_challenger_02_lock_atomicity_and_invariants(self):
        """
        Stress-tests lock invariants:
        - is_connected MUST always return a boolean without crashing.
        - get_elapsed_seconds must return >= 0 even while start_time is concurrently modified.
        - Concurrent readers (30 threads) vs concurrent writers (30 threads) checking lock behavior.
        """
        shared_presence = AdversarialFaultyPresence("lock_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="lock_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            invariant_violations = []
            stop_flag = threading.Event()

            def reader_invariant_checker():
                while not stop_flag.is_set():
                    try:
                        conn = mgr.is_connected
                        if not isinstance(conn, bool):
                            invariant_violations.append(f"is_connected not bool: {type(conn)}")

                        st = mgr.state
                        if st not in [RPCState.CONNECTED, RPCState.CONNECTING, RPCState.DISCONNECTED, RPCState.PAUSED]:
                            invariant_violations.append(f"Invalid state: {st}")

                        elapsed = mgr.get_elapsed_seconds()
                        if elapsed < 0:
                            invariant_violations.append(f"Negative elapsed: {elapsed}")
                    except Exception as e:
                        invariant_violations.append(f"Reader exception: {e}")

            def writer_disrupter():
                for i in range(100):
                    mgr.set_active(i % 2 == 0)
                    mgr.restart_match()
                    time.sleep(0.001)

            readers = [threading.Thread(target=reader_invariant_checker) for _ in range(30)]
            writers = [threading.Thread(target=writer_disrupter) for _ in range(30)]

            for r in readers:
                r.start()
            for w in writers:
                w.start()

            for w in writers:
                w.join(timeout=5.0)

            stop_flag.set()
            for r in readers:
                r.join(timeout=2.0)

            self.assertEqual(invariant_violations, [], f"Invariant violations detected: {invariant_violations}")
            mgr.shutdown()


class TestChallengerMaliciousPayloads(unittest.TestCase):
    """
    Empirical Challenge 2: Malicious and invalid CONFIG_CHANGE payloads,
    attribute injection attacks, malformed structures, and type confusion.
    """

    def test_challenger_03_private_attribute_injection_defense(self):
        """
        Adversarially attempts to inject private members, methods, and system attributes:
        _running, _cmd_queue, _rpc, _loop, _lock, _worker_thread, __class__, __dict__,
        shutdown, set_active, restart_match, client_id, on_state_change, on_match_reset.
        """
        shared_presence = AdversarialFaultyPresence("attack_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="attack_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            orig_running = mgr._running
            orig_queue = mgr._cmd_queue
            orig_rpc = mgr._rpc
            orig_loop = mgr._loop
            orig_lock = mgr._lock
            orig_thread = mgr._worker_thread
            orig_class = mgr.__class__
            orig_client_id = mgr.client_id

            malicious_attacks = {
                "_running": False,
                "_cmd_queue": "hacked_queue",
                "_rpc": None,
                "_loop": "fake_loop",
                "_lock": "broken_lock",
                "_worker_thread": "dead_thread",
                "__class__": dict,
                "__dict__": {},
                "shutdown": "nuked",
                "set_active": "overwritten",
                "restart_match": lambda: 12345,
                "client_id": "999999999999999999",
                "on_state_change": "hijacked",
                "on_match_reset": "hijacked",
            }

            # Dispatch via public API
            mgr.update_presence_config(**malicious_attacks)

            # Wait for worker to process queue
            time.sleep(0.2)

            # Assert internal attributes were completely untouched
            self.assertEqual(mgr._running, orig_running, "_running was compromised!")
            self.assertEqual(mgr._cmd_queue, orig_queue, "_cmd_queue was compromised!")
            self.assertIsNotNone(mgr._rpc, "_rpc was compromised!")
            self.assertEqual(mgr._loop, orig_loop, "_loop was compromised!")
            self.assertEqual(mgr._lock, orig_lock, "_lock was compromised!")
            self.assertEqual(mgr._worker_thread, orig_thread, "_worker_thread was compromised!")
            self.assertEqual(mgr.__class__, orig_class, "__class__ was compromised!")
            self.assertEqual(mgr.client_id, orig_client_id, "client_id was compromised!")
            self.assertTrue(callable(mgr.shutdown), "shutdown method was corrupted!")
            self.assertTrue(callable(mgr.set_active), "set_active method was corrupted!")
            self.assertTrue(callable(mgr.restart_match), "restart_match method was corrupted!")

            # Assert worker thread is still running and healthy
            self.assertTrue(mgr._worker_thread.is_alive(), "Worker thread died from injection attack!")

            mgr.shutdown()

    def test_challenger_04_arbitrary_and_unauthorized_keys_defense(self):
        """
        Sends arbitrary, unexpected, and exploit-like keys to verify they are dropped.
        """
        shared_presence = AdversarialFaultyPresence("arbitrary_keys_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="arbitrary_keys_client", auto_start=True)

            arbitrary_payload = {
                "admin": True,
                "__proto__": {"polluted": True},
                "sudo": True,
                "eval": "import os; os.system('echo pwned')",
                "arbitrary_config_flag_abc": 12345,
                "token": "secret_token_leak",
                # Valid keys mixed in
                "champion_name": "Ahri",
                "mode": "detallado",
            }

            mgr.update_presence_config(**arbitrary_payload)
            time.sleep(0.15)

            # Verify arbitrary keys were NOT set on the instance
            for key in ["admin", "__proto__", "sudo", "eval", "arbitrary_config_flag_abc", "token"]:
                self.assertFalse(hasattr(mgr, key), f"Arbitrary key '{key}' was improperly attached!")

            # Verify legitimate allowed keys WERE set
            self.assertEqual(mgr.champion_name, "Ahri")
            self.assertEqual(mgr.mode, "detallado")

            mgr.shutdown()

    def test_challenger_05_malformed_types_in_allowed_keys(self):
        """
        Adversarially feeds type-mismatched or abnormal values into ALLOWED_CONFIG_KEYS:
        - mode: None, 9999, huge string (50k chars)
        - champion_name: None, integer, empty string
        - details: None, integer
        - autoreset: None, "maybe", integer
        Verifies presence update handles or catches errors without worker crashing.
        """
        shared_presence = AdversarialFaultyPresence("types_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="types_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            # Massive string payload
            huge_name = "A" * 50000
            mgr.update_presence_config(
                mode=None,
                champion_name=huge_name,
                details=None,
                game_mode=None,
                autoreset=None,
            )
            time.sleep(0.2)

            self.assertTrue(mgr._worker_thread.is_alive(), "Worker died on malformed value types!")

            # Restore normal configuration and verify normal operation
            mgr.update_presence_config(
                mode="detallado",
                champion_name="Lux",
                details="Partida normal",
                game_mode="Grieta del Invocador",
                autoreset=True,
            )
            time.sleep(0.2)

            self.assertEqual(mgr.champion_name, "Lux")
            self.assertEqual(mgr.mode, "detallado")
            self.assertTrue(mgr._worker_thread.is_alive())

            mgr.shutdown()

    def test_challenger_06_public_api_kwargs_coalescing_resilience(self):
        """
        Verifies that high-frequency rapid bursts of CONFIG_CHANGE via the public API
        update_presence_config are cleanly coalesced without race conditions or crashes.
        """
        shared_presence = AdversarialFaultyPresence("coalesce_fuzz_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="coalesce_fuzz_client", auto_start=False)

            # Burst 500 config changes with various keys
            for i in range(500):
                mgr.update_presence_config(
                    champion_name=f"Champ_{i}",
                    details=f"Details_{i}",
                    mode="detallado" if i % 2 == 0 else "oficial",
                )

            self.assertEqual(mgr._cmd_queue.qsize(), 500)

            # Start worker thread
            mgr._worker_thread.start()

            # Wait for queue to drain
            drain_deadline = time.time() + 3.0
            while not mgr._cmd_queue.empty() and time.time() < drain_deadline:
                time.sleep(0.02)

            time.sleep(0.1)

            # Worker thread must be alive and final values applied
            self.assertTrue(mgr._worker_thread.is_alive(), "Worker died during rapid coalescing!")
            self.assertEqual(mgr.champion_name, "Champ_499")
            self.assertEqual(mgr.details, "Details_499")

            mgr.shutdown()

    def test_challenger_06b_unhandled_non_dict_in_coalescer_defect_probe(self):
        """
        REGRESSION TEST FOR COALESCER RESILIENCE:
        Verifies that queuing non-dict payloads (or None) with 'CONFIG_CHANGE'
        does NOT crash the worker thread, and subsequent valid configurations
        are processed cleanly.
        """
        shared_presence = AdversarialFaultyPresence("probe_client")
        with patch("discord_rpc_manager.Presence", return_value=shared_presence):
            mgr = DiscordRPCManager(client_id="probe_client", auto_start=False)

            # Enqueue non-dict payload followed by another CONFIG_CHANGE
            mgr._cmd_queue.put(("CONFIG_CHANGE", None))
            mgr._cmd_queue.put(("CONFIG_CHANGE", {"champion_name": "Yasuo"}))

            mgr._worker_thread.start()
            # Allow brief moment for worker to process queued items
            time.sleep(0.2)

            self.assertTrue(
                mgr._worker_thread.is_alive(),
                "Worker thread should survive when non-dict payload hits coalescer",
            )
            self.assertTrue(mgr.is_active is not None)
            self.assertEqual(mgr.champion_name, "Yasuo")
            mgr.shutdown()


class TestChallengerSocketTeardownAndReconnect(unittest.TestCase):
    """
    Empirical Challenge 3: Socket teardown and reconnection under simulated rapid disconnects.
    """

    def test_challenger_07_rapid_disconnect_storm_25_cycles(self):
        """
        Simulate a rapid storm of 25 consecutive socket drops with alternating network errors:
        BrokenPipeError, ConnectionResetError, InvalidPipe, DiscordNotFound, PipeClosed,
        ResponseTimeout, OSError.
        Verifies:
        - Each dropped connection records a transition to DISCONNECTED.
        - _safe_close_rpc is invoked each time and sock_writer.close() is called.
        - Worker survives 25 consecutive drops without hanging or crashing.
        - Clean reconnect to CONNECTED occurs when socket stabilizes.
        """
        from pypresence import DiscordNotFound, InvalidPipe, PipeClosed, ResponseTimeout

        errors = [
            BrokenPipeError("Broken pipe"),
            ConnectionResetError("Connection reset"),
            InvalidPipe(),
            DiscordNotFound(),
            PipeClosed(),
            ResponseTimeout(),
            OSError("Socket closed"),
        ]

        active_presence: Optional[AdversarialFaultyPresence] = None
        created_presences: List[AdversarialFaultyPresence] = []
        presence_lock = threading.Lock()

        def make_presence(client_id, **kwargs):
            nonlocal active_presence
            p = AdversarialFaultyPresence(client_id, **kwargs)
            with presence_lock:
                active_presence = p
                created_presences.append(p)
            return p

        state_history = []
        state_lock = threading.Lock()

        def on_state(s, m):
            with state_lock:
                state_history.append((s, m))

        with patch("discord_rpc_manager.Presence", side_effect=make_presence):
            mgr = DiscordRPCManager(
                client_id="storm_client",
                on_state_change=on_state,
                auto_start=True,
            )

            # Wait for initial connection
            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(mgr.state, RPCState.CONNECTED)

            # Deliver 25 rapid disconnect faults
            for i in range(25):
                fault = errors[i % len(errors)]
                history_len_before = len(state_history)

                with presence_lock:
                    if active_presence:
                        active_presence.update_exception = fault

                # Trigger update to trip fault
                mgr.update_presence_config(details=f"Storm trip {i}")

                # Wait for state transition to be recorded
                trans_deadline = time.time() + 2.0
                while len(state_history) <= history_len_before and time.time() < trans_deadline:
                    time.sleep(0.005)

                # Verify DISCONNECTED state was notified
                recent_states = [s for s, m in state_history[history_len_before:]]
                self.assertIn(
                    RPCState.DISCONNECTED,
                    recent_states,
                    f"Iteration {i} with fault {type(fault).__name__} failed to notify DISCONNECTED",
                )

                # Reset fault on active presence to allow reconnect
                with presence_lock:
                    if active_presence:
                        active_presence.update_exception = None

                # Wait for reconnect back to CONNECTED
                conn_deadline = time.time() + 5.0
                while mgr.state != RPCState.CONNECTED and time.time() < conn_deadline:
                    time.sleep(0.01)

                self.assertEqual(mgr.state, RPCState.CONNECTED, f"Iteration {i} failed to reconnect to Discord!")

            # Verify all dropped instances had their sock_writer and close() called
            with presence_lock:
                for idx, p in enumerate(created_presences[:-1]):  # all except current active
                    self.assertTrue(p.closed, f"Presence #{idx} was not closed!")
                    self.assertGreaterEqual(
                        p.sock_writer_close_count, 1, f"sock_writer.close() was not called on Presence #{idx}!"
                    )

            self.assertTrue(mgr._worker_thread.is_alive(), "Worker died during 25-cycle disconnect storm!")
            mgr.shutdown()
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_challenger_08_socket_severing_under_high_traffic(self):
        """
        Pumps continuous config changes while abruptly severing the socket.
        Verifies zero crash, unhandled exceptions, or thread termination.
        """
        active_presence = None
        p_lock = threading.Lock()

        def make_presence(client_id, **kwargs):
            nonlocal active_presence
            p = AdversarialFaultyPresence(client_id, **kwargs)
            with p_lock:
                active_presence = p
            return p

        with patch("discord_rpc_manager.Presence", side_effect=make_presence):
            mgr = DiscordRPCManager(client_id="traffic_sever_client", auto_start=True)

            deadline = time.time() + 2.0
            while mgr.state != RPCState.CONNECTED and time.time() < deadline:
                time.sleep(0.01)

            traffic_errors = []
            stop_traffic = threading.Event()

            def traffic_generator():
                i = 0
                while not stop_traffic.is_set():
                    try:
                        mgr.update_presence_config(details=f"Traffic {i}")
                        i += 1
                        time.sleep(0.001)
                    except Exception as e:
                        traffic_errors.append(e)

            traffic_thread = threading.Thread(target=traffic_generator)
            traffic_thread.start()

            # Let traffic flow for 0.1s
            time.sleep(0.1)

            # Abruptly sever socket
            with p_lock:
                if active_presence:
                    active_presence.update_exception = BrokenPipeError("Sudden pipe severing")

            # Let traffic continue colliding with severed socket
            time.sleep(0.2)

            stop_traffic.set()
            traffic_thread.join(timeout=2.0)

            self.assertEqual(traffic_errors, [], f"Traffic generator suffered exceptions: {traffic_errors}")
            self.assertTrue(mgr._worker_thread.is_alive(), "Worker died when pipe severed under traffic!")

            mgr.shutdown()

    def test_challenger_09_shutdown_during_reconnect_backoff(self):
        """
        Verifies calling shutdown() when the worker is waiting in reconnect backoff
        wakes immediately (<0.8s) via command queue rather than sleeping for full timeout.
        """
        from pypresence import DiscordNotFound

        def failing_presence(client_id, **kwargs):
            p = AdversarialFaultyPresence(client_id, **kwargs)
            p.connect_exception = DiscordNotFound()
            return p

        with patch("discord_rpc_manager.Presence", side_effect=failing_presence):
            mgr = DiscordRPCManager(client_id="backoff_shutdown", auto_start=True)

            # Wait until it enters DISCONNECTED backoff
            time.sleep(0.2)
            self.assertEqual(mgr.state, RPCState.DISCONNECTED)

            # Shutdown should wake up queue immediately
            start_shut = time.time()
            mgr.shutdown()
            shut_duration = time.time() - start_shut

            self.assertLess(shut_duration, 0.8, f"Shutdown took {shut_duration:.2f}s — blocked on backoff!")
            self.assertFalse(mgr._worker_thread.is_alive())

    def test_challenger_10_safe_close_rpc_idempotency_and_robustness(self):
        """
        Directly tests _safe_close_rpc robustness when:
        - rpc is None
        - sock_writer is missing
        - sock_writer.close() raises an exception
        - rpc.close() raises an exception
        Verifies _safe_close_rpc never raises and safely clears _rpc to None.
        """
        mgr = DiscordRPCManager(client_id="robust_close", auto_start=False)

        # 1. rpc is None: should not raise
        try:
            mgr._safe_close_rpc()
        except Exception as e:
            self.fail(f"_safe_close_rpc raised when _rpc is None: {e}")

        # 2. rpc has buggy sock_writer and buggy close()
        broken_rpc = MagicMock()
        broken_rpc.sock_writer.close.side_effect = OSError("sock_writer closed failed")
        broken_rpc.close.side_effect = BrokenPipeError("close failed")

        mgr._rpc = broken_rpc
        try:
            mgr._safe_close_rpc()
        except Exception as e:
            self.fail(f"_safe_close_rpc raised when inner closes raised: {e}")

        self.assertIsNone(mgr._rpc, "_rpc was not set to None after _safe_close_rpc!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
