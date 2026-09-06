from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

import httpx

from agentshield_api.observability import telemetry
from app.payment_state import PaymentState


class PaymentProviderError(RuntimeError):
    """Raised when the payment provider cannot safely complete an operation."""


@dataclass(frozen=True)
class OrderResult:
    provider: str
    order_id: str
    amount_minor: int
    currency: str
    state: str


@dataclass(frozen=True)
class ReconciliationResult:
    provider: str
    order_id: str
    state: str
    provider_payment_id: str | None = None
    payment_state: str | None = None


class PaymentProvider(Protocol):
    async def create_order(self, *, amount: Decimal, currency: str, receipt: str) -> OrderResult:
        """Create an external order without claiming that payment completed."""

    async def reconcile_order(self, *, order_id: str) -> ReconciliationResult:
        """Read provider state and return the authoritative state observed now."""

    async def find_order_by_receipt(self, *, receipt: str) -> OrderResult | None:
        """Find an existing order created for a unique internal receipt."""


def amount_to_minor(amount: Decimal, *, currency: str) -> int:
    """Convert a decimal amount to provider subunits without float arithmetic."""
    decimals = {"BHD": 3, "KWD": 3, "OMR": 3}.get(currency.upper(), 2)
    quantum = Decimal(1).scaleb(-decimals)
    normalized = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return int(normalized * (10**decimals))


def _state_from_provider_status(status_value: str) -> str:
    return {
        "created": PaymentState.ORDER_CREATED.value,
        "attempted": PaymentState.PAYMENT_PENDING.value,
        "paid": PaymentState.PAYMENT_CAPTURED.value,
    }.get(status_value.lower(), PaymentState.PAYMENT_UNKNOWN.value)


@dataclass
class MockPaymentProvider:
    """Deterministic provider for integration tests and local failure-path testing."""

    provider: str = "mock"
    order_prefix: str = "order_mock_"
    calls: int = 0
    fail: bool = False
    reconciled_state: str = PaymentState.PAYMENT_PENDING.value
    orders: dict[str, OrderResult] = field(default_factory=dict)

    async def create_order(self, *, amount: Decimal, currency: str, receipt: str) -> OrderResult:
        if self.fail:
            raise PaymentProviderError("mock_provider_failure")
        self.calls += 1
        currency = currency.upper()
        minor = amount_to_minor(amount, currency=currency)
        if minor <= 0:
            raise PaymentProviderError("Provider amount must be positive")
        result = OrderResult(
            provider=self.provider,
            order_id=f"{self.order_prefix}{self.calls}",
            amount_minor=minor,
            currency=currency,
            state=PaymentState.ORDER_CREATED.value,
        )
        self.orders[receipt] = result
        return result

    async def find_order_by_receipt(self, *, receipt: str) -> OrderResult | None:
        if self.fail:
            raise PaymentProviderError("mock_provider_failure")
        return self.orders.get(receipt)

    async def reconcile_order(self, *, order_id: str) -> ReconciliationResult:
        if self.fail:
            raise PaymentProviderError("mock_provider_failure")
        if not order_id:
            raise PaymentProviderError("provider_order_id_required")
        return ReconciliationResult(
            provider=self.provider,
            order_id=order_id,
            state=self.reconciled_state,
            provider_payment_id=f"pay_mock_{order_id.removeprefix(self.order_prefix)}"
            if self.reconciled_state != PaymentState.ORDER_CREATED.value
            else None,
            payment_state=self.reconciled_state
            if self.reconciled_state != PaymentState.ORDER_CREATED.value
            else None,
        )


class RazorpayTestProvider:
    """Server-side Razorpay Orders API adapter restricted to Test Mode keys."""

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(self, *, key_id: str, key_secret: str, timeout_seconds: float = 5.0) -> None:
        if not key_id or not key_secret:
            raise PaymentProviderError("Razorpay Test Mode credentials are not configured")
        if not key_id.startswith("rzp_test_"):
            raise PaymentProviderError("Refusing non-Test-Mode Razorpay credentials")
        self._key_id = key_id
        self._key_secret = key_secret
        self._timeout = timeout_seconds

    def _result_from_payload(self, data: dict) -> OrderResult:
        order_id = data.get("id")
        receipt = data.get("receipt")
        currency = str(data.get("currency", "")).upper()
        amount_minor = data.get("amount")
        if not isinstance(order_id, str) or not order_id:
            raise PaymentProviderError("Razorpay returned an invalid order id")
        if not isinstance(receipt, str) or not receipt:
            raise PaymentProviderError("Razorpay returned an invalid order receipt")
        if not isinstance(amount_minor, int) or amount_minor <= 0:
            raise PaymentProviderError("Razorpay returned an invalid order amount")
        if not currency:
            raise PaymentProviderError("Razorpay returned an invalid order currency")
        return OrderResult(
            provider="razorpay",
            order_id=order_id,
            amount_minor=amount_minor,
            currency=currency,
            state=_state_from_provider_status(str(data.get("status", ""))),
        )

    async def create_order(self, *, amount: Decimal, currency: str, receipt: str) -> OrderResult:
        currency = currency.upper()
        minor = amount_to_minor(amount, currency=currency)
        if minor <= 0:
            raise PaymentProviderError("Provider amount must be positive")

        payload = {"amount": minor, "currency": currency, "receipt": receipt[:40]}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}/orders",
                    json=payload,
                    auth=(self._key_id, self._key_secret),
                    headers={"Content-Type": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise PaymentProviderError("Razorpay request failed") from exc

        if response.status_code >= 400:
            raise PaymentProviderError(f"Razorpay order creation failed with HTTP {response.status_code}")
        return self._result_from_payload(response.json())

    async def find_order_by_receipt(self, *, receipt: str) -> OrderResult | None:
        if not receipt:
            raise PaymentProviderError("order_receipt_required")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    f"{self.BASE_URL}/orders",
                    params={"receipt": receipt, "count": 100},
                    auth=(self._key_id, self._key_secret),
                )
        except httpx.HTTPError as exc:
            raise PaymentProviderError("Razorpay order recovery request failed") from exc

        if response.status_code >= 400:
            raise PaymentProviderError(f"Razorpay order recovery failed with HTTP {response.status_code}")

        data = response.json()
        items = data.get("items", [])
        if not isinstance(items, list):
            raise PaymentProviderError("Razorpay returned an invalid order collection")
        matching = [item for item in items if isinstance(item, dict) and item.get("receipt") == receipt]
        if not matching:
            return None
        if len(matching) > 1:
            raise PaymentProviderError("multiple_provider_orders_for_receipt")
        return self._result_from_payload(matching[0])

    async def reconcile_order(self, *, order_id: str) -> ReconciliationResult:
        if not order_id:
            raise PaymentProviderError("provider_order_id_required")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self.BASE_URL}/orders/{order_id}", auth=(self._key_id, self._key_secret))
        except httpx.HTTPError as exc:
            raise PaymentProviderError("Razorpay reconciliation request failed") from exc

        if response.status_code >= 400:
            raise PaymentProviderError(f"Razorpay reconciliation failed with HTTP {response.status_code}")

        data = response.json()
        return ReconciliationResult(provider="razorpay", order_id=order_id, state=_state_from_provider_status(str(data.get("status", ""))))


def verify_webhook_signature(*, raw_body: bytes, received_signature: str, secret: str) -> bool:
    """Validate Razorpay HMAC-SHA256 against the untouched request body."""
    if not secret or not received_signature:
        telemetry.increment("payment_webhook_events_total", provider="razorpay", event_type="invalid_signature", state="REJECTED")
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    valid = hmac.compare_digest(expected, received_signature)
    if not valid:
        telemetry.increment("payment_webhook_events_total", provider="razorpay", event_type="invalid_signature", state="REJECTED")
    return valid
