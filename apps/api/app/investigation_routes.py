from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.db import get_session
from agentshield_api.models import AuditEvent, Investigation, PolicyEvaluation, RiskDecision, RiskPrediction, Transaction, TransactionFeature
from agentshield_api.observability import telemetry
from app.investigation_service import ReadOnlyLLMProvider, build_evidence

router = APIRouter(prefix="/api/v1/risk/transactions", tags=["investigations"])


async def _load_case(transaction_id: UUID, session: AsyncSession):
    transaction = await session.scalar(select(Transaction).where(Transaction.id == transaction_id))
    decision = await session.scalar(select(RiskDecision).where(RiskDecision.transaction_id == transaction_id))
    if transaction is None or decision is None:
        raise HTTPException(status_code=404, detail="transaction_not_found")
    prediction = await session.scalar(select(RiskPrediction).where(RiskPrediction.transaction_id == transaction_id).order_by(RiskPrediction.created_at.desc()))
    policy_evaluation = await session.scalar(select(PolicyEvaluation).where(PolicyEvaluation.transaction_id == transaction_id).order_by(PolicyEvaluation.evaluated_at.desc()))
    features = await session.scalar(select(TransactionFeature).where(TransactionFeature.transaction_id == transaction_id).order_by(TransactionFeature.computed_at.desc()))
    audits = (await session.scalars(select(AuditEvent).where(AuditEvent.transaction_id == transaction_id).order_by(AuditEvent.occurred_at.asc()))).all()
    return transaction, decision, prediction, policy_evaluation, features, audits


@router.post("/{transaction_id}/investigation")
async def create_investigation(transaction_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    transaction, decision, prediction, policy_evaluation, features, audits = await _load_case(transaction_id, session)
    evidence = build_evidence(
        transaction=transaction,
        decision=decision,
        prediction=prediction,
        policy_evaluation=policy_evaluation,
        features=features,
        audits=audits,
    )
    result = await ReadOnlyLLMProvider().investigate(evidence=evidence, authoritative_decision=decision.decision)
    telemetry.increment("investigations_total", provider=result.provider, status=result.status)

    investigation = await session.scalar(select(Investigation).where(Investigation.transaction_id == transaction_id))
    if investigation is None:
        investigation = Investigation(id=uuid4(), transaction_id=transaction_id)
        session.add(investigation)
    investigation.status = result.status
    investigation.prompt_version = result.prompt_version
    investigation.evidence_hash = result.evidence_hash
    investigation.result = {
        "summary": result.summary,
        "assessment": result.assessment,
        "recommended_action": result.recommended_action,
        "cited_evidence": result.cited_evidence,
        "provider": result.provider,
        "evidence": [item.__dict__ for item in evidence],
    }
    session.add(
        AuditEvent(
            id=uuid4(),
            transaction_id=transaction_id,
            event_type="INVESTIGATION_COMPLETED",
            actor_type="SYSTEM",
            actor_id=None,
            payload={"provider": result.provider, "prompt_version": result.prompt_version, "evidence_hash": result.evidence_hash},
        )
    )
    await session.commit()
    return {"transaction_id": transaction_id, "status": result.status, "prompt_version": result.prompt_version, "evidence_hash": result.evidence_hash, "result": investigation.result}


@router.get("/{transaction_id}/investigation")
async def get_investigation(transaction_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    investigation = await session.scalar(select(Investigation).where(Investigation.transaction_id == transaction_id))
    if investigation is None:
        raise HTTPException(status_code=404, detail="investigation_not_found")
    return {
        "transaction_id": transaction_id,
        "status": investigation.status,
        "prompt_version": investigation.prompt_version,
        "evidence_hash": investigation.evidence_hash,
        "result": investigation.result,
    }


def register_investigation_routes(app) -> None:
    app.include_router(router)
