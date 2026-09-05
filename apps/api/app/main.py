from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agentshield_api.config import settings
from agentshield_api.contracts import (
    AuditItem,
    ModelItem,
    PolicyItem,
    ReviewCreateRequest,
    ReviewResponse,
    RiskEvaluateRequest,
    RiskEvaluateResponse,
    RiskMetricsResponse,
    RiskQueueItem,
    RiskQueueResponse,
    TransactionDetailResponse,
)
from agentshield_api.db import get_session
from agentshield_api.errors import error_payload, install_error_handlers
from agentshield_api.features import FEATURE_VERSION, build_point_in_time_features
from agentshield_api.model_provider import ModelProvider, ModelUnavailable
from agentshield_api.models import (
    Agent,
    AgentBudgetState,
    AgentPolicy,
    AuditEvent,
    IdempotencyRecord,
    Investigation,
    Merchant,
    ModelVersion,
    PaymentOrder,
    PolicyEvaluation,
    ProviderPayment,
    Review,
    RiskDecision,
    RiskPrediction,
    Transaction,
    TransactionFeature,
    WebhookEvent,
)
from agentshield_api.rate_limit import rate_limiter
from agentshield_api.risk import PolicyContext, RiskAssessment, classify_score, decide, evaluate_policy
from agentshield_api.security import authorize_agent
from app.payment_contracts import PaymentOrderRequest, PaymentOrderResponse
from app.razorpay import PaymentProviderError, RazorpayTestProvider, verify_webhook_signature

app = FastAPI(title="AgentShield API", version="0.1.0", description="Defense-only AI risk and trust layer for agentic payments.")
model_provider = ModelProvider(environment=settings.app_env)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    if request.url.path.startswith("/api/v1/"):
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
    return JSONResponse(status_code=exc.status_code, content=error_payload(str(exc.detail).upper(), str(exc.detail), request_id), headers=headers)


def request_hash(request: RiskEvaluateRequest) -> str:
    payload = request.model_dump(mode="json")
    payload.pop("idempotency_key", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def payment_request_hash(request: PaymentOrderRequest) -> str:
    return hashlib.sha256(json.dumps({"transaction_id": str(request.transaction_id)}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def advisory_lock_key(scope: str, key: str) -> int:
    value = int(hashlib.sha256(f"{scope}:{key}".encode()).hexdigest()[:16], 16)
    return value - (1 << 63)


async def claim_or_replay_idempotency(session: AsyncSession, *, scope: str, key: str, request_hash_value: str):
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": advisory_lock_key(scope, key)})
    existing = await session.scalar(select(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == key))
    if existing is None:
        return None
    if existing.request_hash != request_hash_value:
        raise HTTPException(status_code=409, detail="idempotency_key_conflict")
    if existing.response_status == 200:
        return existing.response_body
    return None


async def create_idempotency_claim(session: AsyncSession, *, scope: str, key: str, request_hash_value: str) -> None:
    session.add(IdempotencyRecord(id=uuid4(), scope=scope, key=key, request_hash=request_hash_value, response_status=102, response_body={"status": "processing"}))
    await session.flush()


async def reserve_agent_budget(session: AsyncSession, *, agent_id: UUID, amount: Decimal, daily_limit: Decimal, period_key: str) -> None:
    await session.execute(insert(AgentBudgetState).values(agent_id=agent_id, period_key=period_key, spent=Decimal("0"), reserved=Decimal("0")).on_conflict_do_nothing(index_elements=["agent_id", "period_key"]))
    state = await session.scalar(select(AgentBudgetState).where(AgentBudgetState.agent_id == agent_id, AgentBudgetState.period_key == period_key).with_for_update())
    if state is None:
        raise HTTPException(status_code=503, detail="budget_state_unavailable")
    if amount > daily_limit - state.spent - state.reserved:
        raise HTTPException(status_code=409, detail="daily_limit_exceeded")
    state.reserved += amount


async def settle_budget_reservation(session: AsyncSession, *, agent_id: UUID, amount: Decimal, period_key: str, success: bool) -> None:
    state = await session.scalar(select(AgentBudgetState).where(AgentBudgetState.agent_id == agent_id, AgentBudgetState.period_key == period_key).with_for_update())
    if state is None:
        raise HTTPException(status_code=503, detail="budget_state_unavailable")
    state.reserved = max(Decimal("0"), state.reserved - amount)
    if success:
        state.spent += amount


def queue_select():
    return (
        select(Transaction, Agent, Merchant, RiskDecision)
        .join(Agent, Agent.id == Transaction.agent_id)
        .join(Merchant, Merchant.id == Transaction.merchant_id)
        .join(RiskDecision, RiskDecision.transaction_id == Transaction.id)
    )


def queue_item(transaction: Transaction, agent: Agent, merchant: Merchant, decision: RiskDecision) -> RiskQueueItem:
    return RiskQueueItem(
        transaction_id=transaction.id,
        agent_id=agent.id,
        agent_name=agent.name,
        merchant_id=merchant.id,
        merchant_name=merchant.name,
        amount=transaction.amount,
        currency=transaction.currency,
        status=transaction.status,
        risk_score=decision.risk_score,
        risk_band=decision.risk_band,
        decision=decision.decision,
        model_version=decision.model_version,
        policy_version=decision.policy_version,
        reason_codes=list(decision.reason_codes or []),
        occurred_at=transaction.occurred_at,
    )


def audit_item(row: AuditEvent) -> AuditItem:
    return AuditItem(id=row.id, transaction_id=row.transaction_id, event_type=row.event_type, actor_type=row.actor_type, actor_id=row.actor_id, payload=row.payload or {}, occurred_at=row.occurred_at)


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
    x_agent_api_key: str | None = Header(default=None),
    x_agent_id: UUID | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> RiskEvaluateResponse:
    authorize_agent(request.agent_id, x_agent_api_key, x_agent_id)
    scope = f"risk:evaluate:{request.agent_id}"
    req_hash = request_hash(request)
    replay = await claim_or_replay_idempotency(session, scope=scope, key=request.idempotency_key, request_hash_value=req_hash)
    if replay is not None:
        await session.rollback()
        return RiskEvaluateResponse.model_validate(replay)
    await create_idempotency_claim(session, scope=scope, key=request.idempotency_key, request_hash_value=req_hash)
    agent = await session.scalar(select(Agent).where(Agent.id == request.agent_id))
    merchant = await session.scalar(select(Merchant).where(Merchant.id == request.merchant_id))
    if agent is None or merchant is None:
        raise HTTPException(status_code=404, detail="agent_or_merchant_not_found")
    policy = await session.scalar(select(AgentPolicy).where(AgentPolicy.agent_id == agent.id, AgentPolicy.is_active.is_(True)).order_by(AgentPolicy.version.desc()))
    if policy is None:
        raise HTTPException(status_code=409, detail="active_policy_not_configured")
    occurred_at = (request.occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        features = await build_point_in_time_features(session, agent_id=agent.id, merchant_id=merchant.id, device_id=request.device_id, occurred_at=occurred_at, amount=request.amount)
        model = model_provider.get_active()
        score, model_signals = model.predict(features=features, category=request.category)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    assessment = RiskAssessment(score=score, band=classify_score(score), model_version=model.version, signals=model_signals)
    rules = policy.rules or {}
    transaction_limit = Decimal(str(rules.get("transaction_limit", settings.transaction_limit_default)))
    daily_limit = Decimal(str(rules.get("daily_limit", settings.daily_limit_default)))
    verification_threshold = Decimal(str(rules.get("verification_threshold", settings.verification_threshold)))
    allowed_categories = {str(v).upper() for v in rules.get("allowed_categories", [])}
    period_key = occurred_at.date().isoformat()
    budget_state = await session.scalar(select(AgentBudgetState).where(AgentBudgetState.agent_id == agent.id, AgentBudgetState.period_key == period_key))
    daily_spent = Decimal("0") if budget_state is None else budget_state.spent + budget_state.reserved
    policy_result = evaluate_policy(PolicyContext(agent_active=agent.status == "ACTIVE", amount=request.amount, transaction_limit=transaction_limit, daily_spent=daily_spent, daily_limit=daily_limit, verification_threshold=verification_threshold, category_allowed=not allowed_categories or request.category.upper() in allowed_categories), policy.version)
    decision = decide(assessment, policy_result, verification_threshold)
    transaction_id = uuid4()
    reason_codes = list(dict.fromkeys(policy_result.violations + model_signals))
    transaction = Transaction(id=transaction_id, agent_id=agent.id, merchant_id=merchant.id, amount=request.amount, currency=request.currency, device_id=request.device_id, occurred_at=occurred_at, status="EVALUATED")
    session.add(transaction)
    await session.flush()
    session.add(TransactionFeature(id=uuid4(), transaction_id=transaction_id, feature_version=FEATURE_VERSION, values=features))
    session.add(RiskPrediction(id=uuid4(), transaction_id=transaction_id, model_version=model.version, score=score, risk_band=assessment.band.value, signals={"signals": model_signals}))
    session.add(PolicyEvaluation(id=uuid4(), transaction_id=transaction_id, policy_version=policy.version, result=decision.value, violations=policy_result.violations))
    session.add(RiskDecision(id=uuid4(), transaction_id=transaction_id, decision=decision.value, risk_score=score, risk_band=assessment.band.value, model_version=model.version, policy_version=policy.version, reason_codes=reason_codes))
    session.add(AuditEvent(id=uuid4(), transaction_id=transaction_id, event_type="RISK_DECISION_CREATED", actor_type="AGENT", actor_id=str(agent.id), payload={"decision": decision.value, "risk_score": str(score), "risk_band": assessment.band.value, "model_version": model.version, "policy_version": policy.version, "feature_version": FEATURE_VERSION, "reason_codes": reason_codes}))
    await session.flush()
    response = RiskEvaluateResponse(transaction_id=transaction_id, decision=decision.value, risk_score=score, risk_band=assessment.band.value, model_version=model.version, policy_version=policy.version, reason_codes=reason_codes, external_payment_created=False)
    await session.execute(update(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == request.idempotency_key).values(response_status=200, response_body=response.model_dump(mode="json")))
    await session.commit()
    return response


@app.get("/api/v1/risk/transactions", response_model=RiskQueueResponse, tags=["risk"])
async def list_risk_transactions(limit: int = 25, offset: int = 0, decision: str | None = None, risk_band: str | None = None, session: AsyncSession = Depends(get_session)) -> RiskQueueResponse:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    base = queue_select()
    count_stmt = select(func.count()).select_from(Transaction).join(RiskDecision, RiskDecision.transaction_id == Transaction.id)
    if decision:
        base = base.where(RiskDecision.decision == decision.upper())
        count_stmt = count_stmt.where(RiskDecision.decision == decision.upper())
    if risk_band:
        base = base.where(RiskDecision.risk_band == risk_band.upper())
        count_stmt = count_stmt.where(RiskDecision.risk_band == risk_band.upper())
    total = int(await session.scalar(count_stmt) or 0)
    rows = (await session.execute(base.order_by(Transaction.occurred_at.desc()).limit(limit).offset(offset))).all()
    return RiskQueueResponse(items=[queue_item(t, a, m, d) for t, a, m, d in rows], total=total, limit=limit, offset=offset)


@app.get("/api/v1/risk/transactions/{transaction_id}", response_model=TransactionDetailResponse, tags=["risk"])
async def get_risk_transaction(transaction_id: UUID, session: AsyncSession = Depends(get_session)) -> TransactionDetailResponse:
    row = (await session.execute(queue_select().where(Transaction.id == transaction_id))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="transaction_not_found")
    transaction, agent, merchant, decision = row
    features = await session.scalar(select(TransactionFeature).where(TransactionFeature.transaction_id == transaction_id, TransactionFeature.feature_version == FEATURE_VERSION))
    prediction = await session.scalar(select(RiskPrediction).where(RiskPrediction.transaction_id == transaction_id).order_by(RiskPrediction.created_at.desc()))
    policy_eval = await session.scalar(select(PolicyEvaluation).where(PolicyEvaluation.transaction_id == transaction_id).order_by(PolicyEvaluation.evaluated_at.desc()))
    reviews = (await session.scalars(select(Review).where(Review.transaction_id == transaction_id).order_by(Review.created_at.desc()))).all()
    audits = (await session.scalars(select(AuditEvent).where(AuditEvent.transaction_id == transaction_id).order_by(AuditEvent.occurred_at.asc()))).all()
    investigation = await session.scalar(select(Investigation).where(Investigation.transaction_id == transaction_id))
    payment_order = await session.scalar(select(PaymentOrder).where(PaymentOrder.transaction_id == transaction_id))
    provider_payment = None
    if payment_order is not None:
        provider_payment = await session.scalar(select(ProviderPayment).where(ProviderPayment.payment_order_id == payment_order.id).order_by(ProviderPayment.created_at.desc()))
    return TransactionDetailResponse(transaction=queue_item(transaction, agent, merchant, decision), features=None if features is None else {"version": features.feature_version, "values": features.values, "computed_at": features.computed_at.isoformat()}, prediction=None if prediction is None else {"model_version": prediction.model_version, "score": str(prediction.score), "risk_band": prediction.risk_band, "signals": prediction.signals, "created_at": prediction.created_at.isoformat()}, policy_evaluation=None if policy_eval is None else {"policy_version": policy_eval.policy_version, "result": policy_eval.result, "violations": policy_eval.violations, "evaluated_at": policy_eval.evaluated_at.isoformat()}, reviews=[{"id": str(r.id), "outcome": r.outcome, "reason": r.reason, "created_at": r.created_at.isoformat()} for r in reviews], audits=[audit_item(a) for a in audits], investigation=None if investigation is None else {"status": investigation.status, "summary": investigation.summary}, payment_order=None if payment_order is None else {"id": str(payment_order.id), "provider": payment_order.provider, "provider_order_id": payment_order.provider_order_id, "status": payment_order.status}, provider_payment=None if provider_payment is None else {"id": str(provider_payment.id), "provider_payment_id": provider_payment.provider_payment_id, "status": provider_payment.status})


# Remaining endpoints intentionally stay in this module; the policy mutation router is
# registered after all legacy routes to avoid import cycles during FastAPI bootstrap.
from agentshield_api.policy_routes import register_policy_routes  # noqa: E402

register_policy_routes(app)
