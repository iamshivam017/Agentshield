from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from agentshield_ml.evaluate import calibration_metrics, evaluate_threshold, select_threshold
from agentshield_ml.features import FEATURE_VERSION, build_features
from agentshield_ml.synthetic import SyntheticConfig, generate_transactions

DATASET_VERSION = "synthetic-v1"
SEED = 42
ROWS = 50_000
FALSE_POSITIVE_COST = 1.0
FALSE_NEGATIVE_COST = 5.0


def chronological_split(n: int, train_ratio: float = 0.70, validation_ratio: float = 0.15) -> tuple[slice, slice, slice]:
    if n < 100:
        raise ValueError("dataset is too small for a reliable chronological split")
    train_end = int(n * train_ratio)
    validation_end = train_end + int(n * validation_ratio)
    return slice(0, train_end), slice(train_end, validation_end), slice(validation_end, n)


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_metrics(y_true: np.ndarray, probabilities: np.ndarray, threshold: float) -> dict:
    chosen = evaluate_threshold(
        y_true,
        probabilities,
        threshold,
        false_positive_cost=FALSE_POSITIVE_COST,
        false_negative_cost=FALSE_NEGATIVE_COST,
    )
    return {
        "threshold": asdict(chosen),
        "calibration": calibration_metrics(y_true, probabilities),
    }


def train(output_dir: str = "artifacts/risk", rows: int = ROWS, seed: int = SEED) -> dict:
    if rows < 100:
        raise ValueError("rows must be at least 100")
    transactions = generate_transactions(SyntheticConfig(rows=rows, seed=seed))
    x, y = build_features(transactions)
    train_slice, validation_slice, test_slice = chronological_split(len(x))
    x_train, y_train = x.iloc[train_slice], y.iloc[train_slice]
    x_validation, y_validation = x.iloc[validation_slice], y.iloc[validation_slice]
    x_test, y_test = x.iloc[test_slice], y.iloc[test_slice]

    logistic = Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=seed)),
    ])
    logistic.fit(x_train, y_train)
    logistic_validation = logistic.predict_proba(x_validation)[:, 1]
    logistic_threshold = select_threshold(
        y_validation.to_numpy(),
        logistic_validation,
        false_positive_cost=FALSE_POSITIVE_COST,
        false_negative_cost=FALSE_NEGATIVE_COST,
    )
    logistic_test = logistic.predict_proba(x_test)[:, 1]

    positive = max(int(y_train.sum()), 1)
    negative = max(int((1 - y_train).sum()), 1)
    xgb = XGBClassifier(
        n_estimators=180,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=negative / positive,
        random_state=seed,
        n_jobs=2,
    )
    xgb.fit(x_train, y_train)
    xgb_validation = xgb.predict_proba(x_validation)[:, 1]
    xgb_threshold = select_threshold(
        y_validation.to_numpy(),
        xgb_validation,
        false_positive_cost=FALSE_POSITIVE_COST,
        false_negative_cost=FALSE_NEGATIVE_COST,
    )
    xgb_test = xgb.predict_proba(x_test)[:, 1]

    candidates = {
        "logistic": {
            "model": logistic,
            "validation": model_metrics(y_validation.to_numpy(), logistic_validation, logistic_threshold.threshold),
            "test": model_metrics(y_test.to_numpy(), logistic_test, logistic_threshold.threshold),
            "validation_cost": logistic_threshold.false_positive_cost + logistic_threshold.false_negative_cost,
        },
        "xgboost": {
            "model": xgb,
            "validation": model_metrics(y_validation.to_numpy(), xgb_validation, xgb_threshold.threshold),
            "test": model_metrics(y_test.to_numpy(), xgb_test, xgb_threshold.threshold),
            "validation_cost": xgb_threshold.false_positive_cost + xgb_threshold.false_negative_cost,
        },
    }

    selected_name = min(
        candidates,
        key=lambda name: (
            candidates[name]["validation_cost"],
            -candidates[name]["validation"]["threshold"]["f1"],
            -candidates[name]["validation"]["threshold"]["precision"],
        ),
    )
    selected_model = candidates[selected_name]["model"]
    selected_version = "xgboost-v1" if selected_name == "xgboost" else "baseline-logistic-v1"

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    artifact_path = destination / "model.joblib"
    joblib.dump(selected_model, artifact_path)
    checksum = artifact_sha256(artifact_path)

    test_metrics = candidates[selected_name]["test"]["threshold"]
    metadata = {
        "model_version": selected_version,
        "selected_candidate": selected_name,
        "dataset_version": DATASET_VERSION,
        "feature_version": FEATURE_VERSION,
        "seed": seed,
        "rows": len(transactions),
        "split": {
            "train": train_slice.stop - train_slice.start,
            "validation": validation_slice.stop - validation_slice.start,
            "test": test_slice.stop - test_slice.start,
        },
        "costs": {
            "false_positive": FALSE_POSITIVE_COST,
            "false_negative": FALSE_NEGATIVE_COST,
        },
        "candidates": {
            name: {
                "validation": value["validation"],
                "test": value["test"],
                "validation_total_cost": value["validation_cost"],
            }
            for name, value in candidates.items()
        },
        "frozen_test_metrics": {
            "precision": test_metrics["precision"],
            "recall": test_metrics["recall"],
            "f1": test_metrics["f1"],
            "pr_auc": test_metrics["pr_auc"],
            "roc_auc": test_metrics["roc_auc"],
            "tn": test_metrics["tn"],
            "fp": test_metrics["fp"],
            "fn": test_metrics["fn"],
            "tp": test_metrics["tp"],
            "false_positive_cost": test_metrics["false_positive_cost"],
            "false_negative_cost": test_metrics["false_negative_cost"],
        },
        "threshold": test_metrics["threshold"],
        "calibration": candidates[selected_name]["test"]["calibration"],
        "artifact_sha256": checksum,
        "artifact_path": str(artifact_path),
        "status": "EVALUATED",
        "note": "Threshold was selected on chronological validation data; frozen test data is used only for final reporting.",
    }
    (destination / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate AgentShield risk models.")
    parser.add_argument("--rows", type=int, default=ROWS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--output-dir", default="artifacts/risk")
    args = parser.parse_args()
    print(json.dumps(train(output_dir=args.output_dir, rows=args.rows, seed=args.seed), indent=2))


if __name__ == "__main__":
    main()
