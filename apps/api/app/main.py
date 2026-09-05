from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
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
    WebhookEvent,
)
from app.payment_contracts import PaymentOrderRequest, PaymentOrderResponse
from app.razorpay import PaymentProviderError, RazorpayTestProvider, verify_webhook_signature
from agentshield_api.rate_limit import rate_limiter
from agentshield_api.risk import PolicyContext, RiskAssessment, classify_score, decide, evaluate_policy
from agentshield_api.security import authorize_agent

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
async def evaluate_risk(request: RiskEvaluateRequest, session: AsyncSession = Depends(get_session)) -> RiskEvaluateResponse:
    authorize_agent(request.agent_id)
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
    try:
        model = model_provider.get_active()
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    score, model_signals = model.predict(amount=request.amount, category=request.category)
    assessment = RiskAssessment(score=score, band=classify_score(score), model_version=model.version, signals=model_signals)
    rules = policy.rules or {}
    transaction_limit = Decimal(str(rules.get("transaction_limit", settings.transaction_limit_default)))
    daily_limit = Decimal(str(rules.get("daily_limit", settings.daily_limit_default)))
    verification_threshold = Decimal(str(rules.get("verification_threshold", settings.verification_threshold)))
    allowed_categories = {str(v).upper() for v in rules.get("allowed_categories", [])}
    period_key = (request.occurred_at or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    budget_state = await session.scalar(select(AgentBudgetState).where(AgentBudgetState.agent_id == agent.id, AgentBudgetState.period_key == period_key))
    daily_spent = Decimal("0") if budget_state is None else budget_state.spent + budget_state.reserved
    policy_result = evaluate_policy(PolicyContext(agent_active=agent.status == "ACTIVE", amount=request.amount, transaction_limit=transaction_limit, daily_spent=daily_spent, daily_limit=daily_limit, verification_threshold=verification_threshold, category_allowed=not allowed_categories or request.category.upper() in allowed_categories), policy.version)
    decision = decide(assessment, policy_result, verification_threshold)
    transaction_id = uuid4()
    reason_codes = list(dict.fromkeys(policy_result.violations + model_signals))
    session.add(Transaction(id=transaction_id, agent_id=agent.id, merchant_id=merchant.id, amount=request.amount, currency=request.currency, device_id=request.device_id, occurred_at=request.occurred_at, status="EVALUATED"))
    session.add(RiskPrediction(id=uuid4(), transaction_id=transaction_id, model_version=model.version, score=score, risk_band=assessment.band.value, signals={"signals": model_signals}))
    session.add(PolicyEvaluation(id=uuid4(), transaction_id=transaction_id, policy_version=policy.version, result=decision.value, violations=policy_result.violations))
    session.add(RiskDecision(id=uuid4(), transaction_id=transaction_id, decision=decision.value, risk_score=score, risk_band=assessment.band.value, model_version=model.version, policy_version=policy.version, reason_codes=reason_codes))
    session.add(AuditEvent(id=uuid4(), transaction_id=transaction_id, event_type="RISK_DECISION_CREATED", actor_type="AGENT", actor_id=str(agent.id), payload={"decision": decision.value, "risk_score": str(score), "risk_band": assessment.band.value, "model_version": model.version, "policy_version": policy.version, "reason_codes": reason_codes}))
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
    prediction = await session.scalar(select(RiskPrediction).where(RiskPrediction.transaction_id == transaction_id).order_by(RiskPrediction.created_at.desc()))
    policy_eval = await session.scalar(select(PolicyEvaluation).where(PolicyEvaluation.transaction_id == transaction_id).order_by(PolicyEvaluation.evaluated_at.desc()))
    reviews = (await session.scalars(select(Review).where(Review.transaction_id == transaction_id).order_by(Review.created_at.desc()))).all()
    audits = (await session.scalars(select(AuditEvent).where(AuditEvent.transaction_id == transaction_id).order_by(AuditEvent.occurred_at.asc()))).all()
    investigation = await session.scalar(select(Investigation).where(Investigation.transaction_id == transaction_id))
    payment_order = await session.scalar(select(PaymentOrder).where(PaymentOrder.transaction_id == transaction_id))
    provider_payment = None
    if payment_order is not None:
        provider_payment = await session.scalar(select(ProviderPayment).where(ProviderPayment.payment_order_id == payment_order.id).order_by(ProviderPayment.created_at.desc()))
    return TransactionDetailResponse(
        transaction=queue_item(transaction, agent, merchant, decision),
        prediction=None if prediction is None else {"model_version": prediction.model_version, "score": str(prediction.score), "risk_band": prediction.risk_band, "signals": prediction.signals, "created_at": prediction.created_at.isoformat()},
        policy_evaluation=None if policy_eval is None else {"policy_version": policy_eval.policy_version, "result": policy_eval.result, "violations": policy_eval.violations, "evaluated_at": policy_eval.evaluated_at.isoformat()},
        decision_record={"decision": decision.decision, "risk_score": str(decision.risk_score), "risk_band": decision.risk_band, "model_version": decision.model_version, "policy_version": decision.policy_version, "reason_codes": decision.reason_codes},
        reviews=[ReviewResponse(id=r.id, transaction_id=r.transaction_id, reviewer_id=r.reviewer_id, outcome=r.outcome, note=r.note, created_at=r.created_at) for r in reviews],
        audit_events=[audit_item(a) for a in audits],
        investigation=None if investigation is None else {"status": investigation.status, "prompt_version": investigation.prompt_version, "evidence_hash": investigation.evidence_hash, "result": investigation.result},
        payment_order=None if payment_order is None else {"provider": payment_order.provider, "provider_order_id": payment_order.provider_order_id, "state": payment_order.state, "amount_minor": payment_order.amount_minor, "currency": payment_order.currency},
        provider_payment=None if provider_payment is None else {"provider_payment_id": provider_payment.provider_payment_id, "state": provider_payment.state, "raw_event": provider_payment.raw_event},
    )


@app.post("/api/v1/risk/transactions/{transaction_id}/review", response_model=ReviewResponse, status_code=201, tags=["risk"])
async def review_risk_transaction(transaction_id: UUID, request: ReviewCreateRequest, session: AsyncSession = Depends(get_session)) -> ReviewResponse:
    transaction = await session.scalar(select(Transaction).where(Transaction.id == transaction_id))
    decision = await session.scalar(select(RiskDecision).where(RiskDecision.transaction_id == transaction_id))
    if transaction is None or decision is None:
        raise HTTPException(status_code=404, detail="transaction_not_found")
    review = Review(id=uuid4(), transaction_id=transaction_id, reviewer_id=request.reviewer_id, outcome=request.outcome, note=request.note)
    session.add(review)
    session.add(AuditEvent(id=uuid4(), transaction_id=transaction_id, event_type="RISK_REVIEW_RECORDED", actor_type="REVIEWER", actor_id=request.reviewer_id, payload={"outcome": request.outcome, "note": request.note}))
    await session.commit()
    await session.refresh(review)
    return ReviewResponse(id=review.id, transaction_id=review.transaction_id, reviewer_id=review.reviewer_id, outcome=review.outcome, note=review.note, created_at=review.created_at)


@app.get("/api/v1/policies", response_model=list[PolicyItem], tags=["policies"])
async def list_policies(agent_id: UUID | None = None, session: AsyncSession = Depends(get_session)) -> list[PolicyItem]:
    stmt = select(AgentPolicy).order_by(AgentPolicy.agent_id, AgentPolicy.version.desc())
    if agent_id is not None:
        stmt = stmt.where(AgentPolicy.agent_id == agent_id)
    rows = (await session.scalars(stmt)).all()
    return [PolicyItem(id=p.id, agent_id=p.agent_id, version=p.version, is_active=p.is_active, rules=p.rules, created_at=p.created_at) for p in rows]


@app.get("/api/v1/models", response_model=list[ModelItem], tags=["models"])
async def list_models(session: AsyncSession = Depends(get_session)) -> list[ModelItem]:
    rows = (await session.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc()))).all()
    return [ModelItem(version=m.version, status=m.status, artifact_sha256=m.artifact_sha256, metrics=m.metrics, training_config=m.training_config, created_at=m.created_at) for m in rows]


@app.get("/api/v1/audit", response_model=list[AuditItem], tags=["audit"])
async def list_audit(limit: int = 100, transaction_id: UUID | None = None, session: AsyncSession = Depends(get_session)) -> list[AuditItem]:
    limit = min(max(limit, 1), 250)
    stmt = select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)
    if transaction_id is not None:
        stmt = stmt.where(AuditEvent.transaction_id == transaction_id)
    rows = (await session.scalars(stmt)).all()
    return [audit_item(row) for row in rows]


@app.get("/api/v1/risk/metrics", response_model=RiskMetricsResponse, tags=["risk"])
async def risk_metrics(session: AsyncSession = Depends(get_session)) -> RiskMetricsResponse:
    total = int(await session.scalar(select(func.count()).select_from(RiskDecision)) or 0)
    blocked = int(await session.scalar(select(func.count()).select_from(RiskDecision).where(RiskDecision.decision == "BLOCK")) or 0)
    verify = int(await session.scalar(select(func.count()).select_from(RiskDecision).where(RiskDecision.decision == "VERIFY")) or 0)
    allowed = int(await session.scalar(select(func.count()).select_from(RiskDecision).where(RiskDecision.decision == "ALLOW")) or 0)
    high = int(await session.scalar(select(func.count()).select_from(RiskDecision).where(RiskDecision.risk_band == "HIGH")) or 0)
    return RiskMetricsResponse(evaluations=total, high_risk=high, verification=verify, blocked=blocked, allowed=allowed)


@app.post("/api/v1/payments/orders", response_model=PaymentOrderResponse, tags=["payments"])
async def create_payment_order(request: PaymentOrderRequest, session: AsyncSession = Depends(get_session)) -> PaymentOrderResponse:
    scope = "payment:order"
    req_hash = payment_request_hash(request)
    replay = await claim_or_replay_idempotency(session, scope=scope, key=request.idempotency_key, request_hash_value=req_hash)
    if replay is not None:
        await session.rollback()
        return PaymentOrderResponse.model_validate(replay)
    await create_idempotency_claim(session, scope=scope, key=request.idempotency_key, request_hash_value=req_hash)
    transaction = await session.scalar(select(Transaction).where(Transaction.id == request.transaction_id))
    decision = await session.scalar(select(RiskDecision).where(RiskDecision.transaction_id == request.transaction_id))
    if transaction is None or decision is None:
        raise HTTPException(status_code=404, detail="transaction_or_decision_not_found")
    if decision.decision != "ALLOW":
        raise HTTPException(status_code=409, detail="payment_requires_allow_decision")
    existing = await session.scalar(select(PaymentOrder).where(PaymentOrder.transaction_id == transaction.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="payment_order_already_exists")
    policy = await session.scalar(select(AgentPolicy).where(AgentPolicy.agent_id == transaction.agent_id, AgentPolicy.is_active.is_(True)).order_by(AgentPolicy.version.desc()))
    if policy is None:
        raise HTTPException(status_code=409, detail="active_policy_not_configured")
    daily_limit = Decimal(str((policy.rules or {}).get("daily_limit", settings.daily_limit_default)))
    period_key = transaction.occurred_at.astimezone(timezone.utc).date().isoformat()
    await reserve_agent_budget(session, agent_id=transaction.agent_id, amount=transaction.amount, daily_limit=daily_limit, period_key=period_key)
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        await session.rollback()
        raise HTTPException(status_code=503, detail="razorpay_test_mode_not_configured")
    provider = RazorpayTestProvider(key_id=settings.razorpay_key_id, key_secret=settings.razorpay_key_secret)
    try:
        order = await provider.create_order(amount=transaction.amount, currency=transaction.currency, receipt=str(transaction.id))
    except PaymentProviderError as exc:
        await session.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.add(PaymentOrder(id=uuid4(), transaction_id=transaction.id, provider=order.provider, provider_order_id=order.order_id, state=order.state, amount_minor=order.amount_minor, currency=order.currency))
    await settle_budget_reservation(session, agent_id=transaction.agent_id, amount=transaction.amount, period_key=period_key, success=True)
    session.add(AuditEvent(id=uuid4(), transaction_id=transaction.id, event_type="PAYMENT_ORDER_CREATED", actor_type="SYSTEM", actor_id=None, payload={"provider": order.provider, "provider_order_id": order.order_id, "state": order.state, "test_mode": True}))
    response = PaymentOrderResponse(transaction_id=transaction.id, decision=decision.decision, provider=order.provider, provider_order_id=order.order_id, amount=transaction.amount, currency=transaction.currency, state=order.state, test_mode=True)
    await session.execute(update(IdempotencyRecord).where(IdempotencyRecord.scope == scope, IdempotencyRecord.key == request.idempotency_key).values(response_status=200, response_body=response.model_dump(mode="json")))
    await session.commit()
    return response


@app.post("/api/v1/integrations/razorpay/webhook", tags=["webhooks"])
async def razorpay_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    raw_body = await request.body()
    if not verify_webhook_signature(raw_body=raw_body, received_signature=request.headers.get("X-Razorpay-Signature", ""), secret=settings.razorpay_webhook_secret):
        raise HTTPException(status_code=401, detail="invalid_webhook_signature")
    event_id = request.headers.get("x-razorpay-event-id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing_webhook_event_id")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_webhook_json") from exc
    existing = await session.scalar(select(WebhookEvent).where(WebhookEvent.provider == "razorpay", WebhookEvent.provider_event_id == event_id))
    if existing is not None:
        await session.rollback()
        return {"status": "duplicate_ignored"}
    event_type = payload.get("event")
    session.add(WebhookEvent(id=uuid4(), provider="razorpay", provider_event_id=event_id, signature_valid=True, event_type=event_type, payload_hash=hashlib.sha256(raw_body).hexdigest(), processed=False, payload=payload))
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {}) or {}
    provider_payment_id = payment.get("id")
    order_id = payment.get("order_id")
    state = {"payment.authorized": "PAYMENT_AUTHORIZED", "payment.captured": "PAYMENT_CAPTURED", "payment.failed": "PAYMENT_FAILED"}.get(str(event_type), "PAYMENT_UNKNOWN")
    if isinstance(provider_payment_id, str) and provider_payment_id:
        provider_payment = await session.scalar(select(ProviderPayment).where(ProviderPayment.provider_payment_id == provider_payment_id))
        if provider_payment is None:
            payment_order = await session.scalar(select(PaymentOrder).where(PaymentOrder.provider_order_id == order_id)) if isinstance(order_id, str) else None
            session.add(ProviderPayment(id=uuid4(), provider_payment_id=provider_payment_id, payment_order_id=payment_order.id if payment_order else None, state=state, raw_event=payload))
        else:
            provider_payment.state = state
            provider_payment.raw_event = payload
    if isinstance(order_id, str):
        payment_order = await session.scalar(select(PaymentOrder).where(PaymentOrder.provider_order_id == order_id))
        if payment_order is not None:
            payment_order.state = state
            if state == "PAYMENT_CAPTURED":
                transaction = await session.scalar(select(Transaction).where(Transaction.id == payment_order.transaction_id))
                if transaction is not None:
                    transaction.status = "PAYMENT_CAPTURED"
    event_row = await session.scalar(select(WebhookEvent).where(WebhookEvent.provider == "razorpay", WebhookEvent.provider_event_id == event_id))
    if event_row is not None:
        event_row.processed = True
    await session.commit()
    return {"status": "accepted", "event": str(event_type or "unknown")}
