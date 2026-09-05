from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticConfig:
    rows: int = 50_000
    seed: int = 42
    start: datetime = datetime(2026, 1, 1, tzinfo=timezone.utc)


def generate_transactions(config: SyntheticConfig = SyntheticConfig()) -> pd.DataFrame:
    """Generate a reproducible, defense-only synthetic transaction stream.

    Labels are generated from latent behavioral conditions and are never used as
    direct input features. The generator includes legitimate hard negatives so
    the resulting evaluation is not trivially separable.
    """
    if config.rows < 100:
        raise ValueError("rows must be at least 100")

    rng = np.random.default_rng(config.seed)
    n = config.rows

    agent = rng.integers(1, max(2, n // 100), size=n)
    user = rng.integers(1, max(2, n // 20), size=n)
    merchant = rng.integers(1, max(2, n // 50), size=n)
    device = rng.integers(1, max(2, n // 80), size=n)

    archetype = rng.choice(
        ["conservative", "regular", "high_value", "night_owl", "seasonal"],
        size=n,
        p=[0.20, 0.45, 0.12, 0.10, 0.13],
    )

    amount_scale = np.select(
        [archetype == "conservative", archetype == "high_value"],
        [700.0, 8000.0],
        default=2200.0,
    )
    amount = np.maximum(1.0, rng.lognormal(np.log(amount_scale), 0.7))

    hours = rng.integers(0, 24, size=n)
    weekend = rng.integers(0, 7, size=n) >= 5
    occurred_at = np.array(
        [config.start + timedelta(minutes=15 * int(i)) for i in range(n)],
        dtype="datetime64[ns]",
    )

    new_device = rng.random(n) < 0.07
    new_merchant = rng.random(n) < 0.09
    auth_mismatch = rng.random(n) < 0.035
    burst = rng.random(n) < 0.045

    # Latent anomaly process: suspicious combinations are intentionally rarer
    # than any single condition and legitimate hard negatives remain present.
    latent = (
        1.2 * new_device.astype(float)
        + 0.9 * new_merchant.astype(float)
        + 1.3 * auth_mismatch.astype(float)
        + 1.1 * burst.astype(float)
        + 0.75 * (amount > np.quantile(amount, 0.92)).astype(float)
        + 0.55 * ((hours < 5) & (archetype != "night_owl")).astype(float)
    )
    probability = 1 / (1 + np.exp(-(latent - 3.0)))
    is_anomalous = rng.random(n) < probability

    # Create legitimate hard negatives: high-value, weekend, night-owl, and
    # occasional new-device events may be valid and should not always flag.
    hard_negative = (~is_anomalous) & (
        (archetype == "high_value")
        | (archetype == "night_owl")
        | (weekend & (amount > np.quantile(amount, 0.80)))
    )

    frame = pd.DataFrame(
        {
            "transaction_id": np.arange(1, n + 1, dtype=np.int64),
            "agent_id": agent,
            "user_id": user,
            "merchant_id": merchant,
            "device_id": device,
            "occurred_at": occurred_at,
            "amount": amount.round(2),
            "currency": "INR",
            "hour": hours,
            "is_weekend": weekend,
            "archetype": archetype,
            "new_device": new_device,
            "new_merchant": new_merchant,
            "auth_mismatch": auth_mismatch,
            "burst": burst,
            "hard_negative": hard_negative,
            "is_anomalous": is_anomalous.astype(np.int8),
        }
    )
    return frame


if __name__ == "__main__":
    data = generate_transactions()
    data.to_parquet("data/synthetic_transactions.parquet", index=False)
    print(data["is_anomalous"].value_counts(normalize=True).rename("rate"))
