from __future__ import annotations

import os
from uuid import uuid4

os.environ.setdefault("APP_ENV", "development")

from agentshield_api.contracts import RiskEvaluateRequest
from agentshield_api.main import request_hash
from agentshield_api.rate_limit import InProcessRateLimiter


def test_request_hash_ignores_idempotency_key() -> None:
    payload = {
        "agent_id": str(uuid4()),
        "merchant_id": str(uuid4()),
        "amount": "100.00",
        "currency": "inr",
        "device_id": "device-1",
        "category": "software",
        "occurred_at": "2026-09-05T10:00:00Z",
    }
    first = RiskEvaluateRequest(**payload, idempotency_key="key-one")
    second = RiskEvaluateRequest(**payload, idempotency_key="key-two")
    assert request_hash(first) == request_hash(second)


def test_request_hash_changes_for_business_request() -> None:
    common = {
        "agent_id": uuid4(),
        "merchant_id": uuid4(),
        "currency": "INR",
        "device_id": "device-1",
        "category": "software",
        "occurred_at": "2026-09-05T10:00:00Z",
    }
    first = RiskEvaluateRequest(**common, amount="100.00", idempotency_key="key-one")
    second = RiskEvaluateRequest(**common, amount="101.00", idempotency_key="key-one")
    assert request_hash(first) != request_hash(second)


def test_rate_limiter_rejects_after_limit(monkeypatch) -> None:
    monkeypatch.setattr("agentshield_api.rate_limit.settings.rate_limit_requests", 1)
    limiter = InProcessRateLimiter()
    limiter.check("caller")
    try:
        limiter.check("caller")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 429
    else:
        raise AssertionError("second request should be rate limited")
