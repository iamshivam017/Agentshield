from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.db import get_session
from agentshield_api.models import AuditEvent, ModelVersion
from agentshield_api.security import ROLE_ADMIN, authorize_operator

router = APIRouter(prefix="/api/v1/models", tags=["models"])

_ALLOWED: dict[str, frozenset[str]] = {
    "TRAINED": frozenset({"EVALUATED"}),
    "EVALUATED": frozenset({"CANDIDATE"}),
    "CANDIDATE": frozenset({"APPROVED"}),
    "APPROVED": frozenset({"ACTIVE"}),
    "ACTIVE": frozenset({"RETIRED"}),
    "RETIRED": frozenset(),
}


def _validate_transition(current: str, target: str) -> None:
    if target not in _ALLOWED.get(current, frozenset()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"invalid_model_transition:{current}->{target}")


async def _transition(version: str, target: str, *, operator_id: str | None, session: AsyncSession) -> ModelVersion:
    model = await session.scalar(select(ModelVersion).where(ModelVersion.version == version).with_for_update())
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model_not_found")

    _validate_transition(model.status, target)

    if target == "ACTIVE":
        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('model-active', 0))"))
        await session.execute(
            update(ModelVersion)
            .where(ModelVersion.status == "ACTIVE", ModelVersion.version != version)
            .values(status="RETIRED")
        )

    previous = model.status
    model.status = target
    session.add(
        AuditEvent(
            id=uuid4(), transaction_id=None, event_type="MODEL_STATUS_CHANGED", actor_type="OPERATOR", actor_id=operator_id,
            payload={"model_version": model.version, "from": previous, "to": target, "artifact_sha256": model.artifact_sha256},
        )
    )
    await session.commit()
    await session.refresh(model)
    return model


async def _authorized_transition(
    version: str,
    target: str,
    x_operator_api_key: str | None,
    x_operator_id: str | None,
    session: AsyncSession,
) -> ModelVersion:
    operator_id = authorize_operator(x_operator_api_key, x_operator_id, {ROLE_ADMIN})
    return await _transition(version, target, operator_id=operator_id, session=session)


@router.post("/{version}/candidate", response_model=dict[str, object])
async def candidate_model(
    version: str,
    x_operator_api_key: str | None = Header(default=None),
    x_operator_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    model = await _authorized_transition(version, "CANDIDATE", x_operator_api_key, x_operator_id, session)
    return {"version": model.version, "status": model.status}


@router.post("/{version}/approve", response_model=dict[str, object])
async def approve_model(
    version: str,
    x_operator_api_key: str | None = Header(default=None),
    x_operator_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    model = await _authorized_transition(version, "APPROVED", x_operator_api_key, x_operator_id, session)
    return {"version": model.version, "status": model.status}


@router.post("/{version}/activate", response_model=dict[str, object])
async def activate_model(
    version: str,
    x_operator_api_key: str | None = Header(default=None),
    x_operator_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    model = await _authorized_transition(version, "ACTIVE", x_operator_api_key, x_operator_id, session)
    return {"version": model.version, "status": model.status}


@router.post("/{version}/retire", response_model=dict[str, object])
async def retire_model(
    version: str,
    x_operator_api_key: str | None = Header(default=None),
    x_operator_id: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    model = await _authorized_transition(version, "RETIRED", x_operator_api_key, x_operator_id, session)
    return {"version": model.version, "status": model.status}


def register_model_routes(app) -> None:
    app.include_router(router)
