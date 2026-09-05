from __future__ import annotations

import hashlib
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException

from agentshield_api.config import settings
from agentshield_api.contracts import RiskEvaluateRequest
from agentshield_api.rate_limit import InProcessRateLimiter
from agentshield_api.security import (
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
    _required_roles,
    authorize_agent,
    authorize_operator,
    require_operator,
)


def canonical_business_fingerprint(request: RiskEvaluateRequest) -> str:
    payload = request.model_dump(mode="json")
    payload.pop("idempotency_key", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def test_request_fingerprint_ignores_idempotency_key() -> None:
    payload = {
        "agent_id": str(uuid4()),
        "merchant_id": str(uuid4()),
        "amount": "100.00",
        "currency": "inr",
        "device_id": "device-1",
        "category": "software",
        "occurred_at": "2026-09-05T10:00:00Z",
    }
    first = RiskEvaluateRequest(**payload, idempotency_key="key-one-1")
    second = RiskEvaluateRequest(**payload, idempotency_key="key-two-2")
    assert canonical_business_fingerprint(first) == canonical_business_fingerprint(second)


def test_request_fingerprint_changes_for_business_request() -> None:
    common = {
        "agent_id": uuid4(),
        "merchant_id": uuid4(),
        "currency": "INR",
        "device_id": "device-1",
        "category": "software",
        "occurred_at": "2026-09-05T10:00:00Z",
    }
    first = RiskEvaluateRequest(**common, amount="100.00", idempotency_key="key-one-1")
    second = RiskEvaluateRequest(**common, amount="101.00", idempotency_key="key-one-1")
    assert canonical_business_fingerprint(first) != canonical_business_fingerprint(second)


def test_rate_limiter_rejects_after_limit(monkeypatch) -> None:
    monkeypatch.setattr("agentshield_api.rate_limit.settings.rate_limit_requests", 1)
    limiter = InProcessRateLimiter()
    limiter.check("caller")
    with pytest.raises(Exception) as exc_info:
        limiter.check("caller")
    assert getattr(exc_info.value, "status_code", None) == 429


def test_agent_auth_binds_identity(monkeypatch) -> None:
    agent_id = uuid4()
    monkeypatch.setattr(settings, "require_agent_auth", True)
    monkeypatch.setattr(settings, "agent_api_key", "agent-secret")

    with pytest.raises(HTTPException) as missing:
        authorize_agent(agent_id)
    assert missing.value.status_code == 401

    with pytest.raises(HTTPException) as mismatch:
        authorize_agent(agent_id, "agent-secret", uuid4())
    assert mismatch.value.status_code == 403

    authorize_agent(agent_id, "agent-secret", agent_id)


def test_operator_auth_requires_configured_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "require_operator_auth", False)
    monkeypatch.setattr(settings, "operator_api_key", None)
    monkeypatch.setattr(settings, "operator_admin_api_key", None)
    monkeypatch.setattr(settings, "operator_analyst_api_key", None)
    monkeypatch.setattr(settings, "operator_viewer_api_key", None)
    with pytest.raises(HTTPException) as not_configured:
        authorize_operator()
    assert not_configured.value.status_code == 503


def test_operator_roles_are_derived_from_secrets_and_enforced(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "require_operator_auth", False)
    monkeypatch.setattr(settings, "operator_api_key", None)
    monkeypatch.setattr(settings, "operator_admin_api_key", "admin-secret")
    monkeypatch.setattr(settings, "operator_analyst_api_key", "analyst-secret")
    monkeypatch.setattr(settings, "operator_viewer_api_key", "viewer-secret")

    assert require_operator("admin-secret", "admin-1").role == ROLE_ADMIN
    assert require_operator("analyst-secret", "analyst-1").role == ROLE_ANALYST
    assert require_operator("viewer-secret", "viewer-1").role == ROLE_VIEWER

    with pytest.raises(HTTPException) as analyst_denied:
        authorize_operator("analyst-secret", "analyst-1", {ROLE_ADMIN})
    assert analyst_denied.value.status_code == 403

    with pytest.raises(HTTPException) as viewer_denied:
        authorize_operator("viewer-secret", "viewer-1", {ROLE_ANALYST, ROLE_ADMIN})
    assert viewer_denied.value.status_code == 403


def test_operator_role_cannot_be_selected_by_header(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "require_operator_auth", False)
    monkeypatch.setattr(settings, "operator_api_key", "admin-secret")
    monkeypatch.setattr(settings, "operator_admin_api_key", None)
    monkeypatch.setattr(settings, "operator_analyst_api_key", None)
    monkeypatch.setattr(settings, "operator_viewer_api_key", None)

    principal = require_operator("admin-secret", "viewer-supplied")
    assert principal.role == ROLE_ADMIN
    assert principal.operator_id == "viewer-supplied"


def test_sensitive_control_plane_mutations_are_least_privilege() -> None:
    assert _required_roles("/api/v1/risk/transactions/123/investigation", "POST") == {ROLE_ANALYST, ROLE_ADMIN}
    assert _required_roles("/api/v1/payments/orders/123/reconcile", "POST") == {ROLE_ANALYST, ROLE_ADMIN}
    assert _required_roles("/api/v1/models/baseline/activate", "POST") == {ROLE_ADMIN}
    assert _required_roles("/api/v1/risk/transactions/123/investigation", "GET") == {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
