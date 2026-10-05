"""System-wide user idle detection.

Windows uses user32.GetLastInputInfo; other platforms fall back to pynput
global listeners. Any failure disables the feature instead of raising.
"""

import ctypes
import logging
import sys
import time
from collections.abc import Callable
from typing import Any, Protocol

log = logging.getLogger(__name__)

_TICK_MASK = 0xFFFFFFFF


class IdleDetector(Protocol):
    @property
    def available(self) -> bool: ...

    def idle_seconds(self) -> float | None:
        """Seconds since last user input, or None if detection is unavailable."""
        ...

    def stop(self) -> None: ...


class NullIdleDetector:
    """Used when idle detection cannot work; the timer keeps running without it."""

    @property
    def available(self) -> bool:
        return False

    def idle_seconds(self) -> float | None:
        return None

    def stop(self) -> None:
        pass


def _elapsed_ms(now_tick: int, last_input_tick: int) -> int:
    """Difference of two 32-bit millisecond tick counters, robust to the 49.7-day wrap."""
    return (now_tick - last_input_tick) & _TICK_MASK


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("dwTime", ctypes.c_uint32)]


GetLastInputInfoFn = Callable[[Any], int]
GetTickCountFn = Callable[[], int]


def _load_win32_functions() -> tuple[GetLastInputInfoFn, GetTickCountFn]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    get_last_input_info = user32.GetLastInputInfo
    get_last_input_info.argtypes = [ctypes.POINTER(_LastInputInfo)]
    get_last_input_info.restype = ctypes.c_int
    get_tick_count = kernel32.GetTickCount
    get_tick_count.argtypes = []
    get_tick_count.restype = ctypes.c_uint32
    return get_last_input_info, get_tick_count


class WindowsIdleDetector:
    def __init__(
        self,
        get_last_input_info: GetLastInputInfoFn | None = None,
        get_tick_count: GetTickCountFn | None = None,
    ) -> None:
        if get_last_input_info is None or get_tick_count is None:
            get_last_input_info, get_tick_count = _load_win32_functions()
        self._get_last_input_info = get_last_input_info
        self._get_tick_count = get_tick_count
        self._available = True
        self.idle_seconds()

    @property
    def available(self) -> bool:
        return self._available

    def idle_seconds(self) -> float | None:
        if not self._available:
            return None
        try:
            info = _LastInputInfo(cbSize=ctypes.sizeof(_LastInputInfo))
            if not self._get_last_input_info(ctypes.pointer(info)):
                raise OSError(f"GetLastInputInfo failed (error {ctypes.get_last_error()})")
            return _elapsed_ms(self._get_tick_count(), info.dwTime) / 1000.0
        except Exception:
            log.warning("Windows idle detection failed; disabling it", exc_info=True)
            self._available = False
            return None

    def stop(self) -> None:
        pass


class PynputIdleDetector:
    """Tracks the timestamp of the last mouse/keyboard event via pynput listeners."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        from pynput import keyboard, mouse

        self._clock = clock
        self._last_input = clock()
        self._available = True
        self._listeners = [
            mouse.Listener(on_move=self._touch, on_click=self._touch, on_scroll=self._touch),
            keyboard.Listener(on_press=self._touch, on_release=self._touch),
        ]
        for listener in self._listeners:
            listener.daemon = True
            listener.start()
        # macOS listeners silently receive nothing without Accessibility permission.
        if not all(getattr(listener, "IS_TRUSTED", True) for listener in self._listeners):
            self.stop()
            raise PermissionError("pynput listeners are not trusted by the OS")

    @property
    def available(self) -> bool:
        return self._available

    def idle_seconds(self) -> float | None:
        if not self._available:
            return None
        if not all(listener.is_alive() for listener in self._listeners):
            log.warning("pynput listener stopped unexpectedly; disabling idle detection")
            self.stop()
            return None
        return max(0.0, self._clock() - self._last_input)

    def stop(self) -> None:
        self._available = False
        for listener in self._listeners:
            try:
                listener.stop()
            except Exception:
                log.debug("Failed to stop pynput listener", exc_info=True)

    def _touch(self, *_: object) -> None:
        self._last_input = self._clock()


def create_idle_detector() -> IdleDetector:
    """Return the best detector for this platform, or NullIdleDetector on any failure."""
    detector: IdleDetector
    try:
        if sys.platform == "win32":
            detector = WindowsIdleDetector()
        else:
            detector = PynputIdleDetector()
    except Exception:
        log.warning("Idle detection unavailable; feature disabled", exc_info=True)
        return NullIdleDetector()
    if not detector.available:
        log.warning("Idle detection failed its first probe; feature disabled")
        detector.stop()
        return NullIdleDetector()
    log.info("Idle detection backend: %s", type(detector).__name__)
    return detector
