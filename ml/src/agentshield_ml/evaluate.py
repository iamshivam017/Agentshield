from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score


@dataclass(frozen=True)
class ThresholdMetrics:
    threshold: float
    precision: float
    recall: float
    f1: float
    pr_auc: float
    roc_auc: float
    tn: int
    fp: int
    fn: int
    tp: int
    false_positive_cost: float
    false_negative_cost: float


def evaluate_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    *,
    false_positive_cost: float = 1.0,
    false_negative_cost: float = 5.0,
) -> ThresholdMetrics:
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between 0 and 1")
    predicted = probabilities >= threshold
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return ThresholdMetrics(
        threshold=threshold,
        precision=precision_score(y_true, predicted, zero_division=0),
        recall=recall_score(y_true, predicted, zero_division=0),
        f1=f1_score(y_true, predicted, zero_division=0),
        pr_auc=average_precision_score(y_true, probabilities),
        roc_auc=roc_auc_score(y_true, probabilities),
        tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp),
        false_positive_cost=float(fp * false_positive_cost),
        false_negative_cost=float(fn * false_negative_cost),
    )


def calibration_metrics(y_true: np.ndarray, probabilities: np.ndarray, *, bins: int = 10) -> dict[str, float]:
    """Measure probability calibration without using labels to choose a threshold."""
    if probabilities.size == 0:
        raise ValueError("probabilities must not be empty")
    clipped = np.clip(probabilities, 0.0, 1.0)
    brier = brier_score_loss(y_true, clipped)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (clipped >= left) & (clipped < right if right < 1.0 else clipped <= right)
        if not np.any(mask):
            continue
        confidence = float(np.mean(clipped[mask]))
        accuracy = float(np.mean(y_true[mask]))
        ece += float(np.mean(mask)) * abs(confidence - accuracy)
    return {"brier_score": float(brier), "expected_calibration_error": float(ece), "bins": float(bins)}


def select_threshold(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    *,
    min_precision: float = 0.80,
    min_recall: float = 0.60,
    false_positive_cost: float = 1.0,
    false_negative_cost: float = 5.0,
) -> ThresholdMetrics:
    """Select a validation threshold by cost subject to quality floors."""
    candidates = np.unique(np.clip(probabilities, 0.01, 0.99))
    scored = [
        evaluate_threshold(
            y_true,
            probabilities,
            float(t),
            false_positive_cost=false_positive_cost,
            false_negative_cost=false_negative_cost,
        )
        for t in candidates
    ]
    feasible = [
        item
        for item in scored
        if item.precision >= min_precision and item.recall >= min_recall
    ]
    pool = feasible or scored
    return min(
        pool,
        key=lambda item: (
            item.false_positive_cost + item.false_negative_cost,
            -item.f1,
            -item.precision,
        ),
    )
