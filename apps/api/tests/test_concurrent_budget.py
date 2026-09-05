from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from agentshield_api.config import settings
from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, AgentBudgetState, AgentPolicy, Merchant, RiskDecision, Transaction
from app.main import app
from app.payment_contracts import PaymentOrderRequest
from app.razorpay import MockPaymentProvider

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_concurrent_payment_orders_do_not_exceed_daily_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_operator_auth", False)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "razorpay_key_id", "rzp_test_concurrency")
    monkeypatch.setattr(settings, "razorpay_key_secret", "test-secret")

    provider = MockPaymentProvider()

    class FakeRazorpayProvider:
        async def create_order(self, *, amount: Decimal, currency: str, receipt: str):
            return await provider.create_order(amount=amount, currency=currency, receipt=receipt)

    monkeypatch.setattr("app.main.RazorpayTestProvider", FakeRazorpayProvider)

    agent_id = uuid4()
    merchant_id = uuid4()
    transaction_ids = [uuid4() for _ in range(5)]

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Budget Concurrency Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Budget Merchant", category="SOFTWARE"))
        session.add(
            AgentPolicy(
                id=uuid4(),
                agent_id=agent_id,
                version=1,
                is_active=True,
                rules={
                    "transaction_limit": "50.00",
                    "daily_limit": "100.00",
                    "verification_threshold": "0.25",
                    "allowed_categories": ["SOFTWARE"],
                },
            )
        )
        for transaction_id in transaction_ids:
            session.add(
                Transaction(
                    id=transaction_id,
                    agent_id=agent_id,
                    merchant_id=merchant_id,
                    amount=Decimal("30.00"),
                    currency="INR",
                    device_id="concurrent-device",
                    occurred_at="2026-09-05T10:00:00+00:00",
                    status="EVALUATED",
                )
            )
            session.add(
                RiskDecision(
                    id=uuid4(),
                    transaction_id=transaction_id,
                    decision="ALLOW",
                    risk_score=Decimal("0.01"),
                    risk_band="LOW",
                    model_version="dev-heuristic-0",
                    policy_version=1,
                    reason_codes=[],
                )
            )
        await session.commit()

    async def place_order(transaction_id) -> int:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/payments/orders",
                json=PaymentOrderRequest(
                    transaction_id=transaction_id,
                    idempotency_key=f"budget-{transaction_id.hex}",
                ).model_dump(mode="json"),
            )
            return response.status_code

    statuses = await asyncio.gather(*(place_order(transaction_id) for transaction_id in transaction_ids))
    assert statuses.count(200) == 3
    assert statuses.count(409) == 2

    async with SessionLocal() as session:
        state = await session.scalar(
            select(AgentBudgetState).where(
                AgentBudgetState.agent_id == agent_id,
                AgentBudgetState.period_key == "2026-09-05",
            )
        )
        assert state is not None
        assert state.spent == Decimal("90.00")
        assert state.reserved == Decimal("0.00")

        await session.execute(delete(RiskDecision).where(RiskDecision.transaction_id.in_(transaction_ids)))
        await session.execute(delete(Transaction).where(Transaction.id.in_(transaction_ids)))
        await session.execute(delete(AgentPolicy).where(AgentPolicy.agent_id == agent_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
