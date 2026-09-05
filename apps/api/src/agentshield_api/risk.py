from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class RiskBand(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    VERIFY = "VERIFY"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class RiskAssessment:
    score: Decimal
    band: RiskBand
    model_version: str
    signals: list[str]


@dataclass(frozen=True)
class PolicyContext:
    agent_active: bool
    amount: Decimal
    transaction_limit: Decimal
    daily_spent: Decimal
    daily_limit: Decimal
    verification_threshold: Decimal
    category_allowed: bool


@dataclass(frozen=True)
class PolicyResult:
    version: int
    violations: list[str]

    @property
    def hard_violation(self) -> bool:
        return bool(self.violations)


def classify_score(score: Decimal) -> RiskBand:
    if score < Decimal("0.30"):
        return RiskBand.LOW
    if score < Decimal("0.70"):
        return RiskBand.MEDIUM
    return RiskBand.HIGH


def evaluate_policy(context: PolicyContext, version: int) -> PolicyResult:
    violations: list[str] = []
    if not context.agent_active:
        violations.append("AGENT_INACTIVE")
    if context.amount > context.transaction_limit:
        violations.append("TRANSACTION_LIMIT_EXCEEDED")
    if context.daily_spent + context.amount > context.daily_limit:
        violations.append("DAILY_LIMIT_EXCEEDED")
    if not context.category_allowed:
        violations.append("CATEGORY_RESTRICTED")
    return PolicyResult(version=version, violations=violations)


def decide(assessment: RiskAssessment, policy: PolicyResult, verification_threshold: Decimal) -> Decision:
    if policy.hard_violation:
        return Decision.BLOCK
    if assessment.band is RiskBand.HIGH:
        return Decision.BLOCK
    if assessment.band is RiskBand.MEDIUM:
        return Decision.VERIFY
    if assessment.score >= verification_threshold:
        return Decision.VERIFY
    return Decision.ALLOW
