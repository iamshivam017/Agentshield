from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.exc import DBAPIError

from agentshield_api.config import settings
from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, AgentPolicy, AuditEvent
from app.main import app

pytestmark = pytest.mark.asyncio


def policy_rules(limit: str = "1000.00") -> dict[str, object]:
    return {
        "transaction_limit": limit,
        "daily_limit": "5000.00",
        "verification_threshold": "0.25",
        "allowed_categories": ["SOFTWARE", "ELECTRONICS"],
    }


@pytest.mark.integration
async def test_policy_rotation_is_authorized_versioned_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_id = uuid4()
    monkeypatch.setattr(settings, "require_operator_auth", True)
    monkeypatch.setattr(settings, "operator_api_key", "operator-test-key")

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Policy Agent", status="ACTIVE"))
        session.add(AgentPolicy(id=uuid4(), agent_id=agent_id, version=1, is_active=True, rules=policy_rules()))
        await session.commit()

    payload = {"agent_id": str(agent_id), "rules": policy_rules("1500.00")}
    operator_headers = {"X-Operator-API-Key": "operator-test-key", "X-Operator-ID": "risk-admin"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        unauthorized = await client.post("/api/v1/policies", json=payload)
        assert unauthorized.status_code == 401

        created = await client.post("/api/v1/policies", json=payload, headers=operator_headers)
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["version"] == 2
        assert created_body["is_active"] is True
        assert created_body["rules"]["transaction_limit"] == "1500.00"
        assert created_body["rules"]["allowed_categories"] == ["SOFTWARE", "ELECTRONICS"]

        policies = await client.get(f"/api/v1/policies?agent_id={agent_id}", headers=operator_headers)
        assert policies.status_code == 200
        versions = {item["version"]: item for item in policies.json()}
        assert versions[1]["is_active"] is False
        assert versions[1]["rules"] == policy_rules()
        assert versions[2]["is_active"] is True

    async with SessionLocal() as session:
        audit = await session.scalar(
            select(AuditEvent)
            .where(AuditEvent.event_type == "POLICY_VERSION_CREATED", AuditEvent.actor_id == "risk-admin")
            .order_by(AuditEvent.occurred_at.desc())
        )
        assert audit is not None
        assert audit.payload["version"] == 2
        assert audit.payload["agent_id"] == str(agent_id)
        assert len(audit.payload["rules_hash"]) == 64

        await session.execute(delete(AuditEvent).where(AuditEvent.actor_id == "risk-admin"))
        await session.execute(delete(AgentPolicy).where(AgentPolicy.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()


async def test_policy_contract_rejects_unknown_and_incomplete_rules() -> None:
    agent_id = str(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        unknown = await client.post(
            "/api/v1/policies",
            json={"agent_id": agent_id, "rules": {"transaction_limit": "100.00", "daily_limit": "1000.00", "verification_threshold": "0.25", "mode": "danger"}},
        )
        assert unknown.status_code == 422

        incomplete = await client.post(
            "/api/v1/policies",
            json={"agent_id": agent_id, "rules": {"transaction_limit": "100.00", "daily_limit": "1000.00"}},
        )
        assert incomplete.status_code == 422


@pytest.mark.integration
async def test_policy_version_rules_are_immutable_but_activation_can_rotate() -> None:
    agent_id = uuid4()
    policy_id = uuid4()
    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Immutable Policy Agent", status="ACTIVE"))
        session.add(AgentPolicy(id=policy_id, agent_id=agent_id, version=1, is_active=True, rules=policy_rules()))
        await session.commit()

        policy = await session.get(AgentPolicy, policy_id)
        assert policy is not None
        policy.is_active = False
        await session.commit()

        policy = await session.get(AgentPolicy, policy_id)
        assert policy is not None
        assert policy.is_active is False
        original_rules = dict(policy.rules)
        policy.rules = {**policy.rules, "transaction_limit": "9999.00"}
        with pytest.raises(DBAPIError):
            await session.commit()
        await session.rollback()

        policy = await session.get(AgentPolicy, policy_id)
        assert policy is not None
        assert policy.rules == original_rules
        assert policy.version == 1

        await session.execute(delete(AgentPolicy).where(AgentPolicy.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
