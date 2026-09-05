from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic, time
from typing import Protocol

from fastapi import HTTPException, status

from .config import settings


class RateStore(Protocol):
    def check(self, key: str, limit: int, window_seconds: int) -> int: ...


class InProcessRateStore:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> int:
        now = monotonic()
        with self._lock:
            events = self._events[key]
            while events and now - events[0] >= window_seconds:
                events.popleft()
            events.append(now)
            return len(events)


_REDIS_RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


class RedisRateStore:
    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def check(self, key: str, limit: int, window_seconds: int) -> int:
        bucket = int(time() // window_seconds)
        redis_key = f"agentshield:rate:{window_seconds}:{bucket}:{key}"
        result = self._client.eval(_REDIS_RATE_SCRIPT, 1, redis_key, window_seconds)
        return int(result)


class RateLimiter:
    """Fixed-window limiter with Redis distribution and safe local fallback."""

    def __init__(self, store: RateStore | None) -> None:
        self._store = store
        self._fallback = InProcessRateStore()

    def check(self, key: str) -> None:
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds
        if self._store is None:
            if settings.app_env.lower() in {"production", "staging"}:
                raise HTTPException(status_code=503, detail="rate_limit_backend_unavailable")
            self._check_store(self._fallback, key, limit, window)
            return

        try:
            self._check_store(self._store, key, limit, window)
        except HTTPException:
            raise
        except Exception as exc:
            if settings.app_env.lower() in {"production", "staging"}:
                raise HTTPException(status_code=503, detail="rate_limit_backend_unavailable") from exc
            self._check_store(self._fallback, key, limit, window)

    @staticmethod
    def _check_store(store: RateStore, key: str, limit: int, window: int) -> None:
        count = store.check(key, limit, window)
        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate_limit_exceeded",
                headers={"Retry-After": str(max(1, window - int(time()) % window))},
            )


def build_rate_limiter() -> RateLimiter:
    redis_url = getattr(settings, "redis_url", None)
    if redis_url:
        try:
            return RateLimiter(RedisRateStore(redis_url))
        except Exception:
            if settings.app_env.lower() in {"production", "staging"}:
                return RateLimiter(None)
    return RateLimiter(None)


rate_limiter = build_rate_limiter()
InProcessRateLimiter = InProcessRateStore
