from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    merchant_id: UUID
    amount: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    device_id: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    occurred_at: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=200)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone information")
        return value


class RiskEvaluateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    decision: str
    risk_score: Decimal
    risk_band: str
    model_version: str
    policy_version: int
    reason_codes: list[str]
    external_payment_created: bool
