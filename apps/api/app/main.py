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
from payment_contracts import PaymentOrderRequest, PaymentOrderResponse
from razorpay import PaymentProviderError, RazorpayTestProvider, verify_webhook_signature
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