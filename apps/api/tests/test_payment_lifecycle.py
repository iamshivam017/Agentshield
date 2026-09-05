from __future__ import annotations

from decimal import Decimal

import pytest

from app.payment_state import PaymentState, can_transition, monotonic_state_update, razorpay_event_state, transition_state
from app.razorpay import MockPaymentProvider, PaymentProviderError, amount_to_minor


@pytest.mark.asyncio
async def test_mock_provider_is_deterministic_and_provider_agnostic() -> None:
    provider = MockPaymentProvider()
    first = await provider.create_order(amount=Decimal("123.45"), currency="inr", receipt="tx-1")
    second = await provider.create_order(amount=Decimal("123.45"), currency="inr", receipt="tx-2")

    assert first.provider == "mock"
    assert first.order_id == "order_mock_1"
    assert second.order_id == "order_mock_2"
    assert first.amount_minor == 12345
    assert first.state == PaymentState.ORDER_CREATED.value


@pytest.mark.asyncio
async def test_mock_provider_failure_is_explicit() -> None:
    provider = MockPaymentProvider(fail=True)
    with pytest.raises(PaymentProviderError, match="mock_provider_failure"):
        await provider.create_order(amount=Decimal("10.00"), currency="INR", receipt="tx-1")


def test_payment_state_machine_allows_forward_progress() -> None:
    assert can_transition("ORDER_CREATED", "PAYMENT_PENDING")
    assert can_transition("PAYMENT_PENDING", "PAYMENT_AUTHORIZED")
    assert can_transition("PAYMENT_AUTHORIZED", "PAYMENT_CAPTURED")
    assert transition_state("PAYMENT_PENDING", "PAYMENT_CAPTURED") == "PAYMENT_CAPTURED"
    assert not can_transition("PAYMENT_CAPTURED", "PAYMENT_AUTHORIZED")


def test_terminal_capture_cannot_regress_on_out_of_order_webhook() -> None:
    assert monotonic_state_update("PAYMENT_CAPTURED", "PAYMENT_AUTHORIZED") == "PAYMENT_CAPTURED"
    assert monotonic_state_update("PAYMENT_CAPTURED", "PAYMENT_FAILED") == "PAYMENT_CAPTURED"
    assert monotonic_state_update("PAYMENT_AUTHORIZED", "PAYMENT_CAPTURED") == "PAYMENT_CAPTURED"


def test_unknown_and_event_mapping_are_explicit() -> None:
    assert razorpay_event_state("payment.authorized") == PaymentState.PAYMENT_AUTHORIZED
    assert razorpay_event_state("payment.captured") == PaymentState.PAYMENT_CAPTURED
    assert razorpay_event_state("payment.failed") == PaymentState.PAYMENT_FAILED
    assert razorpay_event_state("unrecognized.event") == PaymentState.PAYMENT_UNKNOWN


def test_currency_subunit_conversion_remains_decimal_safe() -> None:
    assert amount_to_minor(Decimal("10.12"), currency="INR") == 1012
    assert amount_to_minor(Decimal("1.234"), currency="KWD") == 1234
