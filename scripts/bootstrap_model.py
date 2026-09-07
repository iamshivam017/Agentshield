from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen


REQUIRED_METADATA = {
    "model_version",
    "selected_candidate",
    "dataset_version",
    "feature_version",
    "artifact_sha256",
    "status",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=30) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)


def main() -> None:
    artifact_url = os.getenv("RISK_MODEL_ARTIFACT_URL", "").strip()
    metadata_url = os.getenv("RISK_MODEL_METADATA_URL", "").strip()
    artifact_path = Path(os.getenv("RISK_MODEL_ARTIFACT_PATH", "/tmp/agentshield-model/model.joblib"))
    metadata_path = Path(os.getenv("RISK_MODEL_METADATA_PATH", "/tmp/agentshield-model/metadata.json"))
    expected_sha = os.getenv("RISK_MODEL_ARTIFACT_SHA256", "").strip().lower()
    expected_version = os.getenv("RISK_MODEL_VERSION", "").strip()

    if not artifact_url and not metadata_url:
        if artifact_path.is_file() and metadata_path.is_file():
            return
        if os.getenv("APP_ENV", "development").lower() in {"production", "staging"}:
            raise SystemExit("risk model artifact is not configured")
        return

    if not artifact_url or not metadata_url or not expected_sha or not expected_version:
        raise SystemExit("RISK_MODEL_ARTIFACT_URL, RISK_MODEL_METADATA_URL, RISK_MODEL_ARTIFACT_SHA256, and RISK_MODEL_VERSION are required together")

    download(artifact_url, artifact_path)
    download(metadata_url, metadata_path)

    actual_sha = sha256(artifact_path).lower()
    if actual_sha != expected_sha:
        raise SystemExit("downloaded risk model SHA-256 does not match configured checksum")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    missing = REQUIRED_METADATA.difference(metadata)
    if missing:
        raise SystemExit(f"model metadata missing required fields: {sorted(missing)}")
    if str(metadata["artifact_sha256"]).lower() != actual_sha:
        raise SystemExit("model metadata SHA-256 does not match downloaded artifact")
    if str(metadata["model_version"]) != expected_version:
        raise SystemExit("model metadata version does not match configured version")
    if metadata["feature_version"] != "v1":
        raise SystemExit(f"unsupported model feature version: {metadata['feature_version']!r}")
    if metadata["status"] not in {"APPROVED", "ACTIVE"}:
        raise SystemExit(f"model artifact must be APPROVED or ACTIVE for deployed serving, got {metadata['status']!r}")


if __name__ == "__main__":
    main()
