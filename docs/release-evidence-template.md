# AgentShield Release Evidence Record

Use this document for an actual release-validation run. Replace every placeholder with observed evidence; do not mark a gate PASS from repository configuration alone.

## Release identity

- Date/time (UTC): `<timestamp>`
- Git commit SHA: `<40-char SHA>`
- API image digest: `<immutable image digest>`
- Web image digest: `<immutable image digest>`
- Deployment target: `<platform / environment>`
- Operator: `<name or role>`
- Change/release reference: `<release tag, ticket, or incident reference>`

## 1. Model promotion

- Artifact location: `<artifact URI>`
- Model version: `<version>`
- Feature version: `<feature version>`
- Artifact SHA-256: `<sha256>`
- Persisted registry state before promotion: `<state>`
- APPROVED transition evidence: `<timestamp + audit/event reference>`
- ACTIVE transition evidence: `<timestamp + audit/event reference>`
- Previous ACTIVE version retired: `<yes/no + evidence>`
- Serving configuration matches artifact/version/checksum: `<yes/no + evidence>`

**Gate result:** `PASS | FAIL`

## 2. Razorpay Test Mode validation

- Test Mode credentials loaded from managed secret/configuration store: `<yes/no>`
- Credential mode validation result: `<evidence>`
- ALLOW risk evaluation → provider order: `<transaction ID + provider order ID>`
- VERIFY → no provider order: `<transaction ID + evidence>`
- BLOCK → no provider order: `<transaction ID + evidence>`
- Webhook HMAC verification: `<pass/fail + event reference>`
- Duplicate webhook replay: `<pass/fail + event ID>`
- Stale/out-of-order event protection: `<pass/fail + event ID>`
- Reconciliation result: `<pass/fail + audit reference>`
- Receipt-based recovery drill: `<pass/fail + transaction/order reference>`

**Gate result:** `PASS | FAIL`

## 3. Deployment smoke validation

- Database migration result: `<pass/fail + migration head>`
- `/health/live`: `<status + timestamp>`
- `/health/ready`: `<status + timestamp>`
- Authenticated control-plane access: `<pass/fail>`
- Risk evaluation smoke: `<pass/fail + request/decision reference>`
- Policy enforcement smoke: `<pass/fail>`
- Payment lifecycle smoke: `<pass/fail>`
- Logs/metrics visible in centralized backend: `<pass/fail>`

**Gate result:** `PASS | FAIL`

## 4. Performance evidence

Run `perf/k6/risk-evaluate.js` against the selected target. Record the exact profile used for each run.

| Profile | Date/time UTC | Duration | Requests | p95 | p99 | Error rate | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| smoke | `<timestamp>` | `<duration>` | `<count>` | `<ms>` | `<ms>` | `<%>` | `PASS/FAIL` |
| load | `<timestamp>` | `<duration>` | `<count>` | `<ms>` | `<ms>` | `<%>` | `PASS/FAIL` |
| stress | `<timestamp>` | `<duration>` | `<count>` | `<ms>` | `<ms>` | `<%>` | `PASS/FAIL` |
| soak | `<timestamp>` | `<duration>` | `<count>` | `<ms>` | `<ms>` | `<%>` | `PASS/FAIL` |

- Target environment configuration: `<instance/container/database details>`
- Model version/checksum: `<version + sha256>`
- k6 commit SHA: `<40-char SHA>`
- Result files/log references: `<artifact or dashboard links>`

**Gate result:** `PASS | FAIL`

## 5. Observability validation

- Central metrics backend: `<name>`
- Metric retention: `<period>`
- Alert routing destination: `<destination>`
- API/Risk/Payment telemetry visible: `<yes/no>`
- Correlation ID traceability verified: `<yes/no>`
- Alert test performed: `<yes/no + evidence>`

**Gate result:** `PASS | FAIL`

## 6. Backup and rollback evidence

- Backup schedule: `<schedule>`
- Last successful backup: `<timestamp>`
- Restore drill: `<timestamp + result>`
- Observed RPO: `<measured value>`
- Observed RTO: `<measured value>`
- Previous application image SHA/digest: `<immutable reference>`
- Previous approved/active model version: `<version>`
- Rollback execution: `<pass/fail + timestamp>`
- Post-rollback health/readiness: `<pass/fail>`
- Post-rollback risk smoke: `<pass/fail>`

**Gate result:** `PASS | FAIL`

## 7. Final five-reviewer sign-off

| Reviewer | Scope | Result | Evidence/reference |
| --- | --- | --- | --- |
| Principal Product Manager | Requirements, scope, demo, traceability | `PASS/FAIL` | `<reference>` |
| Staff Backend/Security Engineer | Auth, invariants, integrity, failures | `PASS/FAIL` | `<reference>` |
| Staff ML Engineer | Leakage, calibration, threshold, lineage, monitoring | `PASS/FAIL` | `<reference>` |
| Staff Frontend/Product Designer | UX, accessibility, responsive behavior | `PASS/FAIL` | `<reference>` |
| SRE/Platform Engineer | Deployment, observability, performance, backup/rollback | `PASS/FAIL` | `<reference>` |

## Final release decision

- Repository engineering gate: `PASS`
- Environment evidence gate: `PASS | FAIL | OPEN`
- Production release verdict: `RELEASED | NOT RELEASED`

### Evidence rule

A gate may be marked `PASS` only when the required environment evidence has been observed and recorded. Repository files, CI configuration, or planned procedures alone do not satisfy an environment gate.
