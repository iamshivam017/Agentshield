from __future__ import annotations

import numpy as np

from agentshield_ml.evaluate import calibration_metrics, evaluate_threshold, select_threshold
from agentshield_ml.features import build_features
from agentshield_ml.synthetic import SyntheticConfig, generate_transactions
from agentshield_ml.train import chronological_split


def test_generation_is_reproducible() -> None:
    a = generate_transactions(SyntheticConfig(rows=1_000, seed=7))
    b = generate_transactions(SyntheticConfig(rows=1_000, seed=7))
    assert a.equals(b)


def test_temporal_features_exclude_current_target() -> None:
    data = generate_transactions(SyntheticConfig(rows=500, seed=11))
    features, target = build_features(data)
    assert len(features) == len(target)
    assert "is_anomalous" not in features.columns
    assert "hard_negative" not in features.columns
    assert features["agent_tx_count_prior"].min() == 0


def test_chronological_split_has_frozen_tail() -> None:
    train, validation, test = chronological_split(1_000)
    assert train.stop == validation.start
    assert validation.stop == test.start
    assert train.start == 0
    assert test.stop == 1_000


def test_threshold_metrics_and_cost_selection() -> None:
    y_true = np.array([0, 0, 1, 1, 1])
    probabilities = np.array([0.05, 0.15, 0.55, 0.70, 0.95])
    metrics = evaluate_threshold(y_true, probabilities, 0.5)
    assert metrics.tp == 3
    assert metrics.fp == 0
    assert metrics.recall == 1.0

    chosen = select_threshold(y_true, probabilities, min_precision=0.8, min_recall=0.8)
    assert 0.0 < chosen.threshold < 1.0


def test_calibration_metrics_are_bounded() -> None:
    y_true = np.array([0, 0, 1, 1])
    probabilities = np.array([0.1, 0.2, 0.8, 0.9])
    metrics = calibration_metrics(y_true, probabilities, bins=4)
    assert 0.0 <= metrics["brier_score"] <= 1.0
    assert 0.0 <= metrics["expected_calibration_error"] <= 1.0
    assert metrics["bins"] == 4.0
