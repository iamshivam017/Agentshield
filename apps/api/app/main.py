from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.config import settings
from agentshield_api.contracts import RiskEvaluateRequest, RiskEvaluateResponse
from agentshield_api.db import get_session
from agentshield_api.errors import error_payload, install_error_handlers
from agentshield_api.model_provider import ModelProvider, ModelUnavailable
from agentshield_api.models import (
    Agent,
    AgentBudgetState,
    AgentPolicy,
    AuditEvent,
    IdempotencyRecord,
    Merchant,
    PolicyEvaluation,
    RiskDecision,
    RiskPrediction,
    Transaction,
)
from agentshield_api.rate_limit import rate_limiter
from agentshield_api.risk import PolicyContext, RiskAssessment, classify_score, decide, evaluate_policy
from agentshield_api.security import authorize_agent

app = FastAPI(
    title="AgentShield API",
    version="0.1.0",
    description="Defense-only AI risk and trust layer for agentic payments.",
)

model_provider = ModelProvider(environment=settings.app_env)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    if request.url.path.startswith("/api/v1/risk/"):
        rate_limiter.check(request.client.host if request.client else "unknown")
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    headers = dict(exc.headers or {})
    headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(str(exc.detail).upper(), str(exc.detail), request_id),
        headers=headers,
    )


def request_hash(request: RiskEvaluateRequest) -> str:
    payload = request.model_dump(mode="json")
    payload.pop("idempotency_key", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def advisory_lock_key(scope: str, key: str) -> int:
    digest = hashlib.sha256(f"{scope}:{key}".encode("utf-8")).hexdigest()[:16]
    value = int(digest, 16)
    return value - (1 << 63)


async def claim_or_replay_idempotency(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    request_hash_value: str,
) -> RiskEvaluateResponse | None:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": advisory_lock_key(scope, key)})
    existing = await session.scalar(
        select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key)
    )
    if existing is not None:
        if existing.request_hash != request_hash_value:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="idempotency_key_conflict")
        if existing.response_status == 200:
            return RiskEvaluateResponse.model_validate(existing.response_body)

    return None


async def create_idempotency_claim(
    session: AsyncSession,
    *,
    scope: str,
    key: str,
    request_hash_value: str,
) -> None:
    if await session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key)):
        return
    session.add(
        IdempotencyRecord(
            id=uuid4(),
            scope=scope,
            key=key,
            request_hash=request_hash_value,
            response_status=102,
            response_body={"status": "processing"},
        )
    )
    await session.flush()


async def reserve_agent_budget(
    session: AsyncSession,
    *,
    agent_id: UUID,
    amount: Decimal,
    daily_limit: Decimal,
    period_key: str,
) -> Decimal:
    await session.execute(
        insert(AgentBudgetState)
        .values(agent_id=agent_id, period_key=period_key, spent=Decimal("0"), reserved=Decimal("0"))
        .on_conflict_do_nothing(index_elements=["agent_id", "period_key"])
    )
    state = await session.scalar(
        select(AgentBudgetState)
        .where(AgentBudgetState.agent_id == agent_id, AgentBudgetState.period_key == period_key)
        .with_for_update()
    )
    if state is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="budget_state_unavailable")
    available = daily_limit - state.spent - state.reserved
    if amount > available:
        return state.spent + state.reserved
    state.reserved += amount
    return state.spent + state.reserved


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
    authorize_agent(request.agent_id)
    scope = f"risk:evaluate:{request.agent_id}"
    request_hash_value = request_hash(request)

    replay = await claim_or_replay_idempotency(
        session,
        scope=scope,
        key=request.idempotency_key,
        request_hash_value=request_hash_value,
    )
    if replay is not None:
        await session.rollback()
        return replay

    await create_idempotency_claim(
        session,
        scope=scope,
        key=request.idempotency_key,
        request_hash_value=request_hash_value,
    )

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
    allowed_categories = {str(value).upper() for value in rules.get("allowed_categories", [])}
    category_allowed = not allowed_categories or request.category.upper() in allowed_categories
    period_key = request.occurred_at.astimezone(timezone.utc).date().isoformat()

    budget_total = Decimal("0")
    await session.flush()
    budget_state = await session.scalar(
        select(AgentBudgetState)
        .where(AgentBudgetState.agent_id == agent.id, AgentBudgetState.period_key == period_key)
        .with_for_update()
    )
    if budget_state is not None:
        budget_total = budget_state.spent + budget_state.reserved

    policy_result = evaluate_policy(
        PolicyContext(
            agent_active=agent.status == "ACTIVE",
            amount=request.amount,
            transaction_limit=transaction_limit,
            daily_spent=budget_total,
            daily_limit=daily_limit,
            verification_threshold=verification_threshold,
            category_allowed=category_allowed,
        ),
        policy.version,
    )
    decision = decide(assessment, policy_result, verification_threshold)

    if decision.value != "BLOCK":
        reserve_total = await reserve_agent_budget(
            session,
            agent_id=agent.id,
            amount=request.amount,
            daily_limit=daily_limit,
            period_key=period_key,
        )
        if reserve_total > daily_limit:
            policy_result.violations.append("DAILY_LIMIT_EXCEEDED")
            decision = decide(assessment, policy_result, verification_threshold)

    transaction_id = uuid4()
    reason_codes = list(dict.fromkeys(policy_result.violations + model_signals))
    session.add(
        Transaction(
            id=transaction_id,
            agent_id=agent.id,
            merchant_id=merchant.id,
            amount=request.amount,
            currency=request.currency,
            device_id=request.device_id,
            occurred_at=request.occurred_at or datetime.now(timezone.utc),
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
        PolicyEvaluation(
            id=uuid4(),
            transaction_id=transaction_id,
            policy_version=policy.version,
            result=decision.value,
            violations=policy_result.violations,
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
            reason_codes=reason_codes,
        )
    )
    session.add(
        AuditEvent(
            id=uuid4(),
            transaction_id=transaction_id,
            event_type="RISK_DECISION_CREATED",
            actor_type="AGENT",
            actor_id=str(agent.id),
            payload={
                "decision": decision.value,
                "risk_score": str(score),
                "risk_band": assessment.band.value,
                "model_version": model.version,
                "policy_version": policy.version,
                "reason_codes": reason_codes,
            },
        )
    )

    response = RiskEvaluateResponse(
        transaction_id=transaction_id,
        decision=decision.value,
        risk_score=score,
        risk_band=assessment.band.value,
        model_version=model.version,
        policy_version=policy.version,
        reason_codes=reason_codes,
        external_payment_created=False,
    )
    await session.execute(
        update(IdempotencyRecord)
        .where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == request.idempotency_key)
        .values(response_status=200, response_body=response.model_dump(mode="json"))
    )
    await session.commit()
    return response
