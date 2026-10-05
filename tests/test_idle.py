import ctypes
import sys
import types
from typing import Any

import pytest

from furniture_timer import idle
from furniture_timer.idle import (
    NullIdleDetector,
    PynputIdleDetector,
    WindowsIdleDetector,
    _elapsed_ms,
    create_idle_detector,
)


def test_elapsed_ms_plain() -> None:
    assert _elapsed_ms(10_000, 4_000) == 6_000


def test_elapsed_ms_survives_tick_wraparound() -> None:
    assert _elapsed_ms(500, 0xFFFFFFFF - 499) == 1_000


def test_null_detector_is_inert() -> None:
    detector = NullIdleDetector()
    assert detector.available is False
    assert detector.idle_seconds() is None
    detector.stop()


def _fake_last_input(dw_time: int, ok: bool = True) -> Any:
    def get_last_input_info(info_ptr: Any) -> int:
        info_ptr.contents.dwTime = dw_time
        return 1 if ok else 0

    return get_last_input_info


def test_windows_detector_math_with_fakes() -> None:
    detector = WindowsIdleDetector(_fake_last_input(1_000), lambda: 6_500)
    assert detector.available
    assert detector.idle_seconds() == 5.5


def test_windows_detector_disables_after_runtime_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = {"n": 0}

    def flaky(info_ptr: Any) -> int:
        calls["n"] += 1
        return 1 if calls["n"] == 1 else 0

    detector = WindowsIdleDetector(flaky, lambda: 0)
    assert detector.available

    assert detector.idle_seconds() is None
    assert detector.idle_seconds() is None
    assert not detector.available
    assert caplog.text.count("Windows idle detection failed") == 1


def test_factory_degrades_when_win32_load_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise OSError("user32 missing")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(idle, "_load_win32_functions", boom)

    assert isinstance(create_idle_detector(), NullIdleDetector)


def test_factory_degrades_when_first_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        idle, "_load_win32_functions", lambda: (_fake_last_input(0, ok=False), lambda: 0)
    )

    assert isinstance(create_idle_detector(), NullIdleDetector)


def test_factory_degrades_without_pynput(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setitem(sys.modules, "pynput", None)

    assert isinstance(create_idle_detector(), NullIdleDetector)


class _FakeListener:
    IS_TRUSTED = True

    def __init__(self, **callbacks: Any) -> None:
        self.callbacks = callbacks
        self.daemon = False
        self.alive = False

    def start(self) -> None:
        self.alive = True

    def stop(self) -> None:
        self.alive = False

    def is_alive(self) -> bool:
        return self.alive


def _install_fake_pynput(monkeypatch: pytest.MonkeyPatch, trusted: bool = True) -> None:
    listener_cls = type("Listener", (_FakeListener,), {"IS_TRUSTED": trusted})
    package = types.ModuleType("pynput")
    package.mouse = types.SimpleNamespace(Listener=listener_cls)  # type: ignore[attr-defined]
    package.keyboard = types.SimpleNamespace(Listener=listener_cls)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", package)


def test_pynput_detector_tracks_last_input(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pynput(monkeypatch)
    now = [100.0]
    detector = PynputIdleDetector(clock=lambda: now[0])

    now[0] = 130.0
    assert detector.idle_seconds() == 30.0

    detector._listeners[1].callbacks["on_press"]("key")
    now[0] = 135.0
    assert detector.idle_seconds() == 5.0

    detector._listeners[0].alive = False
    assert detector.idle_seconds() is None
    assert not detector.available


def test_pynput_untrusted_listeners_degrade(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_pynput(monkeypatch, trusted=False)
    monkeypatch.setattr(sys, "platform", "darwin")

    assert isinstance(create_idle_detector(), NullIdleDetector)


@pytest.mark.skipif(sys.platform != "win32", reason="real Win32 API")
def test_real_windows_detector() -> None:
    detector = create_idle_detector()
    assert isinstance(detector, WindowsIdleDetector)
    value = detector.idle_seconds()
    assert value is not None and value >= 0
    assert ctypes.sizeof(idle._LastInputInfo) == 8
