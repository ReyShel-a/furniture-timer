import pytest

from furniture_timer.timer_model import (
    IdleChoice,
    InvalidTransition,
    TimerModel,
    TimerState,
)

WALL_START = 1_700_000_000.0
THRESHOLD = 300.0


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def wall(self) -> float:
        return WALL_START + self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def model(clock: FakeClock) -> TimerModel:
    return TimerModel(clock=clock, wall_clock=clock.wall)


def _auto_paused_example(model: TimerModel, clock: FakeClock) -> None:
    """Work 100 s, idle starts at T0=100, threshold fires at T0+300, decision at T0+510."""
    model.start()
    clock.advance(100 + THRESHOLD)
    model.auto_pause(THRESHOLD)
    clock.advance(210)


def test_initial_state(model: TimerModel) -> None:
    assert model.state is TimerState.IDLE
    assert model.active_seconds == 0
    assert model.start_ts is None
    assert model.pending_idle_seconds is None


def test_run_pause_resume_accumulates(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(10)
    assert model.active_seconds == 10

    model.pause()
    clock.advance(5)
    assert model.state is TimerState.PAUSED
    assert model.active_seconds == 10

    model.resume()
    clock.advance(3)
    assert model.state is TimerState.RUNNING
    assert model.active_seconds == 13


def test_toggle_cycles_states(model: TimerModel) -> None:
    model.toggle()
    assert model.state is TimerState.RUNNING
    model.toggle()
    assert model.state is TimerState.PAUSED
    model.toggle()
    assert model.state is TimerState.RUNNING


@pytest.mark.parametrize(
    ("setup", "op"),
    [
        ([], "pause"),
        ([], "resume"),
        ([], "stop"),
        ([], "auto_pause"),
        (["start"], "start"),
        (["start"], "resume"),
        (["start"], "resolve_idle"),
        (["start", "pause"], "pause"),
        (["start", "pause"], "auto_pause"),
    ],
)
def test_invalid_transitions_raise(model: TimerModel, setup: list[str], op: str) -> None:
    for step in setup:
        getattr(model, step)()
    args: dict[str, tuple[object, ...]] = {
        "auto_pause": (THRESHOLD,),
        "resolve_idle": (IdleChoice.RESUME,),
    }
    with pytest.raises(InvalidTransition):
        getattr(model, op)(*args.get(op, ()))


def test_auto_pause_is_retroactive(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(100 + THRESHOLD)
    model.auto_pause(THRESHOLD)

    assert model.state is TimerState.AUTO_PAUSED
    assert model.active_seconds == 100
    clock.advance(200)
    assert model.active_seconds == 100
    assert model.pending_idle_seconds == THRESHOLD + 200


def test_keep_pauses_and_records_idle(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    model.resolve_idle(IdleChoice.KEEP)

    assert model.state is TimerState.PAUSED
    assert model.idle_seconds == 510
    clock.advance(50)
    assert model.active_seconds == 100


def test_resume_runs_and_records_idle(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    model.resolve_idle(IdleChoice.RESUME)

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == 510
    clock.advance(20)
    assert model.active_seconds == 120


def test_discard_runs_and_drops_idle(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    model.resolve_idle(IdleChoice.DISCARD)

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == 0
    clock.advance(20)
    assert model.active_seconds == 120


def test_toggle_in_auto_paused_acts_as_resume(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    model.toggle()

    assert model.state is TimerState.RUNNING
    assert model.idle_seconds == 510


def test_idle_longer_than_segment_is_clamped(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(50)
    model.pause()
    clock.advance(1000)
    model.resume()
    clock.advance(400)
    model.auto_pause(2000)

    assert model.active_seconds == 50
    assert model.pending_idle_seconds == 400


def test_negative_idle_is_treated_as_zero(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(10)
    model.auto_pause(-5)

    assert model.active_seconds == 10
    assert model.pending_idle_seconds == 0


def test_stop_returns_totals_and_resets(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(3600.4)
    result = model.stop()

    assert result.start_ts == int(WALL_START)
    assert result.end_ts == int(WALL_START + 3600.4)
    assert result.active_seconds == 3600
    assert result.idle_seconds == 0
    assert model.state is TimerState.IDLE
    assert model.active_seconds == 0
    assert model.start_ts is None


def test_stop_while_paused(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    clock.advance(30)
    model.pause()
    clock.advance(100)

    assert model.stop().active_seconds == 30


def test_stop_while_auto_paused_counts_as_keep(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    result = model.stop()

    assert result.active_seconds == 100
    assert result.idle_seconds == 510
    assert model.state is TimerState.IDLE


def test_multiple_idle_cycles_accumulate(model: TimerModel, clock: FakeClock) -> None:
    model.start()
    for _ in range(2):
        clock.advance(60 + THRESHOLD)
        model.auto_pause(THRESHOLD)
        clock.advance(10)
        model.resolve_idle(IdleChoice.RESUME)
    clock.advance(60)
    model.auto_pause(0)
    model.resolve_idle(IdleChoice.DISCARD)

    result = model.stop()
    assert result.active_seconds == 180
    assert result.idle_seconds == 2 * (THRESHOLD + 10)


def test_new_session_after_stop_starts_clean(model: TimerModel, clock: FakeClock) -> None:
    _auto_paused_example(model, clock)
    model.stop()
    clock.advance(5)
    model.start()
    clock.advance(7)

    assert model.active_seconds == 7
    assert model.idle_seconds == 0
    assert model.start_ts == int(WALL_START + clock.now - 7)
