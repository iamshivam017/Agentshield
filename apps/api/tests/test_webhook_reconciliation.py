from __future__ import annotations

import hashlib
import hmac
import json
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
async def test_stale_webhook_cannot_regress_captured_payment(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "webhook-test-secret"
    monkeypatch.setattr(settings, "razorpay_webhook_secret", secret)
    agent_id = uuid4()
    merchant_id = uuid4()
    transaction_id = uuid4()
    payment_order_id = uuid4()
    provider_payment_id = f"pay_{uuid4().hex}"
    provider_order_id = f"order_{uuid4().hex}"

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Webhook Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Webhook Merchant", category="SOFTWARE"))
        session.add(
            Transaction(
                id=transaction_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                amount=Decimal("25.00"),
                currency="INR",
                device_id="webhook-device",
                occurred_at="2026-09-05T10:00:00+00:00",
                status="PAYMENT_CAPTURED",
            )
        )
        session.add(
            PaymentOrder(
                id=payment_order_id,
                transaction_id=transaction_id,
                provider="mock",
                provider_order_id=provider_order_id,
                state="PAYMENT_CAPTURED",
                amount_minor=2500,
                currency="INR",
            )
        )
        session.add(
            ProviderPayment(
                id=uuid4(),
                provider_payment_id=provider_payment_id,
                payment_order_id=payment_order_id,
                state="PAYMENT_CAPTURED",
                raw_event={"event": "payment.captured"},
            )
        )
        await session.commit()

    payload = {
        "event": "payment.authorized",
        "payload": {
            "payment": {
                "entity": {
                    "id": provider_payment_id,
                    "order_id": provider_order_id,
                }
            }
        },
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/integrations/razorpay/webhook",
            content=raw_body,
            headers={
                "X-Razorpay-Signature": signature,
                "x-razorpay-event-id": f"evt_{uuid4().hex}",
            },
        )
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"

    async with SessionLocal() as session:
        order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        payment = await session.scalar(
            select(ProviderPayment).where(ProviderPayment.provider_payment_id == provider_payment_id)
        )
        assert order is not None
        assert payment is not None
        assert order.state == "PAYMENT_CAPTURED"
        assert payment.state == "PAYMENT_CAPTURED"

        await session.execute(delete(ProviderPayment).where(ProviderPayment.provider_payment_id == provider_payment_id))
        await session.execute(delete(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        await session.execute(delete(Transaction).where(Transaction.id == transaction_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
