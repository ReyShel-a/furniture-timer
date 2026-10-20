"""Sample monitors every 30s and pause or resume the open session."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Final

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from furniture_timer import paths
from furniture_timer.i18n import t
from furniture_timer.screen_match import best_score, judge
from furniture_timer.screen_policy import ScreenAction, decide
from furniture_timer.screen_zones import (
    GrayBuffer,
    ZoneRole,
    has_active_zone,
    load_profile,
    save_profile,
)
from furniture_timer.settings import Settings
from furniture_timer.timer_model import InvalidTransition, TimerModel, TimerState
from furniture_timer.ui.controller import TimerController
from furniture_timer.ui.screen_dialog import ScreenDialog
from furniture_timer.ui.screen_grab import grab_screens
from furniture_timer.ui.settings_dialog import SettingsDialog
from furniture_timer.ui.widget import TimerWidget

log = logging.getLogger(__name__)

SAMPLE_INTERVAL_MS: Final[int] = 30_000
FIRST_SAMPLE_MS: Final[int] = 1_000

Grabber = Callable[[], list[GrayBuffer]]


class ScreenController(QObject):
    _matched = Signal(str)

    def __init__(
        self,
        model: TimerModel,
        widget: TimerWidget,
        settings_dialog: SettingsDialog,
        dialog: ScreenDialog,
        settings: Settings,
        timer_controller: TimerController,
        profile_dir: Path | None = None,
        grabber: Grabber | None = None,
        interval_ms: int = SAMPLE_INTERVAL_MS,
        first_sample_ms: int = FIRST_SAMPLE_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._widget = widget
        self._dialog = dialog
        self._settings = settings
        self._timer_controller = timer_controller
        self._root = profile_dir if profile_dir is not None else paths.screen_profile_dir()
        self._grabber = grabber if grabber is not None else grab_screens
        self._profile = load_profile(self._root)
        self._manual_hold = False
        self._screen_paused = False
        self._matching = False
        self._matched.connect(self._on_matched)

        self._poll = QTimer(self)
        self._poll.setInterval(interval_ms)
        self._poll.setTimerType(Qt.TimerType.CoarseTimer)
        self._poll.timeout.connect(self.sample)
        self._soon = QTimer(self)
        self._soon.setSingleShot(True)
        self._soon.setInterval(first_sample_ms)
        self._soon.setTimerType(Qt.TimerType.CoarseTimer)
        self._soon.timeout.connect(self.sample)

        settings_dialog.screen_clicked.connect(self.open_editor)
        dialog.save_clicked.connect(self._on_save)
        dialog.cancel_clicked.connect(dialog.hide)
        dialog.check_clicked.connect(self.check_now)
        timer_controller.state_changed.connect(self._on_state)
        self._on_state()

    @property
    def is_polling(self) -> bool:
        return self._poll.isActive()

    @property
    def sample_interval_ms(self) -> int:
        return self._poll.interval()

    def open_editor(self) -> None:
        self._dialog.load_from(self._profile, self._settings.screen_auto_enabled)
        self._dialog.show()
        self._dialog.raise_()
        self._dialog.activateWindow()

    def sample(self, *, block: bool = False) -> None:
        """Pause or resume from the latest monitor image. Failures leave the timer."""
        if not self._wants_poll() or self._matching:
            return
        try:
            grabs = self._grabber()
            if not grabs:
                raise RuntimeError("no screens")
        except Exception:
            log.warning("Screen sample failed; timer left unchanged", exc_info=True)
            return
        zones = tuple(self._profile.zones)
        if block:
            self._apply_signal(self._read_signal(grabs))
            return
        self._matching = True
        threading.Thread(
            target=self._score_later,
            args=(grabs, zones),
            daemon=True,
        ).start()

    def _score_later(
        self,
        grabs: list[GrayBuffer],
        zones: tuple[object, ...],
    ) -> None:
        signal = self._read_signal(grabs, zones)
        self._matched.emit("" if signal is None else signal)

    def _on_matched(self, signal: str) -> None:
        self._matching = False
        self._apply_signal(signal or None)

    def _apply_signal(self, signal: str | None) -> None:
        if signal is None or not self._wants_poll():
            return
        action = decide(
            self._model.state,
            signal,
            manual_hold=self._manual_hold,
            screen_paused=self._screen_paused,
        )
        if action is ScreenAction.PAUSE:
            self._apply_pause()
        elif action is ScreenAction.RESUME:
            self._apply_resume()

    def check_now(self) -> None:
        """Score the editor's current zones without changing the timer."""
        needles = self._dialog.draft_needles()
        if not needles:
            self._dialog.show_status(t("screen.signal.absent"))
            return
        try:
            grabs = self._grabber()
        except Exception:
            log.warning("Screen check failed", exc_info=True)
            self._dialog.show_status(t("screen.error.capture"), error=True)
            return
        if not grabs:
            self._dialog.show_status(t("screen.error.capture"), error=True)
            return
        lines: list[str] = []
        scored: list[tuple[ZoneRole, float]] = []
        for name, role, crop in needles:
            score = max((best_score(grab, crop) for grab in grabs), default=0.0)
            scored.append((role, score))
            lines.append(t("screen.check.zone", name=name, score=f"{score:.2f}"))
        lines.append(t(f"screen.signal.{judge(scored)}"))
        self._dialog.show_status("\n".join(lines))

    def _on_save(self) -> None:
        if self._dialog.enabled() and not self._dialog.has_active_zone():
            self._dialog.show_status(t("screen.error.need_active"), error=True)
            return
        try:
            profile = self._dialog.build_profile()
            save_profile(self._root, profile)
            self._settings.screen_auto_enabled = self._dialog.enabled()
            self._settings.save()
        except Exception:
            log.exception("Could not save screen zones")
            self._dialog.show_status(t("screen.error.save"), error=True)
            return
        self._profile = profile
        log.info(
            "Screen zones saved: enabled=%s zones=%d",
            self._settings.screen_auto_enabled,
            len(profile.zones),
        )
        self._dialog.hide()
        self._on_state()

    def _on_state(self) -> None:
        state = self._model.state
        if state is TimerState.IDLE:
            self._manual_hold = False
            self._screen_paused = False
        elif state is TimerState.PAUSED:
            if not self._screen_paused:
                self._manual_hold = True
        elif state is TimerState.RUNNING:
            self._manual_hold = False
            self._screen_paused = False
        self._sync_poll()
        self._widget.show_screen_status(self._status_key())

    def _apply_pause(self) -> None:
        self._screen_paused = True
        try:
            self._model.pause()
        except InvalidTransition:
            self._screen_paused = False
            log.warning("Screen pause ignored", exc_info=True)
            return
        log.info("Screen paused the session")
        self._timer_controller.refresh()

    def _apply_resume(self) -> None:
        try:
            self._model.resume()
        except InvalidTransition:
            log.warning("Screen resume ignored", exc_info=True)
            return
        self._screen_paused = False
        log.info("Screen resumed the session")
        self._timer_controller.refresh()

    def _read_signal(
        self,
        grabs: list[GrayBuffer],
        zones: tuple[object, ...] | None = None,
    ) -> str | None:
        try:
            if not grabs:
                raise RuntimeError("no screens")
            scored: list[tuple[ZoneRole, float]] = []
            for zone in self._profile.zones if zones is None else zones:
                score = max((best_score(grab, zone.crop) for grab in grabs), default=0.0)
                scored.append((zone.role, score))
            return judge(scored)
        except Exception:
            log.warning("Screen sample failed; timer left unchanged", exc_info=True)
            return None

    def _wants_poll(self) -> bool:
        if not self._settings.screen_auto_enabled or not has_active_zone(self._profile):
            return False
        state = self._model.state
        if state is TimerState.RUNNING:
            return True
        return state is TimerState.PAUSED and self._screen_paused and not self._manual_hold

    def _sync_poll(self) -> None:
        if not self._wants_poll():
            self._poll.stop()
            self._soon.stop()
            return
        if not self._poll.isActive():
            self._poll.start()
            self._soon.start()

    def _status_key(self) -> str | None:
        if not self._settings.screen_auto_enabled:
            return None
        state = self._model.state
        if state is TimerState.RUNNING:
            return "widget.tooltip.screen_active"
        if state is TimerState.PAUSED and self._manual_hold:
            return "widget.tooltip.screen_hold"
        if state is TimerState.PAUSED and self._screen_paused:
            return "widget.tooltip.screen_paused"
        return None
