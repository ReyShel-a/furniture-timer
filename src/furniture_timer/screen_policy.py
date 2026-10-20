"""Map a screen sample to pause, resume, or no change.

The screen check never starts or stops a session. A manual pause holds
until the user resumes. System-idle auto-pause is left to the idle dialog.
"""

from enum import Enum

from furniture_timer.screen_match import ScreenSignal
from furniture_timer.timer_model import TimerState


class ScreenAction(Enum):
    NONE = "none"
    PAUSE = "pause"
    RESUME = "resume"


def decide(
    state: TimerState,
    signal: str | None,
    *,
    manual_hold: bool,
    screen_paused: bool,
) -> ScreenAction:
    """signal None means the capture failed and the timer must stay as it is."""
    if signal is None or state is TimerState.IDLE or state is TimerState.AUTO_PAUSED:
        return ScreenAction.NONE
    if signal == ScreenSignal.ACTIVE:
        if state is TimerState.PAUSED and screen_paused and not manual_hold:
            return ScreenAction.RESUME
        return ScreenAction.NONE
    if state is TimerState.RUNNING:
        return ScreenAction.PAUSE
    return ScreenAction.NONE
