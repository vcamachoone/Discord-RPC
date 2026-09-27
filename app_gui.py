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
from typing import Optional, Any

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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
    fallback = os.path.join("/Users/victormanuel/discord-rpc", filename)
    if os.path.exists(fallback):
        return fallback
    return path


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
            assets_dir=assets_dir,
            auto_create=True,
        )

        # 2. Initialize Discord RPC Manager actor
        self.rpc_manager = DiscordRPCManager(
            client_id=client_id,
            on_state_change=self.on_rpc_state_change,
            on_match_reset=self.on_match_reset,
            auto_start=auto_start,
        )

        # 3. Initialize Popover UI Controller
        self.popover = LoLPopoverController(
            rpc_manager=self.rpc_manager,
            on_mode_change=self.on_mode_change,
            on_action_toggle=self.on_action_toggle,
            on_autorun_toggle=self.on_autorun_toggle,
        )

        # 4. Synchronize initial state to RPC manager
        self._sync_initial_state()

        # Set initial status item state
        self.status_item.set_state("normal")
        self.status_item.set_tooltip("Discord RPC - League of Legends")

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

        app = AppKit.NSApplication.sharedApplication()
        if app and app.isRunning():
            app.terminate_(None)


class LoLAppDelegate(AppKit.NSObject):
    """Application delegate for NSApplication life cycle."""

    def init(self):
        self = objc.super(LoLAppDelegate, self).init()
        if self is not None:
            self.controller = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        logger.info("League of Legends Discord RPC launched successfully.")
        self.controller = LoLAppController()
        # Auto-display popover and notification on launch (suppressed when launched silently)
        is_silent = "--silent" in sys.argv or "--background" in sys.argv
        if not is_silent:
            AppKit.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.6, self, b"autoShowPopoverOnLaunch:", None, False
            )
            try:
                subprocess.Popen([
                    "osascript", "-e",
                    'display notification "Haz clic en el icono de Discord en la barra superior para abrir el menú." with title "League of Legends RPC" subtitle "Iniciado en la barra de menús"'
                ])
            except Exception:
                pass

    @objc.IBAction
    def autoShowPopoverOnLaunch_(self, timer: Any) -> None:
        if self.controller and self.controller.status_item and self.controller.popover:
            btn = self.controller.status_item.get_button()
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
                self.controller.popover.toggle(btn)
        return True

    def applicationWillTerminate_(self, notification):
        logger.info("League of Legends Discord RPC terminating.")
        if self.controller:
            self.controller.quit()


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
    app = AppKit.NSApplication.sharedApplication()
    # Configure activation policy: accessory (no dock icon, menu bar agent)
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    setup_main_menu(app)

    delegate = LoLAppDelegate.alloc().init()
    app.setDelegate_(delegate)

    setup_signal_handlers(delegate)

    try:
        AppHelper.installMachInterrupt()
    except Exception:
        pass

    logger.info("Starting Cocoa event loop...")
    AppHelper.runEventLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
