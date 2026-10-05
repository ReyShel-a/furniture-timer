"""Poll system idle, auto-pause, and drive the non-blocking idle dialog."""

import logging
from collections.abc import Callable
from typing import Final

from PySide6.QtCore import QObject, Qt, QTimer

from furniture_timer.formatting import format_hms
from furniture_timer.idle import IdleDetector
from furniture_timer.timer_model import IdleChoice, TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.idle_dialog import IdleDialog
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

IDLE_POLL_INTERVAL_MS: Final[int] = 1000


class IdleController(QObject):
    def __init__(
        self,
        model: TimerModel,
        widget: TimerWidget,
        dialog: IdleDialog,
        detector: IdleDetector,
        threshold: Callable[[], float],
        timer_controller: TimerController,
        interval_ms: int = IDLE_POLL_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._widget = widget
        self._dialog = dialog
        self._detector = detector
        self._threshold = threshold
        self._timer_controller = timer_controller
        self._user_returned = False
        self._last_reading: float | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(interval_ms)
        self._poll_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._poll_timer.timeout.connect(self.poll)

        dialog.keep_clicked.connect(lambda: self._resolve(IdleChoice.KEEP))
        dialog.resume_clicked.connect(lambda: self._resolve(IdleChoice.RESUME))
        dialog.discard_clicked.connect(lambda: self._resolve(IdleChoice.DISCARD))
        timer_controller.state_changed.connect(self.sync)
        self.sync()

    @property
    def is_polling(self) -> bool:
        return self._poll_timer.isActive()

    def poll(self) -> None:
        reading = self._detector.idle_seconds()
        if reading is None:
            return
        state = self._model.state
        if state is TimerState.RUNNING and reading >= self._threshold():
            self._auto_pause(reading)
        elif state is TimerState.AUTO_PAUSED:
            self._on_auto_paused_reading(reading)
        self._last_reading = reading

    def sync(self) -> None:
        state = self._model.state
        if state is TimerState.RUNNING or state is TimerState.AUTO_PAUSED:
            self._poll_timer.start()
        else:
            self._poll_timer.stop()
        if state is not TimerState.AUTO_PAUSED:
            self._dialog.hide()
            self._user_returned = False
            self._last_reading = None

    def _auto_pause(self, reading: float) -> None:
        self._model.auto_pause(reading)
        log.info("Auto-paused after %.1fs idle", reading)
        self._user_returned = False
        self._timer_controller.refresh()
        self._dialog.place_near(self._widget.frameGeometry())
        self._dialog.show_alert(self._pending_hms())

    def _on_auto_paused_reading(self, reading: float) -> None:
        self._model.observe_idle(reading)
        self._dialog.update_duration(self._pending_hms())
        if self._last_reading is not None and reading < self._last_reading:
            self._user_returned = True
            self._maybe_prompt()

    def _maybe_prompt(self) -> None:
        if (
            self._model.state is TimerState.AUTO_PAUSED
            and self._user_returned
            and not self._dialog.is_on_screen()
        ):
            self._dialog.place_near(self._widget.frameGeometry())
            self._dialog.show_prompt(self._pending_hms())

    def _resolve(self, choice: IdleChoice) -> None:
        if self._model.state is not TimerState.AUTO_PAUSED:
            return
        self._model.resolve_idle(choice)
        log.info("Idle resolved as %s", choice.value)
        self._dialog.hide()
        self._user_returned = False
        self._timer_controller.refresh()
        self.sync()

    def _pending_hms(self) -> str:
        pending = self._model.pending_idle_seconds
        return format_hms(0.0 if pending is None else pending)
