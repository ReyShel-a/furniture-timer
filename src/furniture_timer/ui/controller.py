"""Glue between TimerModel and TimerWidget: owns the 1 s tick QTimer."""

import logging
from typing import Final

from PySide6.QtCore import QObject, Qt, QTimer

from furniture_timer.formatting import format_hms
from furniture_timer.timer_model import TimerModel, TimerSnapshot, TimerState
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

TICK_INTERVAL_MS: Final[int] = 1000


class TimerController(QObject):
    def __init__(
        self,
        model: TimerModel,
        widget: TimerWidget,
        interval_ms: int = TICK_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._widget = widget
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self.tick)

        widget.start_pause_clicked.connect(self._on_start_pause)
        widget.stop_clicked.connect(self._on_stop)

        self._refresh()

    @property
    def is_ticking(self) -> bool:
        return self._timer.isActive()

    def tick(self) -> None:
        self._render(self._model.snapshot())

    def _on_start_pause(self) -> None:
        self._model.toggle()
        self._refresh()

    def _on_stop(self) -> None:
        if self._model.state is TimerState.IDLE:
            return
        result = self._model.stop()
        log.info(
            "Session stopped: active=%ss idle=%ss",
            result.active_seconds,
            result.idle_seconds,
        )
        self._refresh()

    def _refresh(self) -> None:
        snap = self._model.snapshot()
        self._render(snap)
        self._sync_timer(snap.state)

    def _render(self, snap: TimerSnapshot) -> None:
        self._widget.show_time(format_hms(snap.active_seconds))
        self._widget.show_state(snap.state)
        self._widget.show_session_start(snap.start_ts)

    def _sync_timer(self, state: TimerState) -> None:
        if state is TimerState.RUNNING:
            self._timer.start()
        else:
            self._timer.stop()
