"""
discord_rpc_manager.py - Thread-Safe Actor-Model Discord Rich Presence Manager

Runs a dedicated background worker thread managing pypresence and its asyncio event loop.
Maintains an internal command queue to ensure that all Cocoa / AppKit UI calls are non-blocking,
eliminates race conditions and socket corruption, dispatches status callbacks to Cocoa via
PyObjCTools.AppHelper.callAfter, and provides resilient auto-reconnect and match reset timers.
"""

import asyncio
import queue
import random
import threading
import time
from typing import Any, Callable, Dict, Optional

from pypresence import DiscordNotFound, InvalidPipe, Presence

DEFAULT_CLIENT_ID = "1402418696126992445"
LOL_LOGO_URL = (
    "https://cdn.discordapp.com/app-icons/1402418696126992445/"
    "7c99428541032ac02ec6981d88b78fb7.png?size=512"
)


class RPCState:
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PAUSED = "paused"


class DiscordRPCManager:
    """
    Thread-Safe Actor-Model Discord Rich Presence Controller.

    All public control methods (set_active, update_presence_config, restart_match, shutdown)
    are strictly non-blocking and thread-safe.
    """

    def __init__(
        self,
        client_id: str = DEFAULT_CLIENT_ID,
        on_state_change: Optional[Callable[[str, str], None]] = None,
        on_match_reset: Optional[Callable[[int], None]] = None,
        auto_start: bool = True,
    ):
        self.client_id: str = client_id
        self.on_state_change: Optional[Callable[[str, str], None]] = on_state_change
        self.on_match_reset: Optional[Callable[[int], None]] = on_match_reset

        self._cmd_queue: queue.Queue = queue.Queue()
        self._running: bool = True
        self._state: str = RPCState.DISCONNECTED
        self._rpc: Optional[Presence] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Presence configuration state
        self.is_active: bool = True
        self.mode: str = "oficial"  # "oficial" or "detallado"
        self.autoreset: bool = True
        self.start_time: int = int(time.time())
        self.match_duration_sec: int = random.randint(1200, 1800)  # 20 - 30 minutes

        # Detailed presence fields
        self.champion_name: str = "Malzahar"
        self.champion_image_url: str = ""
        self.rank_text: str = "Oro II"
        self.rank_image_url: str = ""
        self.game_mode: str = "Grieta del Invocador (Clasificatoria)"
        self.details: str = "En partida"

        # Worker thread
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="DiscordRPCWorker",
        )
        if auto_start:
            self._worker_thread.start()

    # -------------------------------------------------------------------------
    # Public Non-Blocking API
    # -------------------------------------------------------------------------

    def set_active(self, active: bool) -> None:
        """Enables or pauses presence publishing to Discord."""
        self.is_active = active
        self._cmd_queue.put(("SET_ACTIVE", active))

    def update_presence_config(self, **kwargs) -> None:
        """
        Thread-safe configuration update from Cocoa UI.
        Supported keys: mode, champion_name, champion_image_url, rank_text,
        rank_image_url, game_mode, details, autoreset.
        """
        self._cmd_queue.put(("CONFIG_CHANGE", kwargs))

    def restart_match(self) -> None:
        """Resets the match timer back to 00:00."""
        self._cmd_queue.put(("RESTART_MATCH", None))

    def shutdown(self) -> None:
        """Gracefully terminates the background worker and closes Discord IPC socket."""
        self._running = False
        self._cmd_queue.put(("SHUTDOWN", None))
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.5)

    @property
    def state(self) -> str:
        """Current presence connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Returns True if presence is connected and active."""
        return self._state == RPCState.CONNECTED and self._rpc is not None

    def get_elapsed_seconds(self) -> int:
        """Returns elapsed seconds in the current simulated match."""
        return max(0, int(time.time()) - self.start_time)

    # -------------------------------------------------------------------------
    # Thread-Safe Dispatch to Main Run Loop
    # -------------------------------------------------------------------------

    def _dispatch_to_main(self, callback: Optional[Callable], *args: Any) -> None:
        """
        Dispatches callback to the macOS Cocoa main thread via AppHelper.callAfter
        if NSApplication is running; otherwise calls directly (for CLI / tests).
        """
        if not callback:
            return

        try:
            from AppKit import NSApplication

            app = NSApplication.sharedApplication()
            if app and app.isRunning():
                from PyObjCTools import AppHelper

                AppHelper.callAfter(callback, *args)
                return
        except Exception:
            pass

        # Fallback for headless, CLI test runners, or non-GUI execution
        try:
            callback(*args)
        except Exception:
            pass

    def _notify_state(self, state: str, message: str) -> None:
        self._state = state
        self._dispatch_to_main(self.on_state_change, state, message)

    def _notify_match_reset(self, new_start_time: int) -> None:
        self._dispatch_to_main(self.on_match_reset, new_start_time)

    # -------------------------------------------------------------------------
    # Actor Worker Loop
    # -------------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main Actor loop running on dedicated background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while self._running:
            # 1. Connection & Reconnection Management
            if self.is_active and (self._rpc is None):
                self._notify_state(RPCState.CONNECTING, "Conectando a Discord...")
                try:
                    self._rpc = Presence(self.client_id, loop=self._loop)
                    self._rpc.connect()
                    self._notify_state(RPCState.CONNECTED, "Activo en Discord")
                    self._send_rpc_update()
                except (
                    DiscordNotFound,
                    FileNotFoundError,
                    ConnectionRefusedError,
                    ConnectionResetError,
                    BrokenPipeError,
                    InvalidPipe,
                    OSError,
                ):
                    self._rpc = None
                    self._notify_state(RPCState.DISCONNECTED, "Esperando a Discord...")
                    # Interleaved wait on command queue during reconnect backoff
                    try:
                        cmd, payload = self._cmd_queue.get(timeout=3.5)
                        self._process_command(cmd, payload)
                    except queue.Empty:
                        pass
                    continue
                except Exception as e:
                    self._rpc = None
                    self._notify_state(RPCState.DISCONNECTED, f"Error: {e}")
                    try:
                        cmd, payload = self._cmd_queue.get(timeout=3.5)
                        self._process_command(cmd, payload)
                    except queue.Empty:
                        pass
                    continue

            # 2. Command Processing with Coalescing
            try:
                cmd, payload = self._cmd_queue.get(timeout=1.0)
                # Coalesce rapid successive config changes
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
                if not self._running:
                    break
            except queue.Empty:
                pass

            # 3. Auto-Restart Match Timer Check
            if self.is_active and self._rpc and self.autoreset:
                elapsed = int(time.time()) - self.start_time
                if elapsed >= self.match_duration_sec:
                    self.start_time = int(time.time())
                    self.match_duration_sec = random.randint(1200, 1800)
                    self._send_rpc_update()
                    self._notify_match_reset(self.start_time)

        # 4. Teardown
        self._clear_presence()
        if self._rpc:
            try:
                self._rpc.close()
            except Exception:
                pass
            self._rpc = None

        if self._loop and not self._loop.is_closed():
            try:
                self._loop.close()
            except Exception:
                pass

    def _process_command(self, cmd: str, payload: Any) -> None:
        """Dispatches an internal command on the worker thread."""
        if cmd == "SHUTDOWN":
            self._running = False
        elif cmd == "SET_ACTIVE":
            active = bool(payload)
            self.is_active = active
            if not active:
                self._clear_presence()
                self._notify_state(RPCState.PAUSED, "Presencia pausada")
            else:
                self.start_time = int(time.time())
                if self._rpc:
                    self._send_rpc_update()
                    self._notify_state(RPCState.CONNECTED, "Activo en Discord")
                else:
                    self._notify_state(RPCState.CONNECTING, "Conectando a Discord...")
        elif cmd == "CONFIG_CHANGE":
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
            if self.is_active and self._rpc:
                self._send_rpc_update()
        elif cmd == "RESTART_MATCH":
            self.start_time = int(time.time())
            self.match_duration_sec = random.randint(1200, 1800)
            if self.is_active and self._rpc:
                self._send_rpc_update()
            self._notify_match_reset(self.start_time)

    def _send_rpc_update(self) -> None:
        """Sends the presence payload over the Discord IPC socket."""
        if not self._rpc or not self.is_active:
            return

        try:
            if self.mode == "oficial":
                self._rpc.update(
                    start=self.start_time,
                    large_image=LOL_LOGO_URL,
                    large_text="League of Legends",
                )
            else:
                kwargs: Dict[str, Any] = {
                    "details": self.details or "En partida",
                    "state": self.game_mode or "Grieta del Invocador",
                    "start": self.start_time,
                }
                if self.champion_image_url:
                    kwargs["large_image"] = self.champion_image_url
                    kwargs["large_text"] = self.champion_name or "Campeón"
                elif self.champion_name:
                    kwargs["large_text"] = self.champion_name
                    kwargs["large_image"] = LOL_LOGO_URL

                if self.rank_image_url:
                    kwargs["small_image"] = self.rank_image_url
                    kwargs["small_text"] = self.rank_text or "Rango"
                elif self.rank_text:
                    kwargs["small_text"] = self.rank_text

                self._rpc.update(**kwargs)
        except (BrokenPipeError, InvalidPipe, ConnectionResetError, OSError, Exception) as e:
            # Discord closed, crashed, or pipe severed
            if self._rpc:
                try:
                    self._rpc.close()
                except Exception:
                    pass
            self._rpc = None
            self._notify_state(RPCState.DISCONNECTED, "Conexión perdida con Discord")

    def _clear_presence(self) -> None:
        """Clears active presence payload without disconnecting socket."""
        if self._rpc:
            try:
                self._rpc.clear()
            except Exception:
                pass
