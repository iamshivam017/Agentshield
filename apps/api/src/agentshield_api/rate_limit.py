from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from fastapi import HTTPException, status

from .config import settings


class InProcessRateLimiter:
    """Bounded fixed-window limiter for a single API instance.

    Production multi-instance deployments should replace this state store with
    Redis so limits are shared across replicas.
    """

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = monotonic()
        window = settings.rate_limit_window_seconds
        limit = settings.rate_limit_requests
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window:
                events.popleft()
            if len(events) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="rate_limit_exceeded",
                    headers={"Retry-After": str(max(1, int(window - (now - events[0]))))},
                )
            events.append(now)


rate_limiter = InProcessRateLimiter()
