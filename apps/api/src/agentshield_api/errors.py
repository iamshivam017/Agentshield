from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, request_id: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def install_error_handlers(app) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=422,
            content=error_payload("VALIDATION_ERROR", "Request validation failed", request_id),
        )

    # Route registration stays outside main.py while preserving a single app
    # bootstrap point. Import lazily to avoid a module-import cycle.
    from .policy_routes import register_policy_routes

    register_policy_routes(app)
