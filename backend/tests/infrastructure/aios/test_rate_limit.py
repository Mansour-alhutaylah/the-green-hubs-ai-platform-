"""The bounded rate limiter guarding the internal verification endpoint."""

import pytest

from app.infrastructure.aios.rate_limit import FixedWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_requests_within_the_limit_are_allowed() -> None:
    limiter = FixedWindowRateLimiter(limit=3, window_seconds=60, clock=FakeClock())
    assert [limiter.allow("k") for _ in range(3)] == [True, True, True]


def test_the_request_over_the_limit_is_refused() -> None:
    limiter = FixedWindowRateLimiter(limit=2, window_seconds=60, clock=FakeClock())
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False


def test_the_window_resets() -> None:
    clock = FakeClock()
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=clock)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
    clock.advance(60)
    assert limiter.allow("k") is True


def test_keys_are_counted_independently() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=FakeClock())
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False


def test_the_tracked_key_table_stays_bounded() -> None:
    """A caller cycling identifiers must not grow the table without
    bound. Overflow clears rather than evicting one by one: clearing is
    O(1), and forgiving one window's counts is strictly better than an
    unbounded dictionary inside a process serving product traffic."""

    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=FakeClock())
    for index in range(10_000):
        limiter.allow(f"key-{index}")
    assert len(limiter._windows) <= 4096  # noqa: SLF001 - asserting the bound is the point


def test_a_monotonic_clock_is_used_by_default() -> None:
    """A wall-clock jump -- an NTP correction on a busy host -- must not
    hand out a free window."""

    from time import monotonic

    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60)
    assert limiter._clock is monotonic  # noqa: SLF001


@pytest.mark.parametrize(
    "limit,window", [(0, 60), (-1, 60), (1, 0), (1, -5)]
)
def test_a_nonsensical_configuration_is_refused(limit: int, window: float) -> None:
    with pytest.raises(ValueError):
        FixedWindowRateLimiter(limit=limit, window_seconds=window)


def test_reset_forgets_every_window() -> None:
    limiter = FixedWindowRateLimiter(limit=1, window_seconds=60, clock=FakeClock())
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False
    limiter.reset()
    assert limiter.allow("k") is True
