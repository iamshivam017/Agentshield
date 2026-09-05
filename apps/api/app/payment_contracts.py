from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaymentOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=200)


class PaymentOrderResponse(BaseModel):
    transaction_id: UUID
    decision: str
    provider: str
    provider_order_id: str
    amount: Decimal
    currency: str
    state: str
    test_mode: bool
