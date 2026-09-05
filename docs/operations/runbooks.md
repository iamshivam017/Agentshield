# AgentShield Operational Runbooks

## API unavailable or high 5xx rate

1. Check `/health/live` and `/health/ready`.
2. Inspect `http_request` logs using request/correlation IDs.
3. Check database connectivity and pool saturation.
4. Verify the active model artifact and checksum.
5. Compare the latest deployment SHA with the last known-good artifact.
6. Roll back the application artifact when the fault is deployment-specific.

## Risk model unavailable

Do not switch to an unverified model. Check artifact path, SHA-256, model metadata, and feature-version compatibility. In production, the service must not silently substitute the development heuristic model.

## Elevated risk latency

Inspect feature-generation queries first, then model inference and database connection-pool wait. Use query plans for the highest-volume historical feature queries. Keep LLM investigation off the critical risk-evaluation path.

## Razorpay webhook signature failures

Confirm the configured webhook secret matches the Test Mode integration. Verify that the raw request body is used for HMAC calculation before parsing JSON. Review event delivery source and recent secret rotation. Do not bypass signature verification.

## Payment state is unknown or inconsistent

Stop any workflow that would declare payment completion without authoritative provider confirmation. Inspect webhook event IDs, provider payment records, payment-order state, and reconciliation results. Reconcile against the provider before changing terminal state.

## LLM investigation degradation

Core risk decisions remain authoritative. A missing, slow, malformed, or unsafe LLM response must fall back to deterministic evidence-based output. Do not manually promote an LLM explanation into a payment decision.

## Suspicious risk spike

Check decision mix by risk band, model version, policy version, and recent deployment changes. Compare feature-missing counters and model-error counters. Preserve the existing policy boundary while investigating; do not loosen thresholds as an emergency response without an approved change.

## Security incident

Preserve relevant audit events and request/correlation IDs. Rotate exposed credentials, disable compromised operator or agent credentials, verify webhook secrets, review policy changes, and isolate the affected deployment. Never modify historical audit records to conceal an incident.
