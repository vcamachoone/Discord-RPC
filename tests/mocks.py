"""
mocks.py - Test Fixtures and Mocks for Discord RPC & Cocoa UI

Provides isolated, deterministic mocks for:
1. Discord IPC socket (pypresence.Presence) with fault-injection
2. PyObjC AppHelper main thread dispatch
3. Cocoa GUI controls (NSStatusItem, NSPopover, NSSwitch, NSButton)
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional


class MockPresence:
    """
    Mock implementation of pypresence.Presence with fault injection
    and call telemetry for testing DiscordRPCManager.
    """

    def __init__(self, client_id: str, **kwargs):
        self.client_id = client_id
        self.kwargs = kwargs
        self.connected: bool = False
        self.closed: bool = False
        self.connect_count: int = 0
        self.update_count: int = 0
        self.clear_count: int = 0
        self.close_count: int = 0
        self.last_payload: Optional[Dict[str, Any]] = None
        self.payload_history: List[Dict[str, Any]] = []

        # Fault injection hooks
        self.connect_exception: Optional[Exception] = None
        self.update_exception: Optional[Exception] = None
        self.update_delay: float = 0.0

    def connect(self) -> None:
        self.connect_count += 1
        if self.connect_exception:
            raise self.connect_exception
        self.connected = True

    def update(self, **kwargs) -> Dict[str, Any]:
        self.update_count += 1
        if self.update_delay > 0:
            time.sleep(self.update_delay)
        if self.update_exception:
            raise self.update_exception
        self.last_payload = dict(kwargs)
        self.payload_history.append(dict(kwargs))
        return {"status": "ok", "payload": kwargs}

    def clear(self, pid: Optional[int] = None) -> None:
        self.clear_count += 1
        self.last_payload = None

    def close(self) -> None:
        self.close_count += 1
        self.connected = False
        self.closed = True


class MockAppHelper:
    """
    Captures or immediately executes callbacks scheduled via
    PyObjCTools.AppHelper.callAfter.
    """

    def __init__(self, execute_immediately: bool = True):
        self.execute_immediately = execute_immediately
        self.calls: List[tuple] = []
        self._lock = threading.Lock()

    def callAfter(self, func: Callable, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            self.calls.append((func, args, kwargs))
        if self.execute_immediately:
            try:
                func(*args, **kwargs)
            except Exception as e:
                # Store error for test inspection
                pass

    def flush(self) -> None:
        """Executes all pending captured calls."""
        with self._lock:
            pending = list(self.calls)
            self.calls.clear()
        for func, args, kwargs in pending:
            func(*args, **kwargs)


class MockNSStatusBarButton:
    """Mock for NSStatusBarButton."""

    def __init__(self):
        self.image = None
        self.title = ""
        self.target = None
        self.action = None
        self.enabled = True

    def setImage_(self, img: Any) -> None:
        self.image = img

    def setTitle_(self, title: str) -> None:
        self.title = title

    def setTarget_(self, target: Any) -> None:
        self.target = target

    def setAction_(self, action: Any) -> None:
        self.action = action

    def performClick(self) -> None:
        if self.target and self.action:
            # Emulate Cocoa selector dispatch
            if callable(self.action):
                self.action(self)
            elif hasattr(self.target, str(self.action)):
                getattr(self.target, str(self.action))(self)


class MockNSStatusItem:
    """Mock for NSStatusItem."""

    def __init__(self):
        self._button = MockNSStatusBarButton()
        self.menu = None

    def button(self) -> MockNSStatusBarButton:
        return self._button

    def setMenu_(self, menu: Any) -> None:
        self.menu = menu


class MockNSPopover:
    """Mock for NSPopover."""

    def __init__(self):
        self.contentViewController = None
        self.behavior = 0
        self.animates = True
        self.appearance = None
        self.isShown = False
        self.anchor_view = None
        self.anchor_edge = None

    def showRelativeToRect_ofView_preferredEdge_(
        self, rect: Any, view: Any, edge: Any
    ) -> None:
        self.isShown = True
        self.anchor_view = view
        self.anchor_edge = edge

    def close(self) -> None:
        self.isShown = False

    def performClose_(self, sender: Any) -> None:
        self.close()
