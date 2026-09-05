from __future__ import annotations

from secrets import compare_digest
from uuid import UUID

from fastapi import HTTPException, status

from .config import settings


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


def authorize_operator(
    x_operator_api_key: str | None = None,
    x_operator_id: str | None = None,
) -> str:
    """Authenticate a privileged control-plane operator."""
    protected_environment = settings.app_env.lower() in {"production", "staging"}
    if (settings.require_operator_auth or protected_environment) and not settings.operator_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="operator_auth_not_configured")
    if not settings.require_operator_auth and not protected_environment:
        return x_operator_id or "local-operator"
    if x_operator_api_key is None or not compare_digest(x_operator_api_key, settings.operator_api_key or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_operator_credentials")
    return x_operator_id or "operator"
