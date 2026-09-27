#!/usr/bin/env python3
"""
status_item.py - Cocoa NSStatusItem Controller for Discord RPC

Implements LoLStatusItemController, an AppKit/PyObjC controller managing:
  - System status bar item creation with NSSquareStatusItemLength
  - Dynamic status bar icons (normal, active, paused) loaded from assets_gen
  - Dynamic template / non-template mode management:
      - 'normal': setTemplate_(True) (adapts to light/dark menubar)
      - 'active': setTemplate_(False) (preserves #00A8FC vibrant blue dot)
      - 'paused': setTemplate_(False) (preserves 35% alpha dimmed appearance)
  - Target-action dispatch to popover toggle callback
  - Accessors get_button(), get_status_item(), get_state(), get_current_state()
  - Click handling via handle_click(sender) and statusItemButtonClicked_(sender)
  - Safe lifecycle cleanup removing status item from NSStatusBar
"""

import os
import sys
from typing import Callable, Dict, Optional

import AppKit
import objc
from Foundation import NSObject

try:
    import assets_gen
except ImportError:
    # Allow importing if running from a different working directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import assets_gen


class LoLStatusItemController(NSObject):
    """
    Cocoa status bar controller managing an NSStatusItem for League of Legends Discord RPC.
    """

    def __new__(cls, *args, **kwargs):
        # Support both standard Python instantiation LoLStatusItemController(...)
        # and Objective-C style LoLStatusItemController.alloc().init()
        instance = cls.alloc().init()
        instance._setup(*args, **kwargs)
        return instance

    def _setup(
        self,
        on_toggle: Optional[Callable] = None,
        assets_dir: Optional[str] = None,
        auto_create: bool = True,
        **kwargs,
    ) -> None:
        """
        Internal initializer called by __new__.
        Supports kwargs: on_toggle, on_toggle_popover, callback, assets_dir, auto_create.
        """
        # Resolve callback from possible keyword arguments
        cb = on_toggle
        if cb is None:
            cb = kwargs.get("on_toggle_popover")
        if cb is None:
            cb = kwargs.get("callback")

        # Resolve assets_dir
        if assets_dir is None:
            assets_dir = kwargs.get("assets_dir")

        self._on_toggle: Optional[Callable] = cb
        self._assets_dir: Optional[str] = assets_dir
        self._current_state: str = "normal"
        self._status_bar: Optional[AppKit.NSStatusBar] = None
        self._status_item: Optional[AppKit.NSStatusItem] = None
        self._button: Optional[AppKit.NSStatusBarButton] = None
        self._icons: Dict[str, AppKit.NSImage] = {}
        self._icon_paths: Dict[str, str] = {}
        self._cleaned_up: bool = False

        if auto_create:
            self._init_status_item()
            self._load_icons()
            self.set_state("normal")

    def _init_status_item(self) -> None:
        """
        Creates and configures the Cocoa NSStatusItem on the system status bar.
        """
        self._status_bar = AppKit.NSStatusBar.systemStatusBar()
        self._status_item = self._status_bar.statusItemWithLength_(
            AppKit.NSSquareStatusItemLength
        )
        self._button = self._status_item.button()

        if self._button is not None:
            self._button.setTarget_(self)
            self._button.setAction_(b"statusItemButtonClicked:")
            self._button.setToolTip_("Discord RPC - League of Legends")

    def _load_icons(self) -> None:
        """
        Generates or resolves status bar icon files and constructs multi-resolution NSImage instances.
        """
        # Ensure icons are generated and retrieve paths
        self._icon_paths = assets_gen.generate_status_icons(self._assets_dir)

        for state in ("normal", "active", "paused"):
            path_1x = self._icon_paths.get(state) or self._icon_paths.get(f"{state}_1x")
            path_2x = self._icon_paths.get(f"{state}@2x") or self._icon_paths.get(f"{state}_2x")

            # Create multi-representation NSImage with logical size 22x22 pt
            img = AppKit.NSImage.alloc().initWithSize_(AppKit.NSMakeSize(22, 22))

            if path_1x and os.path.exists(path_1x):
                rep_1x = AppKit.NSBitmapImageRep.imageRepWithContentsOfFile_(path_1x)
                if rep_1x is not None:
                    rep_1x.setSize_(AppKit.NSMakeSize(22, 22))
                    img.addRepresentation_(rep_1x)

            if path_2x and os.path.exists(path_2x):
                rep_2x = AppKit.NSBitmapImageRep.imageRepWithContentsOfFile_(path_2x)
                if rep_2x is not None:
                    rep_2x.setSize_(AppKit.NSMakeSize(22, 22))
                    img.addRepresentation_(rep_2x)

            # Fallback if representations couldn't be loaded
            if len(img.representations()) == 0 and path_1x and os.path.exists(path_1x):
                img = AppKit.NSImage.alloc().initWithContentsOfFile_(path_1x)
                if img:
                    img.setSize_(AppKit.NSMakeSize(22, 22))

            self._icons[state] = img

    @objc.IBAction
    def statusItemButtonClicked_(self, sender) -> None:
        """
        Cocoa action triggered when the user clicks the status item button.
        Invokes the registered Python popover toggle callback.
        """
        if callable(self._on_toggle):
            target_sender = sender if sender is not None else self._button
            try:
                self._on_toggle(target_sender)
            except TypeError:
                self._on_toggle()

    def handle_click(self, sender=None) -> None:
        """
        Programmatic click handler mimicking user click event.
        """
        self.statusItemButtonClicked_(sender if sender is not None else self._button)

    def set_state(self, state: Optional[str]) -> None:
        """
        Updates the status item icon according to the connection state:
          - 'normal': Monochrome white template mode (adapts to system theme).
          - 'active': Full color mode showing white Clyde + #00A8FC blue dot.
          - 'paused': Dimmed 35% alpha mode.

        Gracefully defaults unrecognized or empty states to 'normal' without throwing.
        """
        if not state:
            state_norm = "normal"
        else:
            state_norm = str(state).lower().strip()
            if state_norm not in ("normal", "active", "paused"):
                # Graceful fallback to normal for unrecognized strings
                state_norm = "normal"

        self._current_state = state_norm
        image = self._icons.get(state_norm)

        if image is not None:
            # Set template flag according to specification
            if state_norm == "normal":
                image.setTemplate_(True)
            else:
                image.setTemplate_(False)

            if self._button is not None:
                self._button.setImage_(image)

    def get_current_state(self) -> str:
        """Returns the current state ('normal', 'active', or 'paused')."""
        return self._current_state

    def get_state(self) -> str:
        """Returns the current state ('normal', 'active', or 'paused')."""
        return self._current_state

    @property
    def state(self) -> str:
        """Property returning the current state."""
        return self._current_state

    def get_button(self) -> Optional[AppKit.NSStatusBarButton]:
        """
        Returns the NSStatusBarButton instance, used to anchor NSPopover.
        """
        return self._button

    def get_status_item(self) -> Optional[AppKit.NSStatusItem]:
        """
        Returns the underlying NSStatusItem instance.
        """
        return self._status_item

    def set_callback(self, on_toggle: Optional[Callable]) -> None:
        """
        Registers or updates the click callback function.
        """
        self._on_toggle = on_toggle

    def set_tooltip(self, text: str) -> None:
        """
        Sets the hover tooltip for the status bar item.
        """
        if self._button is not None:
            self._button.setToolTip_(text)

    def cleanup(self) -> None:
        """
        Removes the status item from the system status bar and releases resources.
        Safe and idempotent to call multiple times.
        """
        if not self._cleaned_up and self._status_item is not None and self._status_bar is not None:
            self._status_bar.removeStatusItem_(self._status_item)
            self._status_item = None
            self._button = None
            self._cleaned_up = True

    def dealloc(self) -> None:
        """
        Safety cleanup upon garbage collection.
        """
        try:
            self.cleanup()
        except Exception:
            pass
        objc.super(LoLStatusItemController, self).dealloc()


if __name__ == "__main__":
    print("Self-testing status_item.LoLStatusItemController...")
    clicks = []

    controller = LoLStatusItemController(on_toggle_popover=lambda s: clicks.append(s))
    btn = controller.get_button()
    item = controller.get_status_item()
    assert btn is not None, "Button is None"
    assert item is not None, "Status item is None"

    # Test state transitions
    controller.set_state("normal")
    assert controller.get_current_state() == "normal"
    assert btn.image().isTemplate() is True

    controller.set_state("active")
    assert controller.get_current_state() == "active"
    assert btn.image().isTemplate() is False

    controller.set_state("paused")
    assert controller.get_current_state() == "paused"
    assert btn.image().isTemplate() is False

    # Test handle_click
    controller.handle_click(btn)
    assert len(clicks) == 1
    assert clicks[0] == btn

    # Test resilience
    controller.set_state("non_existent_xyz")
    assert controller.get_current_state() == "normal"
    controller.set_state("")
    assert controller.get_current_state() == "normal"
    controller.set_state(None)
    assert controller.get_current_state() == "normal"

    controller.cleanup()
    print("All status_item self-tests passed successfully!")
