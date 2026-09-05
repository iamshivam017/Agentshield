from __future__ import annotations

from dataclasses import dataclass
from secrets import compare_digest
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, status

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
        role = ROLE_ADMIN
        return OperatorPrincipal(operator_id=x_operator_id or "local-operator", role=role)

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
