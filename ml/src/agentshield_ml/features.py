from __future__ import annotations

import pandas as pd

FEATURE_VERSION = "v1"


def build_features(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Build point-in-time-safe features.

    Rolling counts/amounts are shifted so the current transaction cannot leak
    into its own historical aggregates. The target is returned separately.
    """
    required = {
        "agent_id",
        "user_id",
        "merchant_id",
        "device_id",
        "occurred_at",
        "amount",
        "hour",
        "is_weekend",
        "new_device",
        "new_merchant",
        "auth_mismatch",
        "burst",
        "is_anomalous",
    }
    missing = required.difference(transactions.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    frame = transactions.sort_values("occurred_at").reset_index(drop=True).copy()
    frame["occurred_at"] = pd.to_datetime(frame["occurred_at"], utc=True)

    grouped_agent = frame.groupby("agent_id", sort=False)
    grouped_user = frame.groupby("user_id", sort=False)
    grouped_device = frame.groupby("device_id", sort=False)
    grouped_merchant = frame.groupby("merchant_id", sort=False)

    frame["agent_tx_count_prior"] = grouped_agent.cumcount()
    frame["user_tx_count_prior"] = grouped_user.cumcount()
    frame["device_tx_count_prior"] = grouped_device.cumcount()
    frame["merchant_tx_count_prior"] = grouped_merchant.cumcount()

    prior_amount = frame["amount"]
    frame["agent_amount_mean_prior"] = (
        grouped_agent["amount"].transform(lambda s: s.shift(1).expanding().mean())
    ).fillna(0.0)
    frame["user_amount_mean_prior"] = (
        grouped_user["amount"].transform(lambda s: s.shift(1).expanding().mean())
    ).fillna(0.0)

    # Short-window velocity uses only rows strictly before the current event.
    timed = frame.set_index("occurred_at")
    frame["agent_count_1h_prior"] = (
        timed.groupby("agent_id")["amount"]
        .rolling("1h", closed="left")
        .count()
        .reset_index(level=0, drop=True)
        .fillna(0)
        .to_numpy()
    )

    feature_cols = [
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
    features = frame[feature_cols].astype(float)
    target = frame["is_anomalous"].astype(int)

    # Defensive assertion: current target is never part of feature columns.
    assert "is_anomalous" not in features.columns
    assert "hard_negative" not in features.columns
    return features, target
