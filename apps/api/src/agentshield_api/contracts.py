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


class RiskQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: UUID
    agent_id: UUID
    agent_name: str
    merchant_id: UUID
    merchant_name: str
    amount: Decimal
    currency: str
    status: str
    risk_score: Decimal
    risk_band: str
    decision: str
    model_version: str
    policy_version: int
    reason_codes: list[str]
    occurred_at: datetime


class RiskQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RiskQueueItem]
    total: int
    limit: int
    offset: int


class ReviewCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer_id: str = Field(min_length=1, max_length=160)
    outcome: str = Field(pattern="^(APPROVE|REJECT|ESCALATE)$")
    note: str | None = Field(default=None, max_length=4000)


class ReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    transaction_id: UUID
    reviewer_id: str
    outcome: str
    note: str | None
    created_at: datetime


class PolicyItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    agent_id: UUID
    version: int
    is_active: bool
    rules: dict
    created_at: datetime


class ModelItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    status: str
    artifact_sha256: str
    metrics: dict
    training_config: dict
    created_at: datetime


class AuditItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    transaction_id: UUID | None
    event_type: str
    actor_type: str
    actor_id: str | None
    payload: dict
    occurred_at: datetime


class RiskMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: int
    high_risk: int
    verification: int
    blocked: int
    allowed: int


class TransactionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction: RiskQueueItem
    features: dict | None
    prediction: dict | None
    policy_evaluation: dict | None
    decision_record: dict | None
    reviews: list[ReviewResponse]
    audit_events: list[AuditItem]
    investigation: dict | None
    payment_order: dict | None
    provider_payment: dict | None
