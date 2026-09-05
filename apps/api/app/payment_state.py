from __future__ import annotations

from enum import StrEnum


class PaymentState(StrEnum):
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_UNKNOWN = "PAYMENT_UNKNOWN"


_ALLOWED_TRANSITIONS: dict[PaymentState, frozenset[PaymentState]] = {
    PaymentState.ORDER_CREATED: frozenset({PaymentState.PAYMENT_PENDING, PaymentState.PAYMENT_AUTHORIZED, PaymentState.PAYMENT_CAPTURED, PaymentState.PAYMENT_FAILED, PaymentState.PAYMENT_UNKNOWN}),
    PaymentState.PAYMENT_PENDING: frozenset({PaymentState.PAYMENT_AUTHORIZED, PaymentState.PAYMENT_CAPTURED, PaymentState.PAYMENT_FAILED, PaymentState.PAYMENT_UNKNOWN}),
    PaymentState.PAYMENT_AUTHORIZED: frozenset({PaymentState.PAYMENT_CAPTURED, PaymentState.PAYMENT_FAILED, PaymentState.PAYMENT_UNKNOWN}),
    PaymentState.PAYMENT_CAPTURED: frozenset({PaymentState.PAYMENT_CAPTURED}),
    PaymentState.PAYMENT_FAILED: frozenset({PaymentState.PAYMENT_FAILED, PaymentState.PAYMENT_UNKNOWN, PaymentState.PAYMENT_CAPTURED}),
    PaymentState.PAYMENT_UNKNOWN: frozenset({
        PaymentState.PAYMENT_UNKNOWN,
        PaymentState.PAYMENT_PENDING,
        PaymentState.PAYMENT_AUTHORIZED,
        PaymentState.PAYMENT_CAPTURED,
        PaymentState.PAYMENT_FAILED,
    }),
}

_STATE_RANK: dict[PaymentState, int] = {
    PaymentState.PAYMENT_UNKNOWN: 0,
    PaymentState.ORDER_CREATED: 1,
    PaymentState.PAYMENT_PENDING: 2,
    PaymentState.PAYMENT_AUTHORIZED: 3,
    PaymentState.PAYMENT_FAILED: 4,
    PaymentState.PAYMENT_CAPTURED: 5,
}


def can_transition(current: str, target: str) -> bool:
    try:
        current_state = PaymentState(current)
        target_state = PaymentState(target)
    except ValueError:
        return False
    return target_state in _ALLOWED_TRANSITIONS[current_state]


def transition_state(current: str, target: str) -> str:
    """Validate a provider/payment state transition and return its canonical value."""
    if not can_transition(current, target):
        raise ValueError(f"invalid_payment_transition:{current}->{target}")
    return PaymentState(target).value


def monotonic_state_update(current: str, incoming: str) -> str:
    """Apply the strongest observed state without allowing stale events to regress it."""
    try:
        current_state = PaymentState(current)
        incoming_state = PaymentState(incoming)
    except ValueError as exc:
        raise ValueError(f"invalid_payment_state:{current}->{incoming}") from exc
    if _STATE_RANK[incoming_state] < _STATE_RANK[current_state]:
        return current_state.value
    return transition_state(current_state.value, incoming_state.value)


def razorpay_event_state(event_type: str | None) -> PaymentState:
    return {
        "payment.authorized": PaymentState.PAYMENT_AUTHORIZED,
        "payment.captured": PaymentState.PAYMENT_CAPTURED,
        "payment.failed": PaymentState.PAYMENT_FAILED,
        "payment.pending": PaymentState.PAYMENT_PENDING,
    }.get(str(event_type), PaymentState.PAYMENT_UNKNOWN)
