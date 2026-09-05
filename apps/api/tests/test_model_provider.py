from __future__ import annotations

import hashlib

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from agentshield_api import model_provider as model_provider_module
from agentshield_api.model_provider import ModelUnavailable, VerifiedArtifactModel

FEATURE_COUNT = 14


def build_artifact(path) -> tuple[str, str]:
    x = np.array([[0.0] * FEATURE_COUNT, [10_000.0] + [0.0] * (FEATURE_COUNT - 1)])
    y = np.array([0, 1])
    model = LogisticRegression().fit(x, y)
    joblib.dump(model, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest, "test-logistic-v1"


def test_verified_artifact_requires_matching_checksum(tmp_path) -> None:
    artifact = tmp_path / "model.joblib"
    digest, version = build_artifact(artifact)

    model = VerifiedArtifactModel(path=str(artifact), expected_sha256=digest, version=version)
    score, signals = model.predict(amount=10_000, category="software")

    assert 0 <= score <= 1
    assert model.version == version
    assert "MODEL_ARTIFACT_VERIFIED" in signals


def test_verified_artifact_rejects_tampering(tmp_path) -> None:
    artifact = tmp_path / "model.joblib"
    digest, _ = build_artifact(artifact)
    artifact.write_bytes(artifact.read_bytes() + b"tampered")

    with pytest.raises(ModelUnavailable, match="checksum mismatch"):
        VerifiedArtifactModel(path=str(artifact), expected_sha256=digest, version="test-logistic-v1")


def test_production_provider_requires_configured_artifact(monkeypatch) -> None:
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_path", None)
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_sha256", None)
    provider = model_provider_module.ModelProvider(environment="production")

    with pytest.raises(ModelUnavailable, match="verified APPROVED/ACTIVE"):
        provider.get_active()
