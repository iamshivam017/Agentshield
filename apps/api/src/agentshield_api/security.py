from __future__ import annotations

from secrets import compare_digest
from uuid import UUID

from .config import settings


def authorize_agent(
    agent_id: UUID,
    x_agent_api_key: str | None = None,
    x_agent_id: UUID | None = None,
) -> None:
    """Authenticate and bind a caller to the requested agent.

    Development/test environments may omit the shared key. Once authentication
    is enabled, callers must present the configured key and an explicit agent
    identity header matching the request body.
    """
    if settings.require_agent_auth and not settings.agent_api_key:
        raise PermissionError("agent_auth_not_configured")
    if not settings.require_agent_auth:
        return
    if x_agent_api_key is None or not compare_digest(x_agent_api_key, settings.agent_api_key or ""):
        raise PermissionError("invalid_agent_credentials")
    if x_agent_id is None or x_agent_id != agent_id:
        raise PermissionError("agent_identity_mismatch")


def authorize_operator(
    x_operator_api_key: str | None = None,
    x_operator_id: str | None = None,
) -> str:
    """Authenticate a privileged control-plane operator.

    Production/staging require an explicitly configured operator key. Local
    development may opt into the same requirement through configuration.
    """
    protected_environment = settings.app_env.lower() in {"production", "staging"}
    if (settings.require_operator_auth or protected_environment) and not settings.operator_api_key:
        raise PermissionError("operator_auth_not_configured")
    if not settings.require_operator_auth and not protected_environment:
        return x_operator_id or "local-operator"
    if x_operator_api_key is None or not compare_digest(x_operator_api_key, settings.operator_api_key or ""):
        raise PermissionError("invalid_operator_credentials")
    return x_operator_id or "operator"
