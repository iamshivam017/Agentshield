from __future__ import annotations

from agentshield_api.observability import Telemetry, prometheus_snapshot


def test_telemetry_records_requests_and_failures() -> None:
    telemetry = Telemetry()
    telemetry.record_request(method="GET", path="/health/live", status_code=200, latency_ms=3)
    telemetry.record_request(method="POST", path="/api/v1/risk/evaluate", status_code=503, latency_ms=7)
    snapshot = telemetry.snapshot()
    assert snapshot["requests"]["GET /health/live"] == 1
    assert snapshot["requests"]["POST /api/v1/risk/evaluate"] == 1
    assert snapshot["failures"]["POST /api/v1/risk/evaluate"] == 1
    assert snapshot["latency_ms_total"]["POST /api/v1/risk/evaluate"] == 7


def test_prometheus_snapshot_is_nonempty() -> None:
    output = prometheus_snapshot()
    assert "agentshield_http_requests_total" in output
    assert "agentshield_http_failures_total" in output
