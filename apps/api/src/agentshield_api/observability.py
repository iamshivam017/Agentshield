from __future__ import annotations

import json
import logging
import time
from collections import Counter
from threading import Lock
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

logger = logging.getLogger("agentshield")


class Telemetry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests = Counter()
        self._failures = Counter()
        self._latency_ms = Counter()

    def record_request(self, *, method: str, path: str, status_code: int, latency_ms: int) -> None:
        key = f"{method} {path}"
        with self._lock:
            self._requests[key] += 1
            self._latency_ms[key] += latency_ms
            if status_code >= 500:
                self._failures[key] += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "requests": dict(self._requests),
                "failures": dict(self._failures),
                "latency_ms_total": dict(self._latency_ms),
            }


telemetry = Telemetry()


def _safe_path(path: str) -> str:
    return path[:160]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        request.state.correlation_id = correlation_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            path = _safe_path(request.url.path)
            telemetry.record_request(method=request.method, path=path, status_code=status_code, latency_ms=latency_ms)
            logger.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "method": request.method,
                        "path": path,
                        "status_code": status_code,
                        "latency_ms": latency_ms,
                        "request_id": getattr(request.state, "request_id", None),
                        "correlation_id": correlation_id,
                    },
                    separators=(",", ":"),
                )
            )


def prometheus_snapshot() -> str:
    snapshot = telemetry.snapshot()
    lines: list[str] = [
        "# HELP agentshield_http_requests_total Total HTTP requests by method and path.",
        "# TYPE agentshield_http_requests_total counter",
    ]
    for key, value in snapshot["requests"].items():
        method, path = key.split(" ", 1)
        lines.append(f'agentshield_http_requests_total{{method="{method}",path="{path}"}} {value}')
    lines.extend(
        [
            "# HELP agentshield_http_failures_total Total HTTP 5xx responses by method and path.",
            "# TYPE agentshield_http_failures_total counter",
        ]
    )
    for key, value in snapshot["failures"].items():
        method, path = key.split(" ", 1)
        lines.append(f'agentshield_http_failures_total{{method="{method}",path="{path}"}} {value}')
    lines.extend(
        [
            "# HELP agentshield_http_latency_ms_total Total observed request latency in milliseconds.",
            "# TYPE agentshield_http_latency_ms_total counter",
        ]
    )
    for key, value in snapshot["latency_ms_total"].items():
        method, path = key.split(" ", 1)
        lines.append(f'agentshield_http_latency_ms_total{{method="{method}",path="{path}"}} {value}')
    return "\n".join(lines) + "\n"


def install_observability(app: Any) -> None:
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(prometheus_snapshot(), media_type="text/plain; version=0.0.4")
