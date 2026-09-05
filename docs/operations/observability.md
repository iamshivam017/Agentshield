# AgentShield Observability

## Purpose

AgentShield exposes low-cardinality metrics and structured request logs for operational diagnosis of the risk decision path. Telemetry must never contain secrets, raw payment credentials, or unnecessary personal data.

## Metrics contract

The API exposes Prometheus text metrics at `/metrics`.

Core request metrics:

- `agentshield_http_requests_total{method,path}`
- `agentshield_http_failures_total{method,path}`
- `agentshield_http_latency_ms_total{method,path}`

Domain counters use only bounded labels. Transaction IDs, agent IDs, reviewer IDs, provider order IDs, and other unbounded identifiers must never be metric labels.

Expected domain metrics include:

- `agentshield_risk_decisions_total{decision,risk_band}`
- `agentshield_model_errors_total{type}`
- `agentshield_payment_webhook_events_total{provider,event_type,state}`
- `agentshield_payment_reconciliation_total{provider,state}`
- `agentshield_investigations_total{provider,status}`
- `agentshield_policy_violations_total{reason}`
- `agentshield_feature_snapshot_missing_total{feature}`

The initial implementation is process-local. A production deployment must scrape every API instance and aggregate centrally in Prometheus or an equivalent backend.

## Structured logs

Every HTTP request emits a JSON event named `http_request` containing method, bounded path, status code, latency, request ID, and correlation ID. Application logs should keep the same correlation identifiers through downstream work.

## SLO-oriented signals

The principal operational targets are:

- risk evaluation p50 < 100 ms
- risk evaluation p95 < 500 ms
- risk evaluation p99 < 1 s
- control-plane/dashboard API p95 < 500 ms
- HTTP 5xx rate below 2% for sustained traffic

These are engineering targets, not guarantees, and must be validated in the target deployment environment.

## Alert conditions

Recommended alerts are defined in `infra/observability/alerts.yml`:

- elevated API 5xx rate
- elevated risk-evaluation latency
- database readiness failure
- model unavailable in staging/production
- invalid Razorpay webhook signatures
- excessive LLM fallback rate
- sustained unknown payment reconciliation state
- unusual decision-mix spikes

## Cardinality rules

Allowed labels are stable dimensions such as HTTP method, bounded route pattern, decision, risk band, provider, and enumerated state. Do not add free-form user input, IDs, timestamps, or model evidence text to labels.
