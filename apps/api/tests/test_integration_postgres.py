from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, AgentPolicy, Merchant, Transaction
from app.main import app

pytestmark = pytest.mark.asyncio


async def test_risk_evaluate_persists_and_replays_idempotently() -> None:
    agent_id = uuid4()
    merchant_id = uuid4()
    idempotency_key = f"integration-{uuid4()}"

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Integration Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Integration Merchant", category="electronics"))
        session.add(
            AgentPolicy(
                id=uuid4(),
                agent_id=agent_id,
                version=1,
                is_active=True,
                rules={
                    "transaction_limit": "10000.00",
                    "daily_limit": "50000.00",
                    "verification_threshold": "0.25",
                    "allowed_categories": ["electronics"],
                },
            )
        )
        await session.commit()

    payload = {
        "agent_id": str(agent_id),
        "merchant_id": str(merchant_id),
        "amount": "125.00",
        "currency": "INR",
        "device_id": "integration-device",
        "category": "electronics",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "idempotency_key": idempotency_key,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        first = await client.post("/api/v1/risk/evaluate", json=payload)
        assert first.status_code == 200
        first_body = first.json()
        assert first_body["decision"] in {"ALLOW", "VERIFY", "BLOCK"}
        assert first_body["external_payment_created"] is False

        second = await client.post("/api/v1/risk/evaluate", json=payload)
        assert second.status_code == 200
        assert second.json() == first_body

        conflicting = {**payload, "amount": "126.00"}
        conflict = await client.post("/api/v1/risk/evaluate", json=conflicting)
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

        detail = await client.get(f"/api/v1/risk/transactions/{first_body['transaction_id']}")
        assert detail.status_code == 200
        assert detail.json()["transaction"]["transaction_id"] == first_body["transaction_id"]
        assert detail.json()["decision_record"]["model_version"] == first_body["model_version"]

        metrics = await client.get("/api/v1/risk/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["evaluations"] >= 1

    async with SessionLocal() as session:
        transaction = await session.get(Transaction, first_body["transaction_id"])
        assert transaction is not None
        assert transaction.amount == Decimal("125.00")
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.commit()
