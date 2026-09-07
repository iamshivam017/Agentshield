from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


BOOTSTRAP_PATH = Path(__file__).resolve().parents[4] / "scripts" / "bootstrap_model.py"
_SPEC = importlib.util.spec_from_file_location("agentshield_bootstrap_model", BOOTSTRAP_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load bootstrap helper from {BOOTSTRAP_PATH}")
_BOOTSTRAP_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BOOTSTRAP_MODULE)
main = _BOOTSTRAP_MODULE.main


def write_metadata(path: Path, *, sha: str, version: str = "baseline-logistic-v1", status: str = "ACTIVE") -> None:
    path.write_text(
        json.dumps(
            {
                "model_version": version,
                "selected_candidate": "logistic",
                "dataset_version": "synthetic-v1",
                "feature_version": "v1",
                "artifact_sha256": sha,
                "status": status,
            }
        ),
        encoding="utf-8",
    )


def test_development_without_model_configuration_is_allowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_PATH", str(tmp_path / "model.joblib"))
    monkeypatch.setenv("RISK_MODEL_METADATA_PATH", str(tmp_path / "metadata.json"))
    main()


def test_staging_requires_complete_model_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    for key in (
        "RISK_MODEL_ARTIFACT_URL",
        "RISK_MODEL_METADATA_URL",
        "RISK_MODEL_ARTIFACT_SHA256",
        "RISK_MODEL_VERSION",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit, match="risk model artifact is not configured"):
        main()


def test_downloaded_artifact_checksum_is_verified(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    artifact = tmp_path / "remote-model.joblib"
    metadata = tmp_path / "remote-metadata.json"
    artifact.write_bytes(b"verified-model")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()

    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_URL", artifact.as_uri())
    monkeypatch.setenv("RISK_MODEL_METADATA_URL", metadata.as_uri())
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_SHA256", digest)
    monkeypatch.setenv("RISK_MODEL_VERSION", "baseline-logistic-v1")
    monkeypatch.setenv("RISK_MODEL_ARTIFACT_PATH", str(tmp_path / "model.joblib"))
    monkeypatch.setenv("RISK_MODEL_METADATA_PATH", str(tmp_path / "metadata.json"))
    write_metadata(metadata, sha=digest)

    main()
    assert (tmp_path / "model.joblib").read_bytes() == b"verified-model"
