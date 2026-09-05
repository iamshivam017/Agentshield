from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, Merchant, PaymentOrder, ProviderPayment, Transaction

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_database_keeps_captured_payment_terminal() -> None:
    agent_id = uuid4()
    merchant_id = uuid4()
    transaction_id = uuid4()
    payment_order_id = uuid4()
    provider_payment_id = uuid4()

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Payment State Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Payment State Merchant", category="SOFTWARE"))
        session.add(
            Transaction(
                id=transaction_id,
                agent_id=agent_id,
                merchant_id=merchant_id,
                amount=Decimal("25.00"),
                currency="INR",
                device_id="payment-state-device",
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
                provider_order_id=f"order_{uuid4().hex}",
                state="ORDER_CREATED",
                amount_minor=2500,
                currency="INR",
            )
        )
        session.add(
            ProviderPayment(
                id=provider_payment_id,
                provider_payment_id=f"pay_{uuid4().hex}",
                payment_order_id=payment_order_id,
                state="PAYMENT_CAPTURED",
                raw_event={"event": "payment.captured"},
            )
        )
        await session.commit()

        payment_order = await session.get(PaymentOrder, payment_order_id)
        assert payment_order is not None
        payment_order.state = "PAYMENT_CAPTURED"
        await session.commit()

        payment_order.state = "PAYMENT_AUTHORIZED"
        await session.commit()

        provider_payment = await session.get(ProviderPayment, provider_payment_id)
        assert provider_payment is not None
        provider_payment.state = "PAYMENT_AUTHORIZED"
        await session.commit()

        refreshed_order = await session.scalar(select(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        refreshed_payment = await session.scalar(select(ProviderPayment).where(ProviderPayment.id == provider_payment_id))
        assert refreshed_order is not None
        assert refreshed_payment is not None
        assert refreshed_order.state == "PAYMENT_CAPTURED"
        assert refreshed_payment.state == "PAYMENT_CAPTURED"

        await session.execute(delete(ProviderPayment).where(ProviderPayment.id == provider_payment_id))
        await session.execute(delete(PaymentOrder).where(PaymentOrder.id == payment_order_id))
        await session.execute(delete(Transaction).where(Transaction.id == transaction_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
