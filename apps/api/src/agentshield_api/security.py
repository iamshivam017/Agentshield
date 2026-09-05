from __future__ import annotations

from secrets import compare_digest
from uuid import UUID

from fastapi import Header, HTTPException, status

from .config import settings


def authorize_agent(
    agent_id: UUID,
    x_agent_api_key: str | None = Header(default=None),
    x_agent_id: UUID | None = Header(default=None),
) -> None:
    """Authenticate and bind a caller to the requested agent.

    Development/test environments may omit the shared key. Once a key is
    configured, callers must present it and the explicit agent header must
    match the request body. A production deployment must configure a key.
    """
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
