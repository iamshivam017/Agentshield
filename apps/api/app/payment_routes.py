from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.config import settings
from agentshield_api.db import get_session
from agentshield_api.models import AuditEvent, PaymentOrder, ProviderPayment, Transaction
from agentshield_api.observability import telemetry
from app.payment_state import monotonic_state_update
from app.razorpay import MockPaymentProvider, PaymentProviderError, RazorpayTestProvider

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def _provider_for(order: PaymentOrder):
    if order.provider == "mock":
        return MockPaymentProvider(reconciled_state="PAYMENT_CAPTURED")
    if order.provider == "razorpay":
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise HTTPException(status_code=503, detail="razorpay_test_mode_not_configured")
        return RazorpayTestProvider(key_id=settings.razorpay_key_id, key_secret=settings.razorpay_key_secret)
    raise HTTPException(status_code=503, detail="payment_provider_not_supported")


@router.post("/orders/{transaction_id}/reconcile")
async def reconcile_payment_order(transaction_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    order = await session.scalar(select(PaymentOrder).where(PaymentOrder.transaction_id == transaction_id))
    transaction = await session.scalar(select(Transaction).where(Transaction.id == transaction_id))
    if order is None or transaction is None:
        raise HTTPException(status_code=404, detail="payment_order_not_found")

    provider = _provider_for(order)
    try:
        observed = await provider.reconcile_order(order_id=order.provider_order_id)
    except PaymentProviderError as exc:
        telemetry.increment("payment_reconciliation_total", provider=order.provider, state="PROVIDER_ERROR")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    next_order_state = monotonic_state_update(order.state, observed.state)
    changed = next_order_state != order.state
    order.state = next_order_state

    if observed.provider_payment_id:
        provider_payment = await session.scalar(
            select(ProviderPayment).where(ProviderPayment.provider_payment_id == observed.provider_payment_id)
        )
        if provider_payment is None:
            provider_payment = ProviderPayment(
                id=uuid4(),
                provider_payment_id=observed.provider_payment_id,
                payment_order_id=order.id,
                state=observed.payment_state or observed.state,
                raw_event={"source": "reconciliation", "order_id": order.provider_order_id},
            )
            session.add(provider_payment)
        else:
            provider_payment.payment_order_id = order.id
            provider_payment.state = monotonic_state_update(
                provider_payment.state,
                observed.payment_state or observed.state,
            )
    elif observed.payment_state:
        provider_payment = await session.scalar(
            select(ProviderPayment)
            .where(ProviderPayment.payment_order_id == order.id)
            .order_by(ProviderPayment.created_at.desc())
        )
        if provider_payment is not None:
            provider_payment.state = monotonic_state_update(provider_payment.state, observed.payment_state)

    if order.state == "PAYMENT_CAPTURED" and transaction.status != "PAYMENT_CAPTURED":
        transaction.status = "PAYMENT_CAPTURED"
        changed = True

    telemetry.increment("payment_reconciliation_total", provider=observed.provider, state=order.state)
    session.add(
        AuditEvent(
            id=uuid4(),
            transaction_id=transaction_id,
            event_type="PAYMENT_RECONCILED",
            actor_type="SYSTEM",
            actor_id=None,
            payload={
                "provider": observed.provider,
                "provider_order_id": observed.order_id,
                "observed_state": observed.state,
                "effective_state": order.state,
                "changed": changed,
            },
        )
    )
    await session.commit()
    return {
        "status": "reconciled",
        "transaction_id": transaction_id,
        "provider": observed.provider,
        "provider_order_id": observed.order_id,
        "state": order.state,
        "changed": changed,
    }
