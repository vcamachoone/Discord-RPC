"""
Prototype test to verify the in-flight connection abortion fix for DiscordRPCManager.
"""
import asyncio
import queue
import sys
import os
sys.path.insert(0, "/Users/victormanuel/discord-rpc")
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import discord_rpc_manager
from discord_rpc_manager import DiscordRPCManager, RPCState, RECONNECT_EXCEPTIONS


class PatchedDiscordRPCManager(DiscordRPCManager):
    def __init__(self, *args, **kwargs):
        self._connecting_rpc = None
        super().__init__(*args, **kwargs)

    def _safe_close_target(self, target) -> None:
        """Safely terminates a Presence target instance, its socket, and event loop."""
        if not target:
            return

        setattr(target, "_aborted", True)

        # 1. Forcefully abort socket transport to break any in-flight reads
        try:
            sock_writer = getattr(target, "sock_writer", None)
            if sock_writer is not None:
                try:
                    transport = getattr(sock_writer, "transport", None)
                    if transport is not None and hasattr(transport, "abort"):
                        transport.abort()
                except Exception:
                    pass
                try:
                    if hasattr(sock_writer, "close"):
                        sock_writer.close()
                except Exception:
                    pass
        except Exception:
            pass

        # 2. Stop running or pending event loop thread-safely
        try:
            loop = getattr(target, "loop", None)
            if loop is not None:
                def _cancel_and_stop():
                    try:
                        for task in asyncio.all_tasks(loop):
                            task.cancel()
                            try:
                                task._log_destroy_pending = False
                            except Exception:
                                pass
                    except Exception:
                        pass
                    try:
                        loop.stop()
                    except Exception:
                        pass

                try:
                    if hasattr(loop, "is_running") and loop.is_running():
                        if hasattr(loop, "call_soon_threadsafe"):
                            loop.call_soon_threadsafe(_cancel_and_stop)
                        elif hasattr(loop, "stop"):
                            loop.stop()
                    elif hasattr(loop, "stop"):
                        loop.stop()
                except Exception:
                    pass
        except Exception:
            pass

        # 3. Close the presence instance
        try:
            if hasattr(target, "close"):
                target.close()
        except Exception:
            pass

    def _safe_close_rpc(self) -> None:
        """Safely closes Discord RPC instance and in-flight connecting instance."""
        with self._lock:
            rpc = self._rpc
            self._rpc = None
            connecting = self._connecting_rpc
            self._connecting_rpc = None

        for target in (rpc, connecting):
            self._safe_close_target(target)

        # Also ensure manager event loop is stopped if active
        try:
            if self._loop is not None:
                if hasattr(self._loop, "is_running") and self._loop.is_running():
                    if hasattr(self._loop, "call_soon_threadsafe") and hasattr(self._loop, "stop"):
                        self._loop.call_soon_threadsafe(self._loop.stop)
                elif hasattr(self._loop, "stop"):
                    self._loop.stop()
        except Exception:
            pass

    def _worker_loop(self) -> None:
        """Actor loop with in-flight connection tracking and abortion."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while self._running:
            # 1. Connection & Reconnection Management
            with self._lock:
                active = self.is_active
                rpc = self._rpc
            if active and (rpc is None):
                self._notify_state(RPCState.CONNECTING, "Conectando a Discord...")
                new_rpc = None
                try:
                    new_rpc = discord_rpc_manager.Presence(self.client_id, loop=self._loop)
                    with self._lock:
                        if not self._running:
                            break
                        self._connecting_rpc = new_rpc

                    # Intercept update_event_loop to stop any freshly created loop if aborted
                    if hasattr(new_rpc, "update_event_loop"):
                        orig_update_loop = new_rpc.update_event_loop
                        def _tracked_update_loop(loop_arg, _rpc=new_rpc):
                            orig_update_loop(loop_arg)
                            if getattr(_rpc, "_aborted", False) or not self._running:
                                try:
                                    loop_arg.stop()
                                except Exception:
                                    pass
                        new_rpc.update_event_loop = _tracked_update_loop

                    if getattr(new_rpc, "_aborted", False) or not self._running:
                        self._safe_close_target(new_rpc)
                        break

                    new_rpc.connect()

                    with self._lock:
                        self._connecting_rpc = None
                        if not self._running or getattr(new_rpc, "_aborted", False):
                            self._safe_close_target(new_rpc)
                            break
                        self._rpc = new_rpc

                    self._notify_state(RPCState.CONNECTED, "Activo en Discord")
                    self._send_rpc_update()
                except RECONNECT_EXCEPTIONS:
                    with self._lock:
                        if new_rpc is not None and self._connecting_rpc is new_rpc:
                            self._connecting_rpc = None
                    if new_rpc is not None:
                        self._safe_close_target(new_rpc)
                    self._safe_close_rpc()
                    if not self._running:
                        break
                    self._notify_state(RPCState.DISCONNECTED, "Esperando a Discord...")
                    try:
                        cmd, payload = self._cmd_queue.get(timeout=3.5)
                        self._process_command(cmd, payload)
                    except queue.Empty:
                        pass
                    if not self._running:
                        break
                    continue
                except (Exception, asyncio.CancelledError) as e:
                    with self._lock:
                        if new_rpc is not None and self._connecting_rpc is new_rpc:
                            self._connecting_rpc = None
                    if new_rpc is not None:
                        self._safe_close_target(new_rpc)
                    self._safe_close_rpc()
                    if not self._running:
                        break
                    self._notify_state(RPCState.DISCONNECTED, f"Error: {e}")
                    try:
                        cmd, payload = self._cmd_queue.get(timeout=3.5)
                        self._process_command(cmd, payload)
                    except queue.Empty:
                        pass
                    if not self._running:
                        break
                    continue

            # 2. Command Processing with Coalescing
            try:
                cmd, payload = self._cmd_queue.get(timeout=1.0)
                if cmd == "CONFIG_CHANGE":
                    while not self._cmd_queue.empty():
                        try:
                            next_cmd, next_payload = self._cmd_queue.get_nowait()
                            if next_cmd == "CONFIG_CHANGE":
                                payload.update(next_payload)
                            else:
                                self._process_command(cmd, payload)
                                cmd, payload = next_cmd, next_payload
                                break
                        except queue.Empty:
                            break
                self._process_command(cmd, payload)
            except queue.Empty:
                pass

            # 3. Match Auto-Reset Timer Handling
            with self._lock:
                autoreset = self.autoreset
                active = self.is_active
            if autoreset and active:
                if self.get_elapsed_seconds() >= self.match_duration_sec:
                    new_start = int(time.time())
                    with self._lock:
                        self.start_time = new_start
                        self.match_duration_sec = discord_rpc_manager.random.randint(1200, 1800)
                    self._notify_match_reset(new_start)
                    self._send_rpc_update()

        # Exit cleanup
        self._safe_close_rpc()


if __name__ == "__main__":
    print("=== Test 1: 100 iterations of rapid auto_start shutdown ===")
    failures = 0
    t0_all = time.time()
    for i in range(100):
        mgr = PatchedDiscordRPCManager(auto_start=True)
        if i % 3 == 0:
            time.sleep(0.01)
        elif i % 3 == 1:
            time.sleep(0.03)
        mgr.shutdown()
        if mgr._worker_thread.is_alive():
            failures += 1
            print(f"FAILED on iteration {i}")
            mgr._worker_thread.join(timeout=5.0)

    total_time = time.time() - t0_all
    print(f"Completed 100 runs in {total_time:.2f}s with {failures} failures.")
    if failures > 0:
        sys.exit(1)

    # Monkeypatch DiscordRPCManager in its module so test suites run against the fix
    discord_rpc_manager.DiscordRPCManager = PatchedDiscordRPCManager

    print("\n=== Test 2: 100 iterations of test_f11_b5_timer_cleanup_on_shutdown ===")
    from tests.test_tier2_boundaries import TestF11BoundaryTimer
    suite1 = unittest.TestSuite()
    for _ in range(100):
        suite1.addTest(TestF11BoundaryTimer("test_f11_b5_timer_cleanup_on_shutdown"))
    runner = unittest.TextTestRunner(verbosity=0)
    res1 = runner.run(suite1)
    print(f"TestF11BoundaryTimer ran 100 times: failures={len(res1.failures)}, errors={len(res1.errors)}")
    if len(res1.failures) > 0 or len(res1.errors) > 0:
        sys.exit(1)

    print("\n=== Test 3: 20 iterations of test_rpc_manager_shutdown_race (each has 10 sub-runs = 200 shutdowns) ===")
    from tests.test_challenger_m7_stress import TestErrorToastStress
    suite2 = unittest.TestSuite()
    for _ in range(20):
        suite2.addTest(TestErrorToastStress("test_rpc_manager_shutdown_race"))
    res2 = runner.run(suite2)
    print(f"TestErrorToastStress ran 20 times (200 shutdowns): failures={len(res2.failures)}, errors={len(res2.errors)}")
    if len(res2.failures) > 0 or len(res2.errors) > 0:
        sys.exit(1)

    print("\nALL 100+ TESTS PASSED DETERMINISTICALLY WITH ZERO FAILURES!")
    sys.exit(0)
