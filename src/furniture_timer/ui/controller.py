"""Glue between TimerModel and TimerWidget: owns the 1 s tick QTimer."""

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

PersistSession = Callable[[SessionResult, float, float], None]


class TimerController(QObject):
    state_changed = Signal()

    def __init__(
        self,
        model: TimerModel,
        widget: TimerWidget,
        hourly_rate: Callable[[], float] = lambda: DEFAULT_HOURLY_RATE,
        currency: Callable[[], str] = lambda: DEFAULT_CURRENCY,
        persist_session: PersistSession | None = None,
        interval_ms: int = TICK_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._widget = widget
        self._hourly_rate = hourly_rate
        self._currency = currency
        self._persist_session = persist_session
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.tick)

        widget.start_pause_clicked.connect(self._on_start_pause)
        widget.stop_clicked.connect(self._on_stop)

        self.refresh()

    @property
    def is_ticking(self) -> bool:
        return self._timer.isActive()

    def tick(self) -> None:
        self._render(self._model.snapshot())

    def _on_start_pause(self) -> None:
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
        if self._persist_session is not None:
            try:
                self._persist_session(result, rate, cost)
            except Exception:
                log.exception("Failed to persist session")
        self.refresh()

    def refresh(self) -> None:
        snap = self._model.snapshot()
        self._render(snap)
        self._sync_timer(snap.state)
        self.state_changed.emit()

    def _render(self, snap: TimerSnapshot) -> None:
        rate = self._hourly_rate()
        cost = live_cost(snap.active_seconds, rate)
        self._widget.show_time(format_hms(snap.active_seconds))
        self._widget.show_price(rate, cost, self._currency())
        self._widget.show_state(snap.state)
        self._widget.show_session_start(snap.start_ts)

    def _sync_timer(self, state: TimerState) -> None:
        if state is TimerState.RUNNING:
            self._timer.start()
        else:
            self._timer.stop()
