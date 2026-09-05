from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Transaction

FEATURE_VERSION = "v1"
FEATURE_NAMES = (
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
)


async def build_point_in_time_features(
    session: AsyncSession,
    *,
    agent_id: UUID,
    merchant_id: UUID,
    device_id: str,
    occurred_at: datetime,
    amount: Decimal,
) -> dict[str, float]:
    """Build serving features using only transactions strictly before the event."""
    occurred_at = occurred_at.astimezone(timezone.utc)
    prior_filter = Transaction.occurred_at < occurred_at

    agent_count = int(
        await session.scalar(
            select(func.count(Transaction.id)).where(prior_filter, Transaction.agent_id == agent_id)
        )
        or 0
    )
    device_count = int(
        await session.scalar(
            select(func.count(Transaction.id)).where(prior_filter, Transaction.device_id == device_id)
        )
        or 0
    )
    merchant_count = int(
        await session.scalar(
            select(func.count(Transaction.id)).where(prior_filter, Transaction.merchant_id == merchant_id)
        )
        or 0
    )
    agent_mean = await session.scalar(
        select(func.avg(Transaction.amount)).where(prior_filter, Transaction.agent_id == agent_id)
    )
    device_exists = device_count > 0
    merchant_exists = merchant_count > 0

    window_start = occurred_at - timedelta(hours=1)
    agent_1h = int(
        await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.agent_id == agent_id,
                Transaction.occurred_at >= window_start,
                Transaction.occurred_at < occurred_at,
            )
        )
        or 0
    )

    hour = float(occurred_at.hour)
    amount_float = float(amount)
    return {
        "amount": amount_float,
        "hour": hour,
        "is_weekend": float(occurred_at.weekday() >= 5),
        "new_device": float(not device_exists),
        "new_merchant": float(not merchant_exists),
        "auth_mismatch": 0.0,
        "burst": float(agent_1h >= 3),
        "agent_tx_count_prior": float(agent_count),
        "user_tx_count_prior": 0.0,
        "device_tx_count_prior": float(device_count),
        "merchant_tx_count_prior": float(merchant_count),
        "agent_amount_mean_prior": 0.0 if agent_mean is None else float(agent_mean),
        "user_amount_mean_prior": 0.0,
        "agent_count_1h_prior": float(agent_1h),
    }
