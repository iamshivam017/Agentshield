from __future__ import annotations

import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

import pytest

from agentshield_api.model_provider import VerifiedArtifactModel


def test_ci_trained_artifact_is_servable_and_matches_metadata() -> None:
    artifact_path = os.getenv("RISK_MODEL_ARTIFACT_PATH")
    metadata_path = os.getenv("RISK_MODEL_METADATA_PATH")
    expected_sha = os.getenv("RISK_MODEL_ARTIFACT_SHA256")
    version = os.getenv("RISK_MODEL_VERSION")

    if not all((artifact_path, metadata_path, expected_sha, version)):
        pytest.fail("CI trained model artifact contract variables are required for this test")

    artifact = Path(artifact_path)
    metadata_file = Path(metadata_path)
    assert artifact.is_file()
    assert metadata_file.is_file()

    actual_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["artifact_sha256"] == actual_sha
    assert metadata["artifact_sha256"] == expected_sha
    assert metadata["model_version"] == version
    assert metadata["feature_version"] == "v1"
    assert metadata["status"] == "EVALUATED"

    model = VerifiedArtifactModel(
        path=str(artifact),
        expected_sha256=expected_sha,
        version=version,
    )
    features = {
        "amount": 425.0,
        "hour": 12.0,
        "is_weekend": 0.0,
        "new_device": 0.0,
        "new_merchant": 0.0,
        "auth_mismatch": 0.0,
        "burst": 0.0,
        "agent_tx_count_prior": 10.0,
        "user_tx_count_prior": 6.0,
        "device_tx_count_prior": 4.0,
        "merchant_tx_count_prior": 3.0,
        "agent_amount_mean_prior": 390.0,
        "user_amount_mean_prior": 380.0,
        "agent_count_1h_prior": 1.0,
    }
    score, signals = model.predict(features=features, category="software")

    assert Decimal("0") <= score <= Decimal("1")
    assert "MODEL_ARTIFACT_VERIFIED" in signals
