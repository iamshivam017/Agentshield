# AgentShield Release Gates

AgentShield is treated as release-ready only when the repository evidence and the target-environment evidence both pass.

## 1. Source and CI gate

Required before any environment promotion:

```text
GitHub Actions CI: success
API lint/type-check/tests: success
ML tests/training smoke/artifact verification: success
Web lint/type-check/build/E2E/accessibility: success
API + web container builds: success
Live PostgreSQL migrations: success
Backup/restore drill: success
Redis rate-limiter coverage: success
```

The CI workflow is the source-of-truth verification layer for repository changes.

## 2. Model governance gate

A model must be persisted in the model registry and move only through the governed lifecycle:

```text
TRAINED -> EVALUATED -> CANDIDATE -> APPROVED -> ACTIVE -> RETIRED
```

Before APPROVED:

- evaluation metadata is persisted;
- frozen-test metrics are present;
- threshold and calibration information are present;
- artifact SHA-256 is recorded;
- the model version is uniquely identifiable.

Before ACTIVE:

- the artifact is available from the intended artifact store;
- the serving environment is configured for that exact artifact and checksum;
- an authenticated admin performs the APPROVED -> ACTIVE transition;
- the previous ACTIVE version is retired transactionally.

The repository's CI smoke artifact proves the hand-off contract. It is not a substitute for persistence of the real production artifact.

## 3. Payment safety gate

Razorpay integration must remain Test Mode only for this project.

Required environment evidence:

- sandbox credentials are loaded through secrets, never committed;
- an ALLOW decision creates an order;
- VERIFY never creates an order;
- BLOCK never creates an order;
- raw webhook signature verification succeeds before payload processing;
- duplicate provider event IDs are idempotent;
- stale/out-of-order provider events cannot move a payment backward;
- reconciliation produces an auditable result;
- provider-order recovery can reattach an externally-created order after a local persistence failure, using the transaction receipt and amount/currency integrity checks.

No production Razorpay credentials belong in CI, local fixtures, demos, or screenshots.

## 4. Performance gate

Execute `perf/k6/risk-evaluate.js` against the selected deployment target with real target-equivalent configuration.

Select one profile with `K6_PROFILE`:

```text
smoke  — 2 VUs for 15s
load   — ramp to 10 VUs, sustain, ramp down
stress — ramp through 25/50/75 VUs
soak   — ramp to 20 VUs and sustain for 10 minutes
```

Required baseline targets for smoke/load/soak:

- risk evaluation p95 < 500 ms;
- risk evaluation p99 < 1 s;
- HTTP failure rate < 1%.

Stress uses a deliberately wider failure/latency envelope to identify capacity limits:

- HTTP failure rate < 2%;
- p95 < 750 ms;
- p99 < 1.5 s.

Record the environment, commit SHA, model version, load profile, test duration, request count, p95, p99, error rate, and date/time with every run.

Repository presence of the k6 script is not itself performance evidence.

## 5. Deployment gate

The target deployment platform must be explicitly selected before adding target-specific IaC.

The release package must then include:

- immutable API image;
- immutable web image;
- configuration and secret contract;
- database migration procedure;
- rollback procedure;
- health/readiness checks;
- centralized metrics/logging destination;
- alert routing;
- backup retention and restore procedure.

Until a target is selected, this gate remains intentionally open rather than inventing platform-specific infrastructure.

## 6. Final five-reviewer audit

Before declaring the system production-ready, review the release as five independent roles:

1. Principal Product Manager — requirements, scope, demo narrative, traceability.
2. Staff Backend/Security Engineer — authorization, invariants, data integrity, failure modes.
3. Staff ML Engineer — leakage, calibration, thresholding, artifact lineage, monitoring.
4. Staff Frontend/Product Designer — UX hierarchy, accessibility, responsive behavior, operator workflow.
5. SRE/Platform Engineer — deployment, observability, performance, backup/restore, rollback.

Every finding is classified as PASS, FIX, or ACCEPTED RISK with evidence.

## Current evidence boundary

Repository-level gates are verified in CI. Environment-specific gates remain open until the required credentials, artifact store, deployment target, and target telemetry environment are supplied.
