from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from agentshield_api.database import AsyncSessionLocal
from agentshield_api.models import EvaluationRun, ModelVersion


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def register(artifact_dir: Path) -> str:
    metadata_path = artifact_dir / "metadata.json"
    artifact_path = artifact_dir / "model.joblib"
    if not metadata_path.is_file() or not artifact_path.is_file():
        raise SystemExit("model.joblib and metadata.json are required")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = str(metadata["model_version"])
    expected_hash = str(metadata["artifact_sha256"])
    actual_hash = sha256(artifact_path)
    if actual_hash != expected_hash:
        raise SystemExit(f"artifact checksum mismatch: expected {expected_hash}, got {actual_hash}")

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(ModelVersion).where(ModelVersion.version == version))
        if existing is not None:
            if existing.artifact_sha256 != expected_hash:
                raise SystemExit(f"model version {version} already exists with a different artifact checksum")
            return f"{version}:already-registered:{existing.status}"

        frozen = metadata.get("frozen_test_metrics", {})
        model = ModelVersion(
            id=uuid4(),
            version=version,
            status="TRAINED",
            artifact_sha256=expected_hash,
            metrics={
                "frozen_test_metrics": frozen,
                "calibration": metadata.get("calibration", {}),
                "threshold": metadata.get("threshold"),
                "candidates": metadata.get("candidates", {}),
            },
            training_config={
                "dataset_version": metadata.get("dataset_version"),
                "feature_version": metadata.get("feature_version"),
                "seed": metadata.get("seed"),
                "rows": metadata.get("rows"),
                "split": metadata.get("split"),
                "costs": metadata.get("costs"),
                "artifact_path": str(artifact_path),
            },
        )
        evaluation = EvaluationRun(
            id=uuid4(),
            model_version=version,
            dataset_version=str(metadata.get("dataset_version", "unknown")),
            metrics=metadata.get("frozen_test_metrics", {}),
            threshold=metadata.get("threshold", 0),
            seed=int(metadata.get("seed", 0)),
        )
        session.add_all([model, evaluation])
        await session.commit()
        return f"{version}:registered:TRAINED"


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a verified AgentShield model artifact.")
    parser.add_argument("artifact_dir", type=Path)
    args = parser.parse_args()
    print(asyncio.run(register(args.artifact_dir)))


if __name__ == "__main__":
    main()
