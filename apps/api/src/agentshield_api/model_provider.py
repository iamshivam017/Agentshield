from __future__ import annotations

from decimal import Decimal
from typing import Protocol


class ModelUnavailable(RuntimeError):
    """Raised when no approved risk model is available for serving."""


class RiskModel(Protocol):
    version: str

    def predict(self, *, amount: Decimal, category: str) -> tuple[Decimal, list[str]]:
        ...


class DevelopmentHeuristicModel:
    """Explicit development-only scorer until a trained artifact is activated."""

    version = "dev-heuristic-0"

    def predict(self, *, amount: Decimal, category: str) -> tuple[Decimal, list[str]]:
        score = min(Decimal("0.95"), amount / Decimal("10000"))
        signals: list[str] = []
        if amount >= Decimal("5000"):
            signals.append("AMOUNT_ELEVATED")
        if category.lower() in {"crypto", "gambling"}:
            score = min(Decimal("0.95"), score + Decimal("0.20"))
            signals.append("CATEGORY_ELEVATED")
        return score.quantize(Decimal("0.000001")), signals


class ModelProvider:
    def __init__(self, *, environment: str) -> None:
        self.environment = environment
        self._development_model = DevelopmentHeuristicModel()

    def get_active(self) -> RiskModel:
        if self.environment in {"development", "test"}:
            return self._development_model
        raise ModelUnavailable("No APPROVED/ACTIVE risk model artifact is configured")
