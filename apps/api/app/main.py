from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.config import settings
from agentshield_api.contracts import RiskEvaluateRequest, RiskEvaluateResponse
from agentshield_api.db import get_session
from agentshield_api.model_provider import ModelProvider, ModelUnavailable
from agentshield_api.models import Agent, AgentPolicy, Merchant, RiskDecision, RiskPrediction, Transaction
from agentshield_api.risk import PolicyContext, RiskAssessment, classify_score, decide, evaluate_policy

app = FastAPI(
    title="AgentShield API",
    version="0.1.0",
    description="Defense-only AI risk and trust layer for agentic payments.",
)

model_provider = ModelProvider(environment=settings.app_env)


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    try:
        model_provider.get_active()
    except ModelUnavailable:
        return {"status": "degraded", "reason": "risk_model_unavailable"}
    return {"status": "ready"}


@app.get("/api/v1", tags=["system"])
def api_version() -> dict[str, str]:
    return {"service": "agentshield-api", "version": "v1"}


@app.post("/api/v1/risk/evaluate", response_model=RiskEvaluateResponse, tags=["risk"])
async def evaluate_risk(
    request: RiskEvaluateRequest,
    session: AsyncSession = Depends(get_session),
) -> RiskEvaluateResponse:
    agent = await session.scalar(select(Agent).where(Agent.id == request.agent_id))
    merchant = await session.scalar(select(Merchant).where(Merchant.id == request.merchant_id))
    if agent is None or merchant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_or_merchant_not_found")

    policy = await session.scalar(
        select(AgentPolicy)
        .where(AgentPolicy.agent_id == agent.id, AgentPolicy.is_active.is_(True))
        .order_by(AgentPolicy.version.desc())
    )
    if policy is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="active_policy_not_configured")

    try:
        model = model_provider.get_active()
    except ModelUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    score, model_signals = model.predict(amount=request.amount, category=request.category)
    assessment = RiskAssessment(
        score=score,
        band=classify_score(score),
        model_version=model.version,
        signals=model_signals,
    )

    rules = policy.rules or {}
    transaction_limit = Decimal(str(rules.get("transaction_limit", settings.transaction_limit_default)))
    daily_limit = Decimal(str(rules.get("daily_limit", settings.daily_limit_default)))
    verification_threshold = Decimal(str(rules.get("verification_threshold", settings.verification_threshold)))
    allowed_categories = set(rules.get("allowed_categories", []))
    category_allowed = not allowed_categories or request.category in allowed_categories

    policy_result = evaluate_policy(
        PolicyContext(
            agent_active=agent.status == "ACTIVE",
            amount=request.amount,
            transaction_limit=transaction_limit,
            daily_spent=Decimal("0"),
            daily_limit=daily_limit,
            verification_threshold=verification_threshold,
            category_allowed=category_allowed,
        ),
        policy.version,
    )
    decision = decide(assessment, policy_result, verification_threshold)

    transaction_id = uuid4()
    session.add(
        Transaction(
            id=transaction_id,
            agent_id=agent.id,
            merchant_id=merchant.id,
            amount=request.amount,
            currency=request.currency,
            device_id=request.device_id,
            occurred_at=request.occurred_at,
            status="EVALUATED",
        )
    )
    session.add(
        RiskPrediction(
            id=uuid4(),
            transaction_id=transaction_id,
            model_version=model.version,
            score=score,
            risk_band=assessment.band.value,
            signals={"signals": model_signals},
        )
    )
    session.add(
        RiskDecision(
            id=uuid4(),
            transaction_id=transaction_id,
            decision=decision.value,
            risk_score=score,
            risk_band=assessment.band.value,
            model_version=model.version,
            policy_version=policy.version,
            reason_codes=policy_result.violations + model_signals,
        )
    )
    await session.commit()

    # Evaluation is advisory to the payment provider in this vertical slice.
    # No external order is created here; that occurs only after a real provider
    # adapter is integrated and the ALLOW path passes its own invariants.
    return RiskEvaluateResponse(
        transaction_id=transaction_id,
        decision=decision.value,
        risk_score=score,
        risk_band=assessment.band.value,
        model_version=model.version,
        policy_version=policy.version,
        reason_codes=policy_result.violations + model_signals,
        external_payment_created=False,
    )
