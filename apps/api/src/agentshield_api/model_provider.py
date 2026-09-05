from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import joblib
import numpy as np

from .config import settings


class ModelUnavailable(RuntimeError):
    """Raised when no approved risk model is available for serving."""


class RiskModel(Protocol):
    version: str

    def predict(self, *, amount: Decimal, category: str) -> tuple[Decimal, list[str]]:
        ...


class DevelopmentHeuristicModel:
    """Explicit development-only scorer until a verified artifact is activated."""

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


class VerifiedArtifactModel:
    """Loads a trusted joblib classifier only after checksum verification."""

    _feature_names = (
        "amount",
        "hour",
        "is_weekend",
        "new_device",
        "new_merchant",
        "auth_mismatch",
        "burst",
        "agent_tx_count_prior",
        "user_tx_count_prior",
        "device_tx_count_prior",
        "merchant_tx_count_prior",
        "agent_amount_mean_prior",
        "user_amount_mean_prior",
        "agent_count_1h_prior",
    )

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

    def predict(self, *, amount: Decimal, category: str) -> tuple[Decimal, list[str]]:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # Until the request contract carries richer identity/history attributes,
        # unknown historical dimensions are represented explicitly as zero rather
        # than silently using post-event information.
        values = {
            "amount": float(amount),
            "hour": float(now.hour),
            "is_weekend": float(now.weekday() >= 5),
            "new_device": 0.0,
            "new_merchant": 0.0,
            "auth_mismatch": 0.0,
            "burst": 0.0,
            "agent_tx_count_prior": 0.0,
            "user_tx_count_prior": 0.0,
            "device_tx_count_prior": 0.0,
            "merchant_tx_count_prior": 0.0,
            "agent_amount_mean_prior": 0.0,
            "user_amount_mean_prior": 0.0,
            "agent_count_1h_prior": 0.0,
        }
        matrix = np.asarray([[values[name] for name in self._feature_names]], dtype=float)
        try:
            probability = float(self._model.predict_proba(matrix)[0][1])
        except Exception as exc:  # noqa: BLE001 - model implementation is provider-specific
            raise ModelUnavailable("risk model prediction failed") from exc
        score = Decimal(str(min(max(probability, 0.0), 1.0))).quantize(Decimal("0.000001"))
        signals = ["MODEL_ARTIFACT_VERIFIED"]
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
                version=settings.risk_model_version,
            )
        return self._artifact_model
