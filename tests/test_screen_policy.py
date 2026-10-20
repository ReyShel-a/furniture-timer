import pytest

from furniture_timer.screen_match import ScreenSignal
from furniture_timer.screen_policy import ScreenAction, decide
from furniture_timer.timer_model import TimerState


@pytest.mark.parametrize(
    ("state", "signal", "manual_hold", "screen_paused", "expected"),
    [
        (TimerState.IDLE, ScreenSignal.ACTIVE, False, False, ScreenAction.NONE),
        (TimerState.AUTO_PAUSED, ScreenSignal.ABSENT, False, False, ScreenAction.NONE),
        (TimerState.RUNNING, None, False, False, ScreenAction.NONE),
        (TimerState.RUNNING, ScreenSignal.ABSENT, False, False, ScreenAction.PAUSE),
        (TimerState.RUNNING, ScreenSignal.INTERRUPT, False, False, ScreenAction.PAUSE),
        (TimerState.RUNNING, ScreenSignal.ACTIVE, False, False, ScreenAction.NONE),
        (TimerState.PAUSED, ScreenSignal.ACTIVE, False, True, ScreenAction.RESUME),
        (TimerState.PAUSED, ScreenSignal.ACTIVE, True, False, ScreenAction.NONE),
        (TimerState.PAUSED, ScreenSignal.ACTIVE, True, True, ScreenAction.NONE),
        (TimerState.PAUSED, ScreenSignal.ABSENT, False, True, ScreenAction.NONE),
        (TimerState.IDLE, ScreenSignal.INTERRUPT, False, False, ScreenAction.NONE),
    ],
)
def test_decide(
    state: TimerState,
    signal: str | None,
    manual_hold: bool,
    screen_paused: bool,
    expected: ScreenAction,
) -> None:
    assert (
        decide(state, signal, manual_hold=manual_hold, screen_paused=screen_paused) is expected
    )


def test_actions_are_only_pause_and_resume() -> None:
    assert {item.value for item in ScreenAction} == {"none", "pause", "resume"}
