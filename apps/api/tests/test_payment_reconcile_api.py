from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from agentshield_api.config import settings
from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, Merchant, PaymentOrder, ProviderPayment, Transaction
from app.main import app

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_mock_payment_reconciliation_updates_state_and_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "require_operator_auth", True)
    monkeypatch.setattr(settings, "operator_api_key", "operator-test-key")
    agent_id = uuid4()
    merchant_id = uuid4()
    transaction_id = uuid4()
    payment_order_id = uuid4()
    provider_order_id = "order_mock_1"

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Reconcile Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Reconcile Merchant", category="SOFTWARE"))
        session.add(
            Transaction(
                id=transaction_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                amount=Decimal("50.00"),
                currency="INR",
                device_id="reconcile-device",
                occurred_at="2026-09-05T10:00:00+00:00",
                status="EVALUATED",
            )
        )
        await session.flush()
        session.add(
            PaymentOrder(
                id=payment_order_id,
                transaction_id=transaction_id,
                provider="mock",
                provider_order_id=provider_order_id,
                state="ORDER_CREATED",
                amount_minor=5000,
                currency="INR",
            )
        )
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            f"/api/v1/payments/orders/{transaction_id}/reconcile",
            headers={
                "X-Operator-API-Key": "operator-test-key",
                "X-Operator-ID": "risk-analyst",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "PAYMENT_CAPTURED"
        assert body["changed"] is True

    async with SessionLocal() as session:
        order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        payment = await session.scalar(select(ProviderPayment).where(ProviderPayment.payment_order_id == payment_order_id))
        transaction = await session.scalar(select(Transaction).where(Transaction.id == transaction_id))
        assert order is not None
        assert payment is not None
        assert transaction is not None
        assert order.state == "PAYMENT_CAPTURED"
        assert payment.state == "PAYMENT_CAPTURED"
        assert transaction.status == "PAYMENT_CAPTURED"

        await session.execute(delete(ProviderPayment).where(ProviderPayment.payment_order_id == payment_order_id))
        await session.execute(delete(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        await session.execute(delete(Transaction).where(Transaction.id == transaction_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
