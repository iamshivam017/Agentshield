from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException

from agentshield_api.config import settings
from agentshield_api.rate_limit import InProcessRateLimiter, RateLimiter, RedisRateStore


class FakeRedisStore:
    def __init__(self, counts: list[int]) -> None:
        self.counts = iter(counts)
        self.calls: list[tuple[str, int, int]] = []

    def check(self, key: str, limit: int, window_seconds: int) -> int:
        self.calls.append((key, limit, window_seconds))
        return next(self.counts)


def test_in_process_rate_limiter_keeps_existing_contract(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 1)
    limiter = InProcessRateLimiter()
    limiter.check("caller")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("caller")
    assert exc_info.value.status_code == 429


def test_redis_rate_limiter_enforces_shared_counter(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    store = FakeRedisStore([1, 2, 3])
    limiter = RateLimiter(store)

    limiter.check("caller")
    limiter.check("caller")
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("caller")

    assert exc_info.value.status_code == 429
    assert len(store.calls) == 3
    assert store.calls[0][0] == "caller"


def test_protected_environment_fails_closed_without_redis(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "rate_limit_requests", 10)
    limiter = RateLimiter(None)
    with pytest.raises(HTTPException) as exc_info:
        limiter.check("caller")
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "rate_limit_backend_unavailable"


@pytest.mark.integration
def test_live_redis_store_when_configured() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL not configured")

    store = RedisRateStore(redis_url)
    key = f"integration-{uuid.uuid4()}"
    first = store.check(key, limit=2, window_seconds=60)
    second = store.check(key, limit=2, window_seconds=60)
    third = store.check(key, limit=2, window_seconds=60)

    assert (first, second, third) == (1, 2, 3)
