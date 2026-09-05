from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from agentshield_ml.evaluate import select_threshold
from agentshield_ml.features import FEATURE_VERSION, build_features
from agentshield_ml.synthetic import SyntheticConfig, generate_transactions

MODEL_VERSION = "baseline-logistic-v1"
DATASET_VERSION = "synthetic-v1"
SEED = 42


def chronological_split(n: int, train_ratio: float = 0.70, validation_ratio: float = 0.15) -> tuple[slice, slice, slice]:
    if n < 100:
        raise ValueError("dataset is too small for a reliable chronological split")
    train_end = int(n * train_ratio)
    validation_end = train_end + int(n * validation_ratio)
    return slice(0, train_end), slice(train_end, validation_end), slice(validation_end, n)


def train(output_dir: str = "artifacts/baseline") -> dict:
    transactions = generate_transactions(SyntheticConfig(rows=50_000, seed=SEED))
    x, y = build_features(transactions)
    train_slice, validation_slice, test_slice = chronological_split(len(x))

    model = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=SEED)),
    ])
    model.fit(x.iloc[train_slice], y.iloc[train_slice])

    validation_prob = model.predict_proba(x.iloc[validation_slice])[:, 1]
    chosen = select_threshold(y.iloc[validation_slice].to_numpy(), validation_prob)

    test_prob = model.predict_proba(x.iloc[test_slice])[:, 1]
    test_pr_auc = average_precision_score(y.iloc[test_slice], test_prob)
    test_roc_auc = roc_auc_score(y.iloc[test_slice], test_prob)

    metadata = {
        "model_version": MODEL_VERSION,
        "dataset_version": DATASET_VERSION,
        "feature_version": FEATURE_VERSION,
        "seed": SEED,
        "rows": len(transactions),
        "split": {"train": train_slice.stop - train_slice.start, "validation": validation_slice.stop - validation_slice.start, "test": test_slice.stop - test_slice.start},
        "validation_selection": asdict(chosen),
        "frozen_test_metrics": {"pr_auc": float(test_pr_auc), "roc_auc": float(test_roc_auc)},
        "note": "Threshold selected on validation only; test set is frozen for final reporting.",
    }

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, destination / "model.joblib")
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    print(json.dumps(train(), indent=2))
