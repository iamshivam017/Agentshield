from __future__ import annotations

from dataclasses import dataclass
import json
from secrets import compare_digest
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from .config import settings


@dataclass(frozen=True)
class OperatorPrincipal:
    operator_id: str
    role: str


ROLE_VIEWER = "risk_viewer"
ROLE_ANALYST = "risk_analyst"
ROLE_ADMIN = "risk_admin"


def authorize_agent(
    agent_id: UUID,
    x_agent_api_key: str | None = None,
    x_agent_id: UUID | None = None,
) -> None:
    """Authenticate and bind a caller to the requested agent."""
    if settings.require_agent_auth and not settings.agent_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="agent_auth_not_configured",
        )
    if not settings.require_agent_auth:
        return
    if x_agent_api_key is None or not compare_digest(x_agent_api_key, settings.agent_api_key or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_agent_credentials")
    if x_agent_id is None or x_agent_id != agent_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="agent_identity_mismatch")


def _operator_credentials() -> tuple[tuple[str, str], ...]:
    configured = (
        (settings.operator_admin_api_key or settings.operator_api_key, ROLE_ADMIN),
        (settings.operator_analyst_api_key, ROLE_ANALYST),
        (settings.operator_viewer_api_key, ROLE_VIEWER),
    )
    return tuple((secret, role) for secret, role in configured if secret)


def authorize_operator(
    x_operator_api_key: str | None = None,
    x_operator_id: str | None = None,
    allowed_roles: Iterable[str] | None = None,
) -> str:
    """Authenticate a control-plane operator and enforce its role."""
    principal = require_operator(x_operator_api_key, x_operator_id, allowed_roles)
    return principal.operator_id


def require_operator(
    x_operator_api_key: str | None = None,
    x_operator_id: str | None = None,
    allowed_roles: Iterable[str] | None = None,
) -> OperatorPrincipal:
    """Return a server-trusted operator identity.

    In development, auth may be disabled for local UX. In staging/production,
    credentials are mandatory and the role is derived from the configured secret;
    a client cannot select its own role.
    """
    protected_environment = settings.app_env.lower() in {"production", "staging"}
    auth_required = settings.require_operator_auth or protected_environment
    credentials = _operator_credentials()

    if auth_required and not credentials:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="operator_auth_not_configured")
    if not auth_required:
        return OperatorPrincipal(operator_id=x_operator_id or "local-operator", role=ROLE_ADMIN)

    if x_operator_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_operator_credentials")

    matched_role: str | None = None
    for secret, role in credentials:
        if compare_digest(x_operator_api_key, secret):
            matched_role = role
            break
    if matched_role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_operator_credentials")

    allowed = set(allowed_roles or ())
    if allowed and matched_role not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_operator_role")

    operator_id = x_operator_id or f"{matched_role}:operator"
    return OperatorPrincipal(operator_id=operator_id, role=matched_role)


def _required_roles(path: str, method: str) -> set[str] | None:
    """Map control-plane resources to least-privilege roles."""
    if path == "/api/v1/policies" and method == "POST":
        return {ROLE_ADMIN}
    if path.startswith("/api/v1/risk/transactions/") and path.endswith("/review") and method == "POST":
        return {ROLE_ANALYST, ROLE_ADMIN}
    if path.startswith("/api/v1/risk/transactions") and method == "GET":
        return {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
    if path == "/api/v1/policies" and method == "GET":
        return {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
    if path == "/api/v1/models" and method == "GET":
        return {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
    if path == "/api/v1/audit" and method == "GET":
        return {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
    if path == "/api/v1/risk/metrics" and method == "GET":
        return {ROLE_VIEWER, ROLE_ANALYST, ROLE_ADMIN}
    return None


def _auth_error_response(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or "unknown"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": str(exc.detail).upper(),
                "message": str(exc.detail),
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id, **dict(exc.headers or {})},
    )


class ControlPlaneAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        allowed_roles = _required_roles(request.url.path, request.method)
        if allowed_roles is not None:
            try:
                principal = require_operator(
                    request.headers.get("X-Operator-API-Key"),
                    request.headers.get("X-Operator-ID"),
                    allowed_roles,
                )
            except HTTPException as exc:
                return _auth_error_response(request, exc)

            request.state.operator = principal

            if request.url.path.endswith("/review") and request.method == "POST":
                try:
                    body = await request.body()
                    payload = json.loads(body)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    return _auth_error_response(
                        request,
                        HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_review_payload"),
                    )
                supplied_reviewer = payload.get("reviewer_id")
                if supplied_reviewer != principal.operator_id:
                    return _auth_error_response(
                        request,
                        HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="reviewer_identity_mismatch"),
                    )

        return await call_next(request)


def install_control_plane_security(app) -> None:
    """Install auth middleware for analyst/operator control-plane APIs."""
    app.add_middleware(ControlPlaneAuthMiddleware)
