"""Session cost from active time and hourly rate (no Qt)."""


def live_cost(active_seconds: float, hourly_rate: float) -> float:
    """SPEC FR-3: elapsed_sec / 3600 * rate. Negative time clamps to zero."""
    return max(0.0, active_seconds) / 3600.0 * hourly_rate
