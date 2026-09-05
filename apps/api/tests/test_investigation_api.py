from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from agentshield_api.config import settings
from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, AgentPolicy, AuditEvent, Investigation, Merchant, PolicyEvaluation, RiskDecision, RiskPrediction, Transaction, TransactionFeature
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_investigation_api_persists_provenance_and_replays(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_operator_auth", True)
    monkeypatch.setattr(settings, "operator_analyst_api_key", "analyst-test-key")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    agent_id = uuid4()
    merchant_id = uuid4()
    transaction_id = uuid4()
    policy_id = uuid4()
    decision_id = uuid4()
    prediction_id = uuid4()
    feature_id = uuid4()
    policy_evaluation_id = uuid4()
    audit_id = uuid4()

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Investigation Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Investigation Merchant", category="SOFTWARE"))
        session.add(
            AgentPolicy(
                id=policy_id,
                agent_id=agent_id,
                version=1,
                is_active=True,
                rules={
                    "transaction_limit": "1000.00",
                    "daily_limit": "5000.00",
                    "verification_threshold": "0.25",
                    "allowed_categories": ["SOFTWARE"],
                },
            )
        )
        session.add(
            Transaction(
                id=transaction_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                amount=Decimal("250.00"),
                currency="INR",
                device_id="investigation-device",
                occurred_at="2026-09-05T10:00:00+00:00",
                status="EVALUATED",
            )
        )
        await session.flush()
        session.add(TransactionFeature(id=feature_id, transaction_id=transaction_id, feature_version="v1", values={"new_device": 1.0, "burst": 1.0}))
        session.add(RiskPrediction(id=prediction_id, transaction_id=transaction_id, model_version="baseline-logistic-v1", score=Decimal("0.82"), risk_band="HIGH", signals={"signals": ["new_device", "burst"]}))
        session.add(PolicyEvaluation(id=policy_evaluation_id, transaction_id=transaction_id, policy_version=1, result="VERIFY", violations=[]))
        session.add(RiskDecision(id=decision_id, transaction_id=transaction_id, decision="VERIFY", risk_score=Decimal("0.82"), risk_band="HIGH", model_version="baseline-logistic-v1", policy_version=1, reason_codes=["new_device", "burst"]))
        session.add(AuditEvent(id=audit_id, transaction_id=transaction_id, event_type="RISK_DECISION_CREATED", actor_type="AGENT", actor_id=str(agent_id), payload={"decision": "VERIFY"}))
        await session.commit()

    headers = {"X-Operator-API-Key": "analyst-test-key", "X-Operator-ID": "risk-analyst"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(f"/api/v1/risk/transactions/{transaction_id}/investigation", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["result"]["provider"] == "deterministic-fallback"
        assert len(body["evidence_hash"]) == 64
        assert {item["id"] for item in body["result"]["evidence"]} >= {"E1", "E6", "E10"}

        get_response = await client.get(f"/api/v1/risk/transactions/{transaction_id}/investigation", headers=headers)
        assert get_response.status_code == 200
        assert get_response.json()["evidence_hash"] == body["evidence_hash"]

    async with SessionLocal() as session:
        investigation = await session.scalar(select(Investigation).where(Investigation.transaction_id == transaction_id))
        assert investigation is not None
        assert investigation.evidence_hash == body["evidence_hash"]
        await session.execute(delete(Investigation).where(Investigation.transaction_id == transaction_id))
        await session.execute(delete(AuditEvent).where(AuditEvent.id == audit_id))
        await session.execute(delete(AuditEvent).where(AuditEvent.transaction_id == transaction_id))
        await session.execute(delete(RiskDecision).where(RiskDecision.id == decision_id))
        await session.execute(delete(RiskPrediction).where(RiskPrediction.id == prediction_id))
        await session.execute(delete(PolicyEvaluation).where(PolicyEvaluation.id == policy_evaluation_id))
        await session.execute(delete(TransactionFeature).where(TransactionFeature.id == feature_id))
        await session.execute(delete(Transaction).where(Transaction.id == transaction_id))
        await session.execute(delete(AgentPolicy).where(AgentPolicy.id == policy_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
