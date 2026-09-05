from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from fastapi import HTTPException

from agentshield_api.db import SessionLocal
from agentshield_api.models import Agent, AgentBudgetState, AgentPolicy, IdempotencyRecord, Merchant, Transaction
from app.main import app, reserve_agent_budget

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_concurrent_identical_evaluations_replay_one_decision() -> None:
    agent_id = uuid4()
    merchant_id = uuid4()
    key = f"concurrent-{uuid4()}"
    occurred_at = datetime.now(timezone.utc).isoformat()

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Concurrent Agent", status="ACTIVE"))
        session.add(Merchant(id=merchant_id, name="Concurrent Merchant", category="software"))
        session.add(
            AgentPolicy(
                id=uuid4(),
                agent_id=agent_id,
                version=1,
                is_active=True,
                rules={
                    "transaction_limit": "1000.00",
                    "daily_limit": "5000.00",
                    "verification_threshold": "0.25",
                    "allowed_categories": ["SOFTWARE"],
                },
            )
        )
        await session.commit()

    payload = {
        "agent_id": str(agent_id),
        "merchant_id": str(merchant_id),
        "amount": "125.00",
        "currency": "INR",
        "device_id": "concurrent-device",
        "category": "software",
        "occurred_at": occurred_at,
        "idempotency_key": key,
    }

    async def evaluate_once() -> dict:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.post("/api/v1/risk/evaluate", json=payload)
            assert response.status_code == 200
            return response.json()

    first, second = await asyncio.gather(evaluate_once(), evaluate_once())
    assert first == second

    async with SessionLocal() as session:
        transactions = (
            await session.scalars(
                select(Transaction).where(
                    Transaction.agent_id == agent_id,
                    Transaction.occurred_at == datetime.fromisoformat(occurred_at),
                )
            )
        ).all()
        claims = (
            await session.scalars(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.key == key,
                    IdempotencyRecord.scope == f"risk:evaluate:{agent_id}",
                )
            )
        ).all()
        assert len(transactions) == 1
        assert len(claims) == 1

        await session.execute(delete(Transaction).where(Transaction.agent_id == agent_id))
        await session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.key == key))
        await session.execute(delete(AgentPolicy).where(AgentPolicy.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.execute(delete(Merchant).where(Merchant.id == merchant_id))
        await session.commit()


@pytest.mark.asyncio
async def test_budget_row_lock_prevents_concurrent_overspend() -> None:
    agent_id = uuid4()
    period_key = "2026-09-05"

    async with SessionLocal() as session:
        session.add(Agent(id=agent_id, name="Budget Agent", status="ACTIVE"))
        await session.commit()

    async def reserve(amount: Decimal) -> str:
        async with SessionLocal() as session:
            try:
                await reserve_agent_budget(
                    session,
                    agent_id=agent_id,
                    amount=amount,
                    daily_limit=Decimal("100.00"),
                    period_key=period_key,
                )
                await session.commit()
                return "reserved"
            except HTTPException as exc:
                await session.rollback()
                assert exc.status_code == 409
                return "rejected"

    results = await asyncio.gather(reserve(Decimal("60.00")), reserve(Decimal("60.00")))
    assert sorted(results) == ["rejected", "reserved"]

    async with SessionLocal() as session:
        state = await session.scalar(
            select(AgentBudgetState).where(
                AgentBudgetState.agent_id == agent_id,
                AgentBudgetState.period_key == period_key,
            )
        )
        assert state is not None
        assert state.reserved <= Decimal("100.00")
        assert state.spent <= Decimal("100.00")
        await session.execute(delete(AgentBudgetState).where(AgentBudgetState.agent_id == agent_id))
        await session.execute(delete(Agent).where(Agent.id == agent_id))
        await session.commit()
