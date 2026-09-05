from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import joblib
import numpy as np
import pytest
from fastapi import HTTPException
from sklearn.linear_model import LogisticRegression

from agentshield_api import model_provider as model_provider_module
from agentshield_api.models import ModelVersion
from app.model_routes import _validate_transition, _verify_active_serving_contract


FEATURE_COUNT = 14


def build_artifact(path: Path) -> str:
    x = np.array([[0.0] * FEATURE_COUNT, [10_000.0] + [0.0] * (FEATURE_COUNT - 1)])
    y = np.array([0, 1])
    model = LogisticRegression().fit(x, y)
    joblib.dump(model, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_model_lifecycle_requires_approved_sequence() -> None:
    _validate_transition("TRAINED", "EVALUATED")
    _validate_transition("EVALUATED", "CANDIDATE")
    _validate_transition("CANDIDATE", "APPROVED")
    _validate_transition("APPROVED", "ACTIVE")
    _validate_transition("ACTIVE", "RETIRED")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("TRAINED", "ACTIVE"),
        ("EVALUATED", "APPROVED"),
        ("CANDIDATE", "ACTIVE"),
        ("APPROVED", "RETIRED"),
        ("RETIRED", "ACTIVE"),
        ("ACTIVE", "APPROVED"),
    ],
)
def test_model_lifecycle_rejects_skipped_or_regressive_transitions(current: str, target: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_transition(current, target)
    assert exc_info.value.status_code == 409


def test_active_model_requires_exact_serving_artifact(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "model.joblib"
    digest = build_artifact(artifact)
    model = ModelVersion(
        id=uuid4(),
        version="test-model-v1",
        status="APPROVED",
        artifact_sha256=digest,
        metrics={},
        training_config={},
    )

    monkeypatch.setattr(model_provider_module.settings, "app_env", "production")
    monkeypatch.setattr(model_provider_module.settings, "risk_model_version", model.version)
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_sha256", digest)
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_path", str(artifact))

    _verify_active_serving_contract(model)

    artifact.write_bytes(artifact.read_bytes() + b"tampered")
    with pytest.raises(HTTPException, match="serving_model_artifact_tampered"):
        _verify_active_serving_contract(model)


def test_active_model_rejects_version_or_checksum_mismatch(monkeypatch, tmp_path: Path) -> None:
    artifact = tmp_path / "model.joblib"
    digest = build_artifact(artifact)
    model = ModelVersion(
        id=uuid4(),
        version="test-model-v2",
        status="APPROVED",
        artifact_sha256=digest,
        metrics={},
        training_config={},
    )

    monkeypatch.setattr(model_provider_module.settings, "app_env", "staging")
    monkeypatch.setattr(model_provider_module.settings, "risk_model_version", "different-model")
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_sha256", digest)
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_path", str(artifact))
    with pytest.raises(HTTPException, match="serving_model_version_mismatch"):
        _verify_active_serving_contract(model)

    monkeypatch.setattr(model_provider_module.settings, "risk_model_version", model.version)
    monkeypatch.setattr(model_provider_module.settings, "risk_model_artifact_sha256", "0" * 64)
    with pytest.raises(HTTPException, match="serving_model_checksum_mismatch"):
        _verify_active_serving_contract(model)
