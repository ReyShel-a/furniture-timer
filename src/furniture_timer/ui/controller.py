"""Glue between TimerModel and TimerWidget: owns the tick and checkpoint timers."""

import logging
from collections.abc import Callable
from typing import Final

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from furniture_timer.cost import live_cost
from furniture_timer.formatting import format_hms
from furniture_timer.settings import DEFAULT_CURRENCY, DEFAULT_HOURLY_RATE
from furniture_timer.timer_model import (
    SessionResult,
    TimerModel,
    TimerSnapshot,
    TimerState,
)
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

TICK_INTERVAL_MS: Final[int] = 1000
CHECKPOINT_INTERVAL_MS: Final[int] = 30_000

# row id (None on the first write), result, rate, cost, finalized -> stored row id
SaveSession = Callable[[int | None, SessionResult, float, float, bool], int]


class TimerController(QObject):
    state_changed = Signal()

    def __init__(
        self,
        model: TimerModel,
        widget: TimerWidget,
        hourly_rate: Callable[[], float] = lambda: DEFAULT_HOURLY_RATE,
        currency: Callable[[], str] = lambda: DEFAULT_CURRENCY,
        save_session: SaveSession | None = None,
        interval_ms: int = TICK_INTERVAL_MS,
        checkpoint_interval_ms: int = CHECKPOINT_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._widget = widget
        self._hourly_rate = hourly_rate
        self._currency = currency
        self._save_session = save_session
        self._open_row_id: int | None = None
        self._writes_enabled = True
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.tick)
        self._checkpoint_timer = QTimer(self)
        self._checkpoint_timer.setInterval(checkpoint_interval_ms)
        self._checkpoint_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._checkpoint_timer.timeout.connect(self.checkpoint)

        widget.start_pause_clicked.connect(self._on_start_pause)
        widget.stop_clicked.connect(self._on_stop)

        self.refresh()

    @property
    def is_ticking(self) -> bool:
        return self._timer.isActive()

    @property
    def is_checkpointing(self) -> bool:
        return self._checkpoint_timer.isActive()

    @property
    def state(self) -> TimerState:
        return self._model.state

    def tick(self) -> None:
        self._render(self._model.snapshot())

    def checkpoint(self) -> None:
        """Write the open session in place. The row stays unfinished."""
        result = self._model.session_snapshot()
        if result is None:
            return
        self._write(result, finalized=False)

    def finalize_open_session(self) -> None:
        """Store the open session as finished without stopping the model.

        Used when the application is quitting, so the latest totals are on disk
        even though the user did not press Stop.
        """
        result = self._model.session_snapshot()
        if result is None:
            return
        self._write(result, finalized=True)

    def toggle_start_pause(self) -> None:
        self._on_start_pause()

    def _on_start_pause(self) -> None:
        if self._model.state is TimerState.IDLE:
            self._writes_enabled = True
            self._open_row_id = None
        self._model.toggle()
        self.refresh()

    def _on_stop(self) -> None:
        if self._model.state is TimerState.IDLE:
            return
        result = self._model.stop()
        rate = self._hourly_rate()
        cost = live_cost(result.active_seconds, rate)
        log.info(
            "Session stopped: active=%ss idle=%ss rate=%s cost=%s",
            result.active_seconds,
            result.idle_seconds,
            rate,
            cost,
        )
        self._write(result, finalized=True)
        self.refresh()

    def refresh(self) -> None:
        snap = self._model.snapshot()
        self._render(snap)
        self._sync_timers(snap.state)
        if snap.state is not TimerState.IDLE:
            self.checkpoint()
        self.state_changed.emit()

    def _write(self, result: SessionResult, finalized: bool) -> None:
        if self._save_session is None or not self._writes_enabled:
            return
        rate = self._hourly_rate()
        cost = live_cost(result.active_seconds, rate)
        try:
            stored_id = self._save_session(
                self._open_row_id, result, rate, cost, finalized
            )
        except Exception:
            log.exception("Failed to persist session")
            return
        if finalized:
            self._open_row_id = None
            self._writes_enabled = False
            self._checkpoint_timer.stop()
            return
        self._open_row_id = stored_id

    def _render(self, snap: TimerSnapshot) -> None:
        rate = self._hourly_rate()
        cost = live_cost(snap.active_seconds, rate)
        self._widget.show_time(format_hms(snap.active_seconds))
        self._widget.show_price(rate, cost, self._currency())
        self._widget.show_state(snap.state)
        self._widget.show_session_start(snap.start_ts)

    def _sync_timers(self, state: TimerState) -> None:
        if state is TimerState.RUNNING:
            self._timer.start()
        else:
            self._timer.stop()
        if state is TimerState.IDLE or not self._writes_enabled:
            self._checkpoint_timer.stop()
        elif not self._checkpoint_timer.isActive():
            self._checkpoint_timer.start()
