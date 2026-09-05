from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .contracts import PolicyCreateRequest, PolicyItem
from .db import get_session
from .models import Agent, AgentPolicy, AuditEvent
from .security import ROLE_ADMIN, authorize_operator, install_control_plane_security

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


def _lock_key(agent_id: str) -> int:
    value = int(hashlib.sha256(f"policy-version:{agent_id}".encode()).hexdigest()[:16], 16)
    return value - (1 << 63)


@router.post("", response_model=PolicyItem, status_code=status.HTTP_201_CREATED)
async def create_policy(
    request: PolicyCreateRequest,
    x_operator_api_key: str | None = Header(default=None),
    x_operator_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> PolicyItem:
    operator_id = authorize_operator(x_operator_api_key, x_operator_id, {ROLE_ADMIN})
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _lock_key(str(request.agent_id))})

    agent = await session.scalar(select(Agent).where(Agent.id == request.agent_id))
    if agent is None:
        raise HTTPException(status_code=404, detail="agent_not_found")

    latest = await session.scalar(
        select(AgentPolicy)
        .where(AgentPolicy.agent_id == request.agent_id)
        .order_by(AgentPolicy.version.desc())
    )
    next_version = 1 if latest is None else latest.version + 1

    if latest is not None and latest.is_active:
        await session.execute(
            update(AgentPolicy)
            .where(AgentPolicy.id == latest.id)
            .values(is_active=False)
        )

    policy = AgentPolicy(
        id=uuid4(),
        agent_id=request.agent_id,
        version=next_version,
        is_active=True,
        rules=request.rules,
    )
    session.add(policy)
    rules_hash = hashlib.sha256(
        json.dumps(request.rules, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    session.add(
        AuditEvent(
            id=uuid4(),
            transaction_id=None,
            event_type="POLICY_VERSION_CREATED",
            actor_type="OPERATOR",
            actor_id=operator_id,
            payload={
                "agent_id": str(request.agent_id),
                "version": next_version,
                "rules_hash": rules_hash,
            },
        )
    )
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    await session.refresh(policy)
    return PolicyItem(
        id=policy.id,
        agent_id=policy.agent_id,
        version=policy.version,
        is_active=policy.is_active,
        rules=policy.rules,
        created_at=policy.created_at,
    )


def register_policy_routes(app) -> None:
    app.include_router(router)
    from app.payment_routes import router as payment_router
    from app.investigation_routes import router as investigation_router
    from agentshield_api.observability import install_observability
    app.include_router(payment_router)
    app.include_router(investigation_router)
    install_control_plane_security(app)
    install_observability(app)
