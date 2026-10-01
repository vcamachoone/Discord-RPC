#!/usr/bin/env python3
"""
app_gui.py - Native macOS AppKit Application Entry Point for Discord RPC

Coordinates:
  - LoLStatusItemController (Milestone 1): Menu bar status item with dynamic icons.
  - LoLPopoverController (Milestone 2): Native dark NSPopover interface.
  - DiscordRPCManager (Milestone 3): Thread-safe background Actor for pypresence.
  - NSApplicationActivationPolicyAccessory: Hidden dock icon, menubar agent application.
  - Bidirectional communication, thread-safe main runloop dispatch, and signal handling.
"""

import os
import sys
import signal
import subprocess
import logging
import fcntl
import socket
import threading
from typing import Optional, Any, Callable

import AppKit
import objc
from PyObjCTools import AppHelper

# Ensure local module directory is in sys.path
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

from status_item import LoLStatusItemController
from popover_ui import LoLPopoverController
from discord_rpc_manager import DiscordRPCManager, RPCState, DEFAULT_CLIENT_ID
from lol_champions import ChampionResolver
from lol_ranks import format_rank_display, get_rank_crest_url

_log_handlers = [logging.StreamHandler()]
for _lp in (
    os.path.expanduser("~/Library/Logs/com.victormanuel.lolrpc.log"),
    "/tmp/app_live.log",
):
    try:
        os.makedirs(os.path.dirname(_lp), exist_ok=True)
        _log_handlers.append(logging.FileHandler(_lp, mode="a", encoding="utf-8"))
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
    force=True,
)
logger = logging.getLogger("app_gui")

CLIENT_ID = DEFAULT_CLIENT_ID
LOL_LOGO_URL = (
    "https://cdn.discordapp.com/app-icons/1402418696126992445/"
    "7c99428541032ac02ec6981d88b78fb7.png?size=512"
)


def get_asset_path(filename: str) -> str:
    """Resolves asset paths checking local folder and bundle Resources."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, filename)
    if os.path.exists(path):
        return path
    assets_path = os.path.join(base_dir, "assets", filename)
    if os.path.exists(assets_path):
        return assets_path
    return path


class SingleInstanceController:
    """
    Guarantees that only a single instance of the application runs at any time.
    Uses non-blocking fcntl.flock on ~/.config/lol_discord_rpc/app.lock
    and a Unix domain socket at ~/.config/lol_discord_rpc/app.sock.
    If another instance is detected:
      - Connects to the domain socket and sends b"FOCUS\n".
      - Activates the running instance via AppKit.
      - Returns False so the caller can terminate cleanly (sys.exit(0)).
    If this is the primary instance:
      - Cleans up any stale socket file.
      - Binds and listens on the domain socket on a background daemon thread.
      - Calls the registered focus callback when b"FOCUS" is received.
      - Provides cleanup() to release lock and unlink socket.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if not config_dir:
            config_dir = os.path.expanduser("~/.config/lol_discord_rpc")
        self.config_dir = config_dir
        self.lock_path = os.path.join(self.config_dir, "app.lock")
        self.sock_path = os.path.join(self.config_dir, "app.sock")
        self._lock_file = None
        self._server_sock = None
        self._listen_thread = None
        self._running = False
        self._focus_callback: Optional[Callable[[], None]] = None

    def set_focus_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Registers the callback invoked when a secondary instance requests focus."""
        self._focus_callback = callback

    def check_and_acquire(self) -> bool:
        """
        Attempts to acquire the single-instance lock.
        Returns True if acquired (primary instance).
        Returns False if another instance is already running (notified to focus).
        """
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except OSError:
            pass

        # 1. Attempt non-blocking flock on lock file
        try:
            self._lock_file = open(self.lock_path, "a+")
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError, BlockingIOError):
            # Another instance holds the lock
            logger.info("Another instance is already running. Sending FOCUS signal...")
            if self._lock_file:
                try:
                    self._lock_file.close()
                except Exception:
                    pass
                self._lock_file = None
            self._notify_running_instance()
            return False

        # 2. We hold the lock -> Clean up any stale socket
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        # 3. Create Unix domain socket server
        try:
            self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_sock.bind(self.sock_path)
            self._server_sock.listen(5)
            self._running = True
            self._listen_thread = threading.Thread(
                target=self._socket_listener_loop,
                name="SingleInstanceSocketListener",
                daemon=True,
            )
            self._listen_thread.start()
            logger.info("SingleInstanceController listening on %s", self.sock_path)
        except Exception as e:
            logger.warning("Error creating single-instance socket server: %s", e)

        return True

    def _notify_running_instance(self) -> None:
        """Connects to the primary instance's socket and sends FOCUS."""
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1.0)
            client.connect(self.sock_path)
            client.sendall(b"FOCUS\n")
            try:
                client.recv(1024)
            except socket.timeout:
                pass
            client.close()
            logger.info("FOCUS signal successfully sent to primary instance socket.")
        except Exception as e:
            logger.warning("Failed to send FOCUS signal via socket: %s", e)

        # In addition to socket, activate the existing application bundle via LaunchServices
        try:
            apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
                "com.victormanuel.lolrpc"
            )
            if apps and len(apps) > 0:
                apps[0].activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
        except Exception:
            pass

    def _socket_listener_loop(self) -> None:
        """Background thread accepting connections on app.sock."""
        while self._running and self._server_sock:
            try:
                conn, _ = self._server_sock.accept()
                conn.settimeout(1.0)
                data = b""
                try:
                    data = conn.recv(1024)
                    conn.sendall(b"OK\n")
                except Exception:
                    pass
                finally:
                    conn.close()

                if b"FOCUS" in data:
                    logger.info("Received FOCUS command on single-instance socket.")
                    def _trigger_focus():
                        app = AppKit.NSApplication.sharedApplication()
                        if app:
                            app.activateIgnoringOtherApps_(True)
                        if self._focus_callback:
                            try:
                                self._focus_callback()
                            except Exception as ex:
                                logger.warning("Error invoking focus callback: %s", ex)
                        try:
                            subprocess.Popen([
                                "osascript", "-e",
                                'display notification "Haz clic en el icono de Discord en la barra superior (menú) para ver los controles." with title "Discord RPC" subtitle "Ya está en ejecución"'
                            ])
                        except Exception:
                            pass
                    app = AppKit.NSApplication.sharedApplication()
                    if app and app.isRunning():
                        AppHelper.callAfter(_trigger_focus)
                    else:
                        _trigger_focus()
            except OSError:
                break
            except Exception as e:
                if self._running:
                    logger.debug("Socket listener exception: %s", e)

    def cleanup(self) -> None:
        """Releases the lock and cleans up the Unix domain socket."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        if self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None


_single_instance: Optional[SingleInstanceController] = None


class LoLAppController(AppKit.NSObject):
    """
    Main application coordinator integrating LoLStatusItemController,
    LoLPopoverController, and DiscordRPCManager.
    """

    def __new__(cls, *args, **kwargs):
        instance = cls.alloc().init()
        instance._setup(*args, **kwargs)
        return instance

    def _setup(
        self,
        client_id: str = DEFAULT_CLIENT_ID,
        auto_start: bool = True,
        assets_dir: Optional[str] = None,
    ) -> None:
        self._is_shutting_down = False
        self.client_id = client_id

        # 1. Initialize Status Item Controller
        self.status_item = LoLStatusItemController(
            on_toggle=self.toggle_popover,
            on_toggle_presence=self.toggle_presence_from_menu,
            on_open_settings=self.open_settings_from_menu,
            on_quit=self.quit,
            assets_dir=assets_dir,
            auto_create=True,
        )

        # 2. Initialize Discord RPC Manager actor
        self.rpc_manager = DiscordRPCManager(
            client_id=client_id,
            on_state_change=self.on_rpc_state_change,
            on_match_reset=self.on_match_reset,
            auto_start=auto_start,
            load_config=True,
        )

        # 3. Initialize Popover UI Controller
        self.popover = LoLPopoverController(
            rpc_manager=self.rpc_manager,
            on_mode_change=self.on_mode_change,
            on_action_toggle=self.on_action_toggle,
            on_autorun_toggle=self.on_autorun_toggle,
            on_quit=self.quit,
        )

        # 4. Synchronize initial state to RPC manager
        self._sync_initial_state()

        # Set initial status item state
        self.status_item.set_state("normal")
        self.status_item.set_tooltip("Discord RPC - League of Legends")

        # 5. Register NSWorkspace Notifications (Discord launch & sleep/wake)
        self._register_workspace_notifications()

    def _register_workspace_notifications(self) -> None:
        """Registers NSWorkspace notifications for Discord launch and system wake."""
        try:
            nc = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
            nc.addObserver_selector_name_object_(
                self,
                b"onAppLaunched:",
                AppKit.NSWorkspaceDidLaunchApplicationNotification,
                None,
            )
            nc.addObserver_selector_name_object_(
                self,
                b"onSystemWake:",
                AppKit.NSWorkspaceDidWakeNotification,
                None,
            )
        except Exception as e:
            logger.warning("Error registering NSWorkspace notifications: %s", e)

    @objc.IBAction
    def onAppLaunched_(self, notification: Any) -> None:
        """Called when an application is launched in macOS to detect Discord."""
        if self._is_shutting_down:
            return
        user_info = notification.userInfo() if hasattr(notification, "userInfo") else None
        if not user_info:
            return
        app = user_info.get("NSWorkspaceApplicationKey")
        if not app:
            return
        bundle_id = (app.bundleIdentifier() or "").lower()
        name = (app.localizedName() or "").lower()
        if "discord" in bundle_id or "discord" in name:
            logger.info("Discord launch detected (%s: %s). Reconnecting RPC socket...", name, bundle_id)
            if self.rpc_manager:
                self.rpc_manager.reconnect()

    @objc.IBAction
    def onSystemWake_(self, notification: Any) -> None:
        """Called when macOS wakes from sleep."""
        if self._is_shutting_down:
            return
        logger.info("macOS wake from sleep detected. Reconnecting Discord IPC socket...")
        if self.rpc_manager:
            self.rpc_manager.reconnect()

    def focus_popover(self) -> None:
        """Brings the application and popover to the front."""
        logger.info("focus_popover triggered.")
        app = AppKit.NSApplication.sharedApplication()
        if app:
            app.activateIgnoringOtherApps_(True)
        if self.status_item and self.popover:
            btn = self.status_item.get_button()
            logger.info("focus_popover button: %s", btn)
            if btn:
                if self.popover.is_shown():
                    self.popover.close()
                self.popover.show(btn)

    def toggle_presence_from_menu(self) -> None:
        """Toggles Discord RPC presence state from menubar context menu."""
        if self.rpc_manager:
            new_state = not self.rpc_manager.is_active
            self.rpc_manager.set_active(new_state)

    def open_settings_from_menu(self) -> None:
        """Opens the popover directly in settings view from menubar context menu."""
        app = AppKit.NSApplication.sharedApplication()
        if app:
            app.activateIgnoringOtherApps_(True)
        if self.status_item and self.popover:
            btn = self.status_item.get_button()
            if btn:
                self.popover.open_settings_panel()
                self.popover.show(btn)

    def _sync_initial_state(self) -> None:
        """Pushes popover initial configuration to RPC manager."""
        try:
            mode = self.popover.get_current_mode()
            champ_name = self.popover.get_selected_champion()
            resolver = ChampionResolver() if ChampionResolver else None
            if resolver:
                cid, disp = resolver.resolve_champion(champ_name)
                champ_url = resolver.get_square_icon_url(cid)
            else:
                champ_url = ""

            rank_tier = self.popover.get_selected_rank()
            rank_div = self.popover.get_selected_division()
            rank_text = format_rank_display(rank_tier, rank_div)
            rank_url = get_rank_crest_url(rank_tier)
            game_mode = self.popover.get_game_mode_text()
            autoreset = self.popover.get_autoreset_state()

            self.rpc_manager.update_presence_config(
                mode=mode,
                champion_name=champ_name,
                champion_image_url=champ_url,
                rank_text=rank_text,
                rank_image_url=rank_url,
                game_mode=game_mode,
                autoreset=autoreset,
            )
        except Exception as e:
            logger.warning("Error syncing initial state: %s", e)

    def toggle_popover(self, sender: Any = None) -> None:
        """Toggles popover visibility anchored to the status bar button."""
        if self._is_shutting_down:
            return
        button = self.status_item.get_button() if self.status_item else sender
        target = button if button is not None else sender
        if self.popover:
            self.popover.toggle(target)

    def on_rpc_state_change(self, state: str, message: str) -> None:
        """Main-thread callback from DiscordRPCManager when connection state changes."""
        if self._is_shutting_down:
            return
        logger.info("RPC state change: %s (%s)", state, message)

        # Dynamic menubar icon updates
        if state == RPCState.CONNECTED:
            self.status_item.set_state("active")
        elif state == RPCState.PAUSED:
            self.status_item.set_state("paused")
        else:
            self.status_item.set_state("normal")

        # Update hover tooltip
        self.status_item.set_tooltip(f"Discord RPC: {message}")

        # Forward state to popover UI
        if self.popover:
            self.popover.set_connection_state(state)

        # Forward socket/RPC errors to in-app toast
        if self.popover and ("error" in state.lower() or "error" in message.lower() or "perdida" in message.lower() or "falló" in message.lower()):
            self.popover.show_toast(message, "error")

    def on_match_reset(self, new_start_time: int) -> None:
        """Main-thread callback from DiscordRPCManager when match auto-resets."""
        logger.info("Match auto-reset event received: start_time=%s", new_start_time)

    def on_mode_change(self, mode: str) -> None:
        """Callback when user switches between Official and Detailed mode."""
        logger.info("UI mode changed: %s", mode)

    def on_action_toggle(self, active: bool) -> None:
        """Callback when user toggles the primary presence button."""
        logger.info("Presence action toggled: active=%s", active)

    def on_autorun_toggle(self, enabled: bool) -> None:
        """Callback when user toggles macOS autorun switch."""
        logger.info("Autorun toggled: enabled=%s", enabled)

    def quit(self) -> None:
        """Clean shutdown of UI and background workers."""
        if self._is_shutting_down:
            return
        self._is_shutting_down = True
        logger.info("Initiating graceful shutdown...")

        try:
            nc = AppKit.NSWorkspace.sharedWorkspace().notificationCenter()
            nc.removeObserver_(self)
        except Exception:
            pass

        if self.popover:
            try:
                self.popover.close()
            except Exception:
                pass

        if self.status_item:
            try:
                self.status_item.cleanup()
            except Exception:
                pass

        if self.rpc_manager:
            try:
                self.rpc_manager.shutdown()
            except Exception:
                pass

        global _single_instance
        if _single_instance:
            try:
                _single_instance.cleanup()
            except Exception:
                pass

        app = AppKit.NSApplication.sharedApplication()
        if app and app.isRunning():
            app.terminate_(None)

        if "unittest" not in sys.modules and "pytest" not in sys.modules:
            import threading
            threading.Timer(0.15, lambda: os._exit(0)).start()


_GLOBAL_APP_DELEGATE: Any = None
_GLOBAL_APP_CONTROLLER: Any = None


class LoLAppDelegate(AppKit.NSObject):
    """Application delegate for NSApplication life cycle."""

    def init(self):
        self = objc.super(LoLAppDelegate, self).init()
        if self is not None:
            self.controller = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        global _GLOBAL_APP_CONTROLLER
        logger.info("League of Legends Discord RPC launched successfully.")
        self.controller = LoLAppController()
        _GLOBAL_APP_CONTROLLER = self.controller
        global _single_instance
        if _single_instance and self.controller:
            _single_instance.set_focus_callback(self.controller.focus_popover)

        # Auto-display popover on launch (suppressed when launched silently)
        is_silent = "--silent" in sys.argv or "--background" in sys.argv
        if not is_silent:
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.6, self, b"autoShowPopoverOnLaunch:", None, False
            )
        # Display system notification confirming active menubar presence even when launched with --silent
        subtitle = "Ejecutándose en la barra de menús" if is_silent else "Iniciado en la barra de menús"
        try:
            subprocess.Popen([
                "osascript", "-e",
                f'display notification "Haz clic en el icono de Discord en la barra superior para abrir el menú." with title "League of Legends RPC" subtitle "{subtitle}"'
            ])
        except Exception:
            pass

        if not is_silent:
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                1.2, self, b"autoShowPopoverOnLaunch:", None, False
            )

    @objc.IBAction
    def autoShowPopoverOnLaunch_(self, timer: Any) -> None:
        logger.info("autoShowPopoverOnLaunch_ timer fired. controller=%s", self.controller)
        if self.controller and self.controller.status_item and self.controller.popover:
            btn = self.controller.status_item.get_button()
            logger.info("autoShowPopoverOnLaunch_ button=%s", btn)
            if btn:
                app = AppKit.NSApplication.sharedApplication()
                if app:
                    app.activateIgnoringOtherApps_(True)
                self.controller.popover.show(btn)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, sender: Any, flag: bool) -> bool:
        """Called when the user clicks the app bundle in Finder/Applications or runs open -a while running."""
        if self.controller and self.controller.status_item and self.controller.popover:
            btn = self.controller.status_item.get_button()
            if btn:
                app = AppKit.NSApplication.sharedApplication()
                if app:
                    app.activateIgnoringOtherApps_(True)
                self.controller.popover.show(btn)
        return True

    def applicationWillTerminate_(self, notification):
        logger.info("League of Legends Discord RPC terminating.")
        if self.controller:
            self.controller.quit()
        global _single_instance
        if _single_instance:
            _single_instance.cleanup()


class SignalWakeupTarget(AppKit.NSObject):
    """Timer target to periodically yield runloop to Python signal processing."""

    @objc.IBAction
    def wakeup_(self, timer: Any) -> None:
        pass


def setup_main_menu(app: AppKit.NSApplication) -> None:
    """Creates a minimal application menu with Cmd+Q support."""
    main_menu = AppKit.NSMenu.alloc().init()
    app_menu_item = AppKit.NSMenuItem.alloc().init()
    main_menu.addItem_(app_menu_item)
    app_menu = AppKit.NSMenu.alloc().init()
    quit_item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
        "Quit League of Legends RPC",
        b"terminate:",
        "q",
    )
    app_menu.addItem_(quit_item)
    app_menu_item.setSubmenu_(app_menu)
    app.setMainMenu_(main_menu)


def setup_signal_handlers(delegate: LoLAppDelegate) -> None:
    """Installs POSIX signal handlers for SIGINT and SIGTERM."""

    def handle_signal(sig: int, frame: Any) -> None:
        logger.info("Received termination signal %d, stopping...", sig)
        if delegate and delegate.controller:
            delegate.controller.quit()
        else:
            app = AppKit.NSApplication.sharedApplication()
            if app:
                app.terminate_(None)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Periodic timer to wake runloop so Python signal handlers execute promptly
    target = SignalWakeupTarget.alloc().init()
    AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
        0.5, target, b"wakeup:", None, True
    )


def main() -> int:
    """Main application entry point."""
    global _single_instance
    _single_instance = SingleInstanceController()
    if not _single_instance.check_and_acquire():
        logger.info("Secondary instance exiting cleanly (0).")
        return 0

    app = AppKit.NSApplication.sharedApplication()
    # Configure activation policy: accessory (no dock icon, menu bar agent)
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    setup_main_menu(app)

    global _GLOBAL_APP_DELEGATE
    delegate = LoLAppDelegate.alloc().init()
    _GLOBAL_APP_DELEGATE = delegate
    app.setDelegate_(delegate)

    setup_signal_handlers(delegate)

    try:
        AppHelper.installMachInterrupt()
    except Exception:
        pass

    logger.info("Starting Cocoa event loop...")
    try:
        AppHelper.runEventLoop()
    finally:
        if _single_instance:
            _single_instance.cleanup()
    return 0


if __name__ == "__main__":
    sys.exit(main())
