"""Timer state machine: IDLE | RUNNING | PAUSED | AUTO_PAUSED.

Pure model without Qt. Durations use a monotonic clock; session timestamps
use wall-clock unix seconds.

Idle semantics:
- auto_pause() is retroactive: active time is rolled back to the moment idle
  started (now - reported idle seconds), not to the threshold crossing.
- The idle span lasts until the user resolves it (button press).
- KEEP -> PAUSED, RESUME -> RUNNING: the idle span is added to idle_seconds.
- DISCARD -> RUNNING: the idle span is dropped entirely.
- stop() while AUTO_PAUSED resolves the idle span as KEEP first.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class TimerState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    AUTO_PAUSED = "auto_paused"


class IdleChoice(Enum):
    KEEP = "keep"
    RESUME = "resume"
    DISCARD = "discard"


class InvalidTransition(RuntimeError):
    """Operation is not allowed in the current state."""


@dataclass(frozen=True)
class SessionResult:
    start_ts: int
    end_ts: int
    active_seconds: int
    idle_seconds: int


class TimerModel:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._clock = clock
        self._wall_clock = wall_clock
        self._reset()

    def _reset(self) -> None:
        self._state = TimerState.IDLE
        self._start_ts: int | None = None
        self._accumulated = 0.0
        self._segment_start = 0.0
        self._idle_total = 0.0
        self._idle_start = 0.0

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def start_ts(self) -> int | None:
        """Wall-clock unix time when the current session started."""
        return self._start_ts

    @property
    def active_seconds(self) -> float:
        if self._state is TimerState.RUNNING:
            return self._accumulated + (self._clock() - self._segment_start)
        return self._accumulated

    @property
    def idle_seconds(self) -> float:
        """Idle time already attributed to the session (excludes an unresolved span)."""
        return self._idle_total

    @property
    def pending_idle_seconds(self) -> float | None:
        """Length of the unresolved idle span while AUTO_PAUSED, else None."""
        if self._state is not TimerState.AUTO_PAUSED:
            return None
        return self._clock() - self._idle_start

    def start(self) -> None:
        self._require(TimerState.IDLE, op="start")
        self._start_ts = int(self._wall_clock())
        self._segment_start = self._clock()
        self._state = TimerState.RUNNING

    def pause(self) -> None:
        self._require(TimerState.RUNNING, op="pause")
        self._close_segment(self._clock())
        self._state = TimerState.PAUSED

    def resume(self) -> None:
        self._require(TimerState.PAUSED, op="resume")
        self._open_segment(self._clock())

    def toggle(self) -> None:
        """Start/Pause button: start, pause, resume, or resolve auto-pause as RESUME."""
        if self._state is TimerState.IDLE:
            self.start()
        elif self._state is TimerState.RUNNING:
            self.pause()
        elif self._state is TimerState.PAUSED:
            self.resume()
        else:
            self.resolve_idle(IdleChoice.RESUME)

    def auto_pause(self, idle_seconds: float) -> None:
        """Enter AUTO_PAUSED, rolling active time back to when idle started."""
        self._require(TimerState.RUNNING, op="auto_pause")
        now = self._clock()
        idle_start = max(self._segment_start, now - max(0.0, idle_seconds))
        self._close_segment(idle_start)
        self._idle_start = idle_start
        self._state = TimerState.AUTO_PAUSED

    def resolve_idle(self, choice: IdleChoice) -> None:
        self._require(TimerState.AUTO_PAUSED, op="resolve_idle")
        now = self._clock()
        if choice is not IdleChoice.DISCARD:
            self._idle_total += now - self._idle_start
        if choice is IdleChoice.KEEP:
            self._state = TimerState.PAUSED
        else:
            self._open_segment(now)

    def stop(self) -> SessionResult:
        """Finish the session, return its totals and reset to IDLE."""
        if self._state is TimerState.IDLE or self._start_ts is None:
            raise InvalidTransition("stop is not allowed in state IDLE")
        if self._state is TimerState.AUTO_PAUSED:
            self.resolve_idle(IdleChoice.KEEP)
        elif self._state is TimerState.RUNNING:
            self._close_segment(self._clock())
        result = SessionResult(
            start_ts=self._start_ts,
            end_ts=int(self._wall_clock()),
            active_seconds=round(self._accumulated),
            idle_seconds=round(self._idle_total),
        )
        self._reset()
        return result

    def _open_segment(self, now: float) -> None:
        self._segment_start = now
        self._state = TimerState.RUNNING

    def _close_segment(self, end: float) -> None:
        self._accumulated += end - self._segment_start

    def _require(self, expected: TimerState, op: str) -> None:
        if self._state is not expected:
            raise InvalidTransition(f"{op} is not allowed in state {self._state.name}")
