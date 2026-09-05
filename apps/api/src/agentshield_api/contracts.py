from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class PolicyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    rules: dict[str, Any]

    @model_validator(mode="after")
    def validate_and_normalize_rules(self) -> "PolicyCreateRequest":
        allowed_keys = {"transaction_limit", "daily_limit", "verification_threshold", "allowed_categories"}
        unknown = set(self.rules) - allowed_keys
        if unknown:
            raise ValueError(f"unknown_policy_rule:{','.join(sorted(unknown))}")

        normalized: dict[str, Any] = {}
        for key in ("transaction_limit", "daily_limit", "verification_threshold"):
            if key not in self.rules:
                raise ValueError(f"missing_policy_rule:{key}")
            try:
                value = Decimal(str(self.rules[key]))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValueError(f"invalid_policy_rule:{key}") from exc
            if not value.is_finite() or value <= Decimal("0"):
                raise ValueError(f"invalid_policy_rule:{key}")
            exponent = value.as_tuple().exponent
            if key != "verification_threshold" and isinstance(exponent, int) and exponent < -2:
                raise ValueError(f"invalid_policy_rule:{key}")
            if key == "verification_threshold" and value > Decimal("1"):
                raise ValueError(f"invalid_policy_rule:{key}")
            normalized[key] = str(value.quantize(Decimal("0.01") if key != "verification_threshold" else Decimal("0.000001")))

        transaction_limit = Decimal(normalized["transaction_limit"])
        daily_limit = Decimal(normalized["daily_limit"])
        if daily_limit < transaction_limit:
            raise ValueError("daily_limit_must_cover_transaction_limit")

        raw_categories = self.rules.get("allowed_categories", [])
        if raw_categories is None:
            categories: list[object] = []
        elif not isinstance(raw_categories, list) or len(raw_categories) > 100:
            raise ValueError("invalid_allowed_categories")
        else:
            categories = raw_categories

        normalized_categories: list[str] = []
        for category in categories:
            if not isinstance(category, str):
                raise ValueError("invalid_allowed_categories")
            cleaned = category.strip()
            if not 1 <= len(cleaned) <= 80:
                raise ValueError("invalid_allowed_categories")
            normalized_categories.append(cleaned.upper())
        normalized["allowed_categories"] = list(dict.fromkeys(normalized_categories))
        self.rules = normalized
        return self


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
