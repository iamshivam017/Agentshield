from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import joblib  # type: ignore[import-untyped]
import numpy as np

from .config import settings
from .features import FEATURE_NAMES


class ModelUnavailable(RuntimeError):
    """Raised when no approved risk model is available for serving."""


class RiskModel(Protocol):
    version: str

    def predict(
        self,
        *,
        features: dict[str, float] | None = None,
        amount: Decimal | None = None,
        category: str,
    ) -> tuple[Decimal, list[str]]:
        ...


def _fallback_features(*, amount: Decimal | None) -> dict[str, float]:
    values = {name: 0.0 for name in FEATURE_NAMES}
    values["amount"] = float(amount or Decimal("0"))
    return values


class DevelopmentHeuristicModel:
    """Explicit development-only scorer until a verified artifact is activated."""

    version = "dev-heuristic-0"

    def predict(
        self,
        *,
        features: dict[str, float] | None = None,
        amount: Decimal | None = None,
        category: str,
    ) -> tuple[Decimal, list[str]]:
        values = features or _fallback_features(amount=amount)
        amount_value = Decimal(str(values["amount"]))
        score = min(Decimal("0.95"), amount_value / Decimal("10000"))
        signals: list[str] = []
        if amount_value >= Decimal("5000"):
            signals.append("AMOUNT_ELEVATED")
        if values["new_device"]:
            signals.append("NEW_DEVICE")
        if values["new_merchant"]:
            signals.append("NEW_MERCHANT")
        if values["burst"]:
            score = min(Decimal("0.95"), score + Decimal("0.15"))
            signals.append("VELOCITY_SPIKE")
        if category.lower() in {"crypto", "gambling"}:
            score = min(Decimal("0.95"), score + Decimal("0.20"))
            signals.append("CATEGORY_ELEVATED")
        return score.quantize(Decimal("0.000001")), signals


class VerifiedArtifactModel:
    """Loads a trusted joblib classifier only after checksum verification."""

    _feature_names = FEATURE_NAMES

    def __init__(self, *, path: str, expected_sha256: str, version: str) -> None:
        artifact = Path(path)
        if not artifact.is_file():
            raise ModelUnavailable("risk model artifact path does not exist")
        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual.lower() != expected_sha256.lower():
            raise ModelUnavailable("risk model artifact checksum mismatch")
        try:
            loaded: Any = joblib.load(artifact)
        except Exception as exc:  # noqa: BLE001 - convert deserialization failures to a serving error
            raise ModelUnavailable("risk model artifact could not be loaded") from exc
        if not hasattr(loaded, "predict_proba"):
            raise ModelUnavailable("risk model artifact does not expose predict_proba")
        self._model = loaded
        self.version = version
        self.artifact_sha256 = actual

    def predict(
        self,
        *,
        features: dict[str, float] | None = None,
        amount: Decimal | None = None,
        category: str,
    ) -> tuple[Decimal, list[str]]:
        values = features or _fallback_features(amount=amount)
        matrix = np.asarray([[values[name] for name in self._feature_names]], dtype=float)
        try:
            probability = float(self._model.predict_proba(matrix)[0][1])
        except Exception as exc:  # noqa: BLE001 - model implementation is provider-specific
            raise ModelUnavailable("risk model prediction failed") from exc
        score = Decimal(str(min(max(probability, 0.0), 1.0))).quantize(Decimal("0.000001"))
        signals = ["MODEL_ARTIFACT_VERIFIED"]
        if values["new_device"]:
            signals.append("NEW_DEVICE")
        if values["new_merchant"]:
            signals.append("NEW_MERCHANT")
        if values["burst"]:
            signals.append("VELOCITY_SPIKE")
        if category.lower() in {"crypto", "gambling"}:
            signals.append("CATEGORY_ELEVATED")
        return score, signals


class ModelProvider:
    def __init__(self, *, environment: str) -> None:
        self.environment = environment
        self._development_model = DevelopmentHeuristicModel()
        self._artifact_model: VerifiedArtifactModel | None = None

    def get_active(self) -> RiskModel:
        if self.environment in {"development", "test"}:
            return self._development_model
        if self._artifact_model is None:
            if not settings.risk_model_artifact_path or not settings.risk_model_artifact_sha256:
                raise ModelUnavailable("No verified APPROVED/ACTIVE risk model artifact is configured")
            self._artifact_model = VerifiedArtifactModel(
                path=settings.risk_model_artifact_path,
                expected_sha256=settings.risk_model_artifact_sha256,
                version=getattr(settings, "risk_model_version", "artifact-unversioned"),
            )
        return self._artifact_model
