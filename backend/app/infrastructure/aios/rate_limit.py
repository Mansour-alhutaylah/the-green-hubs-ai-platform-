"""A bounded fixed-window rate limiter for the internal AIOS endpoint.

**Why this exists, and what it deliberately is not.** The internal
verification endpoint is the one AIOS surface reachable without an
end-user token -- by design, since the orchestrator has no end-user
token to present. It performs no product action and touches no tenant
data, but it does exercise HMAC comparison, so it must not be an
unbounded compute surface.

This codebase has no existing rate-limiting convention: no middleware,
no dependency, no store. Rather than pretend otherwise, this is the
smallest correct thing that closes the gap, and its limits are stated
plainly:

* **Per process, not per deployment.** Two instances behind a load
  balancer each enforce the limit independently, so the effective ceiling
  is the limit times the instance count. Sufficient here because the only
  legitimate caller is one orchestrator making one call per orchestration
  request.
* **In memory, so it resets on restart.** Acceptable for an abuse brake;
  not acceptable for anything that must be durable -- which is exactly
  why request *deduplication* is explicitly out of scope for this
  foundation and required to be persistent before any mutating workflow.
  The two must not be confused: this bounds volume, it does not make
  anything idempotent.
* **Fixed window, not a token bucket.** A caller can burst twice the
  limit across a window boundary. Immaterial for an abuse brake, and a
  fixed window is auditable at a glance.

A distributed limiter belongs with the first workflow that has more than
one caller. Recorded as a known limitation rather than left implied.
"""

import threading
from dataclasses import dataclass
from time import monotonic
from typing import Callable, Final

#: Hard ceiling on tracked keys, so a caller cycling identifiers cannot
#: grow the table without bound. On overflow the table is cleared rather
#: than evicted one by one: clearing is O(1), and the worst case is that
#: one window's counts are forgiven -- strictly better than an unbounded
#: dictionary in a process serving product traffic.
_MAX_TRACKED_KEYS: Final = 4096


@dataclass
class _Window:
    started_at: float
    count: int


class FixedWindowRateLimiter:
    """Allows at most ``limit`` events per ``window_seconds`` per key."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._limit = limit
        self._window_seconds = window_seconds
        # Monotonic by default: a wall-clock jump (NTP correction, DST on
        # a misconfigured host) must not hand out a free window.
        self._clock = clock
        self._windows: dict[str, _Window] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record one event for ``key`` and report whether it is allowed."""

        now = self._clock()
        with self._lock:
            if len(self._windows) >= _MAX_TRACKED_KEYS and key not in self._windows:
                self._windows.clear()

            window = self._windows.get(key)
            if window is None or now - window.started_at >= self._window_seconds:
                self._windows[key] = _Window(started_at=now, count=1)
                return True

            if window.count >= self._limit:
                return False

            window.count += 1
            return True

    def reset(self) -> None:
        """Forget all recorded windows. Used by tests, never by routes."""

        with self._lock:
            self._windows.clear()
