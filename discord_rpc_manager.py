"""
discord_rpc_manager.py - Thread-Safe Actor-Model Discord Rich Presence Manager

Runs a dedicated background worker thread managing pypresence and its asyncio event loop.
Maintains an internal command queue to ensure that all Cocoa / AppKit UI calls are non-blocking,
eliminates race conditions and socket corruption, dispatches status callbacks to Cocoa via
PyObjCTools.AppHelper.callAfter, and provides resilient auto-reconnect and match reset timers.
"""

import os
import json
import asyncio
import queue
import random
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pypresence import (
    Presence,
    DiscordNotFound,
    InvalidPipe,
    PipeClosed,
    ConnectionTimeout,
    ResponseTimeout,
    PyPresenceException,
)

DEFAULT_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1402418696126992445")
LOL_LOGO_URL = (
    "https://cdn.discordapp.com/app-icons/1402418696126992445/"
    "7c99428541032ac02ec6981d88b78fb7.png?size=512"
)

# Persistent configuration path
CONFIG_DIR = os.path.expanduser("~/.config/lol_discord_rpc")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

# Catalog of Top 10 Most Played Games presets with official Discord Application Client IDs
TOP_GAMES: Dict[str, Dict[str, Any]] = {
    "lol": {
        "id": "lol",
        "name": "League of Legends",
        "client_id": "1402418696126992445",
        "icon": "https://cdn.discordapp.com/app-icons/1402418696126992445/7c99428541032ac02ec6981d88b78fb7.png?size=512",
        "default_details": "En partida",
        "default_state": "Grieta del Invocador",
        "duration_min": 25,
    },
    "valorant": {
        "id": "valorant",
        "name": "VALORANT",
        "client_id": "700142994017648710",
        "icon": "https://cdn.discordapp.com/app-icons/700142994017648710/f135b91b93f218ff4732049c6ee68aa7.png?size=512",
        "default_details": "Competitivo",
        "default_state": "En partida (Ascent)",
        "duration_min": 35,
    },
    "cs2": {
        "id": "cs2",
        "name": "Counter-Strike 2",
        "client_id": "1157771746215391302",
        "icon": "https://cdn.discordapp.com/app-icons/1157771746215391302/c71302eeecae571b697858cceac29323.png?size=512",
        "default_details": "Premier Competitivo",
        "default_state": "Mirage - 11:9",
        "duration_min": 30,
    },
    "minecraft": {
        "id": "minecraft",
        "name": "Minecraft",
        "client_id": "698942205566877706",
        "icon": "https://cdn.discordapp.com/app-icons/698942205566877706/b822d64a85fa6f1571dc3184ecde8c27.png?size=512",
        "default_details": "Modo Supervivencia",
        "default_state": "Mundo Hardcore",
        "duration_min": 45,
    },
    "fortnite": {
        "id": "fortnite",
        "name": "Fortnite",
        "client_id": "432980957394370572",
        "icon": "https://cdn.discordapp.com/app-icons/432980957394370572/612a4c1606bcf6b509ef2bc2c0022204.png?size=512",
        "default_details": "Battle Royale",
        "default_state": "Escuadrones - Quedan 12",
        "duration_min": 20,
    },
    "gtav": {
        "id": "gtav",
        "name": "Grand Theft Auto V",
        "client_id": "650800318536646696",
        "icon": "https://cdn.discordapp.com/app-icons/650800318536646696/63a152d19f560e2270bb3f2f819a5fa1.png?size=512",
        "default_details": "GTA Online / FiveM",
        "default_state": "Los Santos en sesión libre",
        "duration_min": 60,
    },
    "apex": {
        "id": "apex",
        "name": "Apex Legends",
        "client_id": "543884846435401729",
        "icon": "https://cdn.discordapp.com/app-icons/543884846435401729/7a3d077c5cbde6c1e303d29759ad2c17.png?size=512",
        "default_details": "Tríos Clasificatorios",
        "default_state": "Fin del Mundo - Ronda 3",
        "duration_min": 22,
    },
    "overwatch2": {
        "id": "overwatch2",
        "name": "Overwatch 2",
        "client_id": "446342898783453185",
        "icon": "https://cdn.discordapp.com/app-icons/446342898783453185/87e8346cb4bfbb3660aa8838d726b2b5.png?size=512",
        "default_details": "Competitivo",
        "default_state": "King's Row - Carga útil",
        "duration_min": 18,
    },
    "dota2": {
        "id": "dota2",
        "name": "Dota 2",
        "client_id": "378854498308620288",
        "icon": "https://cdn.discordapp.com/app-icons/378854498308620288/1da8a13ba0cbb577a76059ad8330ee0f.png?size=512",
        "default_details": "All Pick Clasificatoria",
        "default_state": "Fase Media",
        "duration_min": 40,
    },
    "rocketleague": {
        "id": "rocketleague",
        "name": "Rocket League",
        "client_id": "379286088717369344",
        "icon": "https://cdn.discordapp.com/app-icons/379286088717369344/b3fcbf70a09e0fafe5fcfebcae4663a8.png?size=512",
        "default_details": "Competitivo 3v3",
        "default_state": "Estadio DFH",
        "duration_min": 10,
    },
    "custom": {
        "id": "custom",
        "name": "Personalizado (Custom)",
        "client_id": "",
        "icon": "",
        "default_details": "Jugando",
        "default_state": "En partida",
        "duration_min": 30,
    },
}


def load_user_config() -> Dict[str, Any]:
    """Loads persistent user configuration from ~/.config/lol_discord_rpc/config.json."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception:
        pass
    return {}


def save_user_config(cfg: Dict[str, Any]) -> None:
    """Saves user configuration to ~/.config/lol_discord_rpc/config.json."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# Whitelist of configurable presence attributes to prevent attribute injection
ALLOWED_CONFIG_KEYS = {
    "mode",
    "champion_name",
    "champion_image_url",
    "rank_text",
    "rank_image_url",
    "game_mode",
    "details",
    "autoreset",
    "buttons",
}


def sanitize_buttons(raw_buttons: Any) -> Optional[List[Dict[str, str]]]:
    """
    Sanitizes and validates Discord Rich Presence interactive profile buttons.

    Rules enforced:
      - raw_buttons must be a list or tuple.
      - Maximum of 2 buttons.
      - Each button must be a dict with non-empty 'label' (<= 32 chars) and 'url' (<= 512 chars).
      - Enforce HTTPS: prefix 'https://' if missing, upgrade 'http://' to 'https://'.
      - Incomplete buttons (missing/empty label or URL) are dropped cleanly.
      - Returns None if no valid buttons exist, preventing Discord schema rejection on empty arrays.
    """
    if not isinstance(raw_buttons, (list, tuple)):
        return None

    valid: List[Dict[str, str]] = []
    for item in raw_buttons:
        if not isinstance(item, dict):
            continue

        raw_label = item.get("label")
        raw_url = item.get("url")

        if raw_label is None or raw_url is None:
            continue

        label = str(raw_label).strip()
        url = str(raw_url).strip()

        if not label or not url:
            continue

        # Enforce HTTPS
        if url.startswith("http://"):
            url = "https://" + url[7:]
        elif not url.startswith("https://"):
            url = "https://" + url

        # Truncate label to 32 and url to 512
        label = label[:32]
        url = url[:512]

        valid.append({"label": label, "url": url})
        if len(valid) == 2:
            break

    return valid if valid else None

# Exceptions caught during connection and reconnection to prevent leaking generic errors
RECONNECT_EXCEPTIONS = (
    DiscordNotFound,
    InvalidPipe,
    PipeClosed,
    ConnectionTimeout,
    ResponseTimeout,
    PyPresenceException,
    FileNotFoundError,
    ConnectionRefusedError,
    ConnectionResetError,
    BrokenPipeError,
    OSError,
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
        load_config: bool = False,
    ):
        saved = load_user_config() if load_config else {}
        if client_id == DEFAULT_CLIENT_ID and saved.get("client_id"):
            self.client_id: str = str(saved["client_id"]).strip()
        else:
            self.client_id = client_id

        self.selected_game_id: str = saved.get("game_id", "lol")
        self.custom_game_name: str = saved.get("game_name", "")
        self.custom_game_icon: str = saved.get("game_icon", "")
        self.on_state_change: Optional[Callable[[str, str], None]] = on_state_change
        self.on_match_reset: Optional[Callable[[int], None]] = on_match_reset

        self._cmd_queue: queue.Queue = queue.Queue()
        self._running: bool = True
        self._state: str = RPCState.DISCONNECTED
        self._rpc: Optional[Presence] = None
        self._connecting_rpc: Optional[Presence] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock: threading.RLock = threading.RLock()

        # Presence configuration state
        self.is_active: bool = True
        self.mode: str = saved.get("mode", "oficial")  # "oficial" or "detallado"
        self.autoreset: bool = saved.get("autoreset", True)
        self.start_time: int = int(time.time())
        duration_saved = saved.get("match_duration_sec")
        self.match_duration_sec: int = int(duration_saved) if duration_saved else random.randint(1200, 1800)

        # Detailed presence fields
        self.champion_name: str = saved.get("champion", "Malzahar")
        self.champion_image_url: str = ""
        self.rank_text: str = saved.get("rank_text", "Oro II")
        self.rank_image_url: str = ""
        self.game_mode: str = saved.get("game_mode", "Grieta del Invocador (Clasificatoria)")
        self.details: str = saved.get("details", "En partida")
        self.buttons: List[Dict[str, str]] = saved.get("buttons", [])

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
        with self._lock:
            self.is_active = active
        self._cmd_queue.put(("SET_ACTIVE", active))

    def set_client_id(self, new_id: str) -> None:
        """Dynamically updates Discord Client ID and triggers reconnect."""
        self._cmd_queue.put(("SET_CLIENT_ID", new_id))

    def set_game_preset(
        self,
        game_id: str,
        client_id: str = "",
        game_name: str = "",
        game_icon: str = "",
        details: str = "",
        state: str = "",
        duration_sec: Optional[int] = None,
    ) -> None:
        """Updates game preset, details, and presence assets."""
        self._cmd_queue.put(
            (
                "SET_GAME",
                {
                    "game_id": game_id,
                    "client_id": client_id,
                    "game_name": game_name,
                    "game_icon": game_icon,
                    "details": details,
                    "state": state,
                    "duration_sec": duration_sec,
                },
            )
        )

    def set_match_duration(self, seconds: int) -> None:
        """Sets match duration in seconds for auto-reset timer."""
        self._cmd_queue.put(("SET_DURATION", seconds))

    def update_presence_config(self, **kwargs) -> None:
        """
        Thread-safe configuration update from Cocoa UI.
        Supported keys: mode, champion_name, champion_image_url, rank_text,
        rank_image_url, game_mode, details, autoreset, buttons.
        """
        self._cmd_queue.put(("CONFIG_CHANGE", kwargs))

    def restart_match(self) -> None:
        """Resets the match timer back to 00:00."""
        self._cmd_queue.put(("RESTART_MATCH", None))

    def reconnect(self) -> None:
        """Forces an immediate reconnection attempt, interrupting backoff sleep."""
        self._cmd_queue.put(("RECONNECT", None))

    def shutdown(self) -> None:
        """Gracefully terminates the background worker and closes Discord IPC socket."""
        self._running = False
        self._safe_close_rpc()
        self._cmd_queue.put(("SHUTDOWN", None))
        if self._worker_thread.is_alive() and threading.current_thread() != self._worker_thread:
            self._worker_thread.join(timeout=4.0)

    @property
    def state(self) -> str:
        """Current presence connection state."""
        with self._lock:
            return self._state

    @property
    def is_connected(self) -> bool:
        """Returns True if presence is connected and active."""
        with self._lock:
            return self._state == RPCState.CONNECTED and self._rpc is not None

    def get_elapsed_seconds(self) -> int:
        """Returns elapsed seconds in the current simulated match."""
        with self._lock:
            st = self.start_time
        return max(0, int(time.time()) - st)

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
        with self._lock:
            self._state = state
        self._dispatch_to_main(self.on_state_change, state, message)

    def _notify_match_reset(self, new_start_time: int) -> None:
        self._dispatch_to_main(self.on_match_reset, new_start_time)

    def _safe_close_target(self, target: Any) -> None:
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

    # -------------------------------------------------------------------------
    # Actor Worker Loop
    # -------------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main Actor loop running on dedicated background thread."""
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
                    new_rpc = Presence(self.client_id, loop=self._loop)
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
                    # Interleaved wait on command queue during reconnect backoff
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
                # Coalesce rapid successive config changes
                if cmd == "CONFIG_CHANGE":
                    while not self._cmd_queue.empty():
                        try:
                            next_cmd, next_payload = self._cmd_queue.get_nowait()
                            if next_cmd == "CONFIG_CHANGE":
                                if isinstance(payload, dict) and isinstance(next_payload, dict):
                                    payload.update(next_payload)
                                elif isinstance(next_payload, dict):
                                    payload = dict(next_payload)
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
            with self._lock:
                active = self.is_active
                rpc = self._rpc
                st = self.start_time
            if active and rpc and self.autoreset:
                elapsed = int(time.time()) - st
                if elapsed >= self.match_duration_sec:
                    now = int(time.time())
                    with self._lock:
                        self.start_time = now
                    self.match_duration_sec = random.randint(1200, 1800)
                    self._send_rpc_update()
                    self._notify_match_reset(now)

        # 4. Teardown
        self._clear_presence()
        self._safe_close_rpc()

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
            with self._lock:
                self.is_active = active
            if not active:
                self._clear_presence()
                self._notify_state(RPCState.PAUSED, "Presencia pausada")
            else:
                now = int(time.time())
                with self._lock:
                    self.start_time = now
                    rpc = self._rpc
                if rpc:
                    self._send_rpc_update()
                    self._notify_state(RPCState.CONNECTED, "Activo en Discord")
                else:
                    self._notify_state(RPCState.CONNECTING, "Conectando a Discord...")
        elif cmd == "SET_CLIENT_ID":
            new_id = str(payload or "").strip() or DEFAULT_CLIENT_ID
            with self._lock:
                changed = (self.client_id != new_id)
                if changed:
                    self.client_id = new_id
            if changed:
                self._safe_close_rpc()
                self._notify_state(RPCState.CONNECTING, "Reconectando con nuevo Client ID...")
        elif cmd == "SET_GAME":
            if isinstance(payload, dict):
                g_id = payload.get("game_id") or "lol"
                c_id = (payload.get("client_id") or "").strip()
                g_name = payload.get("game_name", "")
                g_icon = payload.get("game_icon", "")
                det = payload.get("details")
                st = payload.get("state")
                dur = payload.get("duration_sec")

                with self._lock:
                    self.selected_game_id = g_id
                    if g_name:
                        self.custom_game_name = g_name
                    if g_icon:
                        self.custom_game_icon = g_icon
                    if det is not None:
                        self.details = det
                    if st is not None:
                        self.game_mode = st
                    if dur:
                        self.match_duration_sec = int(dur)

                target_client_id = c_id
                if not target_client_id:
                    target_client_id = TOP_GAMES.get(g_id, {}).get("client_id", DEFAULT_CLIENT_ID) or DEFAULT_CLIENT_ID

                with self._lock:
                    changed_id = (self.client_id != target_client_id)
                    if changed_id:
                        self.client_id = target_client_id

                if changed_id:
                    self._safe_close_rpc()
                    self._notify_state(RPCState.CONNECTING, "Reconectando con nuevo juego...")
                else:
                    with self._lock:
                        active = self.is_active
                        rpc = self._rpc
                    if active and rpc:
                        self._send_rpc_update()
        elif cmd == "SET_DURATION":
            try:
                sec = int(payload)
                with self._lock:
                    self.match_duration_sec = sec
            except Exception:
                pass
        elif cmd == "CONFIG_CHANGE":
            if isinstance(payload, dict):
                for k, v in payload.items():
                    if k in ALLOWED_CONFIG_KEYS and hasattr(self, k):
                        with self._lock:
                            setattr(self, k, v)
            with self._lock:
                active = self.is_active
                rpc = self._rpc
            if active and rpc:
                self._send_rpc_update()
        elif cmd == "RESTART_MATCH":
            now = int(time.time())
            with self._lock:
                self.start_time = now
                active = self.is_active
                rpc = self._rpc
            self.match_duration_sec = random.randint(1200, 1800)
            if active and rpc:
                self._send_rpc_update()
            self._notify_match_reset(now)
        elif cmd == "RECONNECT":
            self._safe_close_rpc()
            with self._lock:
                active = self.is_active
            if active:
                self._notify_state(RPCState.CONNECTING, "Reconectando a Discord...")

    def _send_rpc_update(self) -> None:
        """Sends the presence payload over the Discord IPC socket."""
        with self._lock:
            rpc = self._rpc
            active = self.is_active
            mode = self.mode
            start_time = self.start_time
            details = self.details
            game_mode = self.game_mode
            champ_img = self.champion_image_url
            champ_name = self.champion_name
            rank_img = self.rank_image_url
            rank_text = self.rank_text
            game_id = getattr(self, "selected_game_id", "lol")
            custom_name = getattr(self, "custom_game_name", "")
            custom_icon = getattr(self, "custom_game_icon", "")
            buttons = getattr(self, "buttons", [])

        if not rpc or not active:
            return

        valid_buttons = sanitize_buttons(buttons)

        try:
            if game_id == "lol":
                if mode == "oficial":
                    kwargs: Dict[str, Any] = {
                        "start": start_time,
                        "large_image": LOL_LOGO_URL,
                        "large_text": "League of Legends",
                    }
                    if valid_buttons is not None:
                        kwargs["buttons"] = valid_buttons
                    rpc.update(**kwargs)
                else:
                    kwargs: Dict[str, Any] = {
                        "details": details or "En partida",
                        "state": game_mode or "Grieta del Invocador",
                        "start": start_time,
                    }
                    if champ_img:
                        kwargs["large_image"] = champ_img
                        kwargs["large_text"] = champ_name or "Campeón"
                    elif champ_name:
                        kwargs["large_text"] = champ_name
                        kwargs["large_image"] = LOL_LOGO_URL

                    if rank_img:
                        kwargs["small_image"] = rank_img
                        kwargs["small_text"] = rank_text or "Rango"
                    elif rank_text:
                        kwargs["small_text"] = rank_text

                    if valid_buttons is not None:
                        kwargs["buttons"] = valid_buttons

                    rpc.update(**kwargs)
            else:
                game_info = TOP_GAMES.get(game_id, TOP_GAMES.get("custom", {}))
                g_name = custom_name or game_info.get("name", "Juego")
                g_icon = custom_icon or game_info.get("icon", "") or LOL_LOGO_URL
                kwargs = {
                    "details": details or game_info.get("default_details", "En partida"),
                    "state": game_mode or game_info.get("default_state", "Jugando"),
                    "start": start_time,
                }
                if g_icon:
                    kwargs["large_image"] = g_icon
                    kwargs["large_text"] = g_name
                if valid_buttons is not None:
                    kwargs["buttons"] = valid_buttons
                rpc.update(**kwargs)
        except (BrokenPipeError, InvalidPipe, PipeClosed, ConnectionResetError, OSError, Exception) as e:
            # Discord closed, crashed, or pipe severed
            self._safe_close_rpc()
            self._notify_state(RPCState.DISCONNECTED, "Conexión perdida con Discord")

    def _clear_presence(self) -> None:
        """Clears active presence payload without disconnecting socket."""
        with self._lock:
            rpc = self._rpc
        if rpc:
            try:
                rpc.clear()
            except Exception:
                pass
