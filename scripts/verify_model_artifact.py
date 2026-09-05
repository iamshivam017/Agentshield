from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np

API_FEATURE_NAMES = [
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
]

REQUIRED_METADATA = {
    "model_version",
    "selected_candidate",
    "dataset_version",
    "feature_version",
    "seed",
    "rows",
    "split",
    "candidates",
    "frozen_test_metrics",
    "threshold",
    "calibration",
    "artifact_sha256",
    "status",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(output_dir: Path) -> dict[str, Any]:
    artifact = output_dir / "model.joblib"
    metadata_path = output_dir / "metadata.json"
    if not artifact.is_file() or not metadata_path.is_file():
        raise SystemExit("model.joblib and metadata.json are both required")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    missing = REQUIRED_METADATA.difference(metadata)
    if missing:
        raise SystemExit(f"metadata missing required fields: {sorted(missing)}")
    if metadata["status"] != "EVALUATED":
        raise SystemExit(f"model status must be EVALUATED, got {metadata['status']!r}")
    if metadata["feature_version"] != "v1":
        raise SystemExit(f"unsupported feature_version: {metadata['feature_version']!r}")
    if metadata["selected_candidate"] not in {"logistic", "xgboost"}:
        raise SystemExit("selected_candidate must be logistic or xgboost")
    if metadata["rows"] < 100:
        raise SystemExit("trained model must contain at least 100 rows")

    actual_sha = sha256(artifact)
    expected_sha = str(metadata["artifact_sha256"])
    if actual_sha.lower() != expected_sha.lower():
        raise SystemExit("artifact SHA-256 does not match metadata")

    try:
        model = joblib.load(artifact)
    except Exception as exc:  # noqa: BLE001 - verification CLI should report a stable failure
        raise SystemExit(f"unable to deserialize model artifact: {exc}") from exc
    if not hasattr(model, "predict_proba"):
        raise SystemExit("model artifact must expose predict_proba")

    sample = np.zeros((1, len(API_FEATURE_NAMES)), dtype=float)
    probabilities = np.asarray(model.predict_proba(sample), dtype=float)
    if probabilities.shape != (1, 2):
        raise SystemExit(f"unexpected predict_proba shape: {probabilities.shape}")
    if not 0.0 <= float(probabilities[0, 1]) <= 1.0:
        raise SystemExit("model probability is outside [0, 1]")

    test_metrics = metadata["frozen_test_metrics"]
    for field in ("precision", "recall", "f1", "pr_auc", "roc_auc", "fp", "fn"):
        if field not in test_metrics:
            raise SystemExit(f"frozen_test_metrics missing {field!r}")

    return {
        "model_version": metadata["model_version"],
        "candidate": metadata["selected_candidate"],
        "feature_version": metadata["feature_version"],
        "artifact_sha256": actual_sha,
        "rows": metadata["rows"],
        "smoke_probability": float(probabilities[0, 1]),
        "status": metadata["status"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify an AgentShield risk model artifact and metadata contract.")
    parser.add_argument("artifact_dir", type=Path, help="directory containing model.joblib and metadata.json")
    args = parser.parse_args()
    print(json.dumps(verify(args.artifact_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
