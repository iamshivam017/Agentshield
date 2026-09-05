# Implementation Status

## M14 — Repository Foundation

- [x] Repository created and verified
- [x] README baseline
- [x] Engineering rules (`AGENTS.md`)
- [x] Secret-safe `.gitignore`
- [x] Environment template
- [x] Initial architecture documentation
- [x] Monorepo application scaffolds
- [x] Local PostgreSQL + Redis development stack
- [x] API container definition
- [x] Web standalone container definition
- [ ] CI workflow

### M14.1 — Application Scaffold

- [x] FastAPI service boundary
- [x] Liveness/readiness endpoints
- [x] Next.js web application boundary
- [x] Root development commands
- [x] Docker build context exclusions

### M14.2 — Local Development Infrastructure

- [x] PostgreSQL service
- [x] Redis service
- [x] API development container
- [x] Web standalone build configuration
- [x] Non-root API container user

## M15 — Database & Migrations

- [x] Async SQLAlchemy engine/session foundation
- [x] PostgreSQL domain model layer
- [x] Core AgentShield schema migration
- [x] Risk/AI/payment schema migration
- [x] Transaction, prediction, policy-evaluation, decision persistence
- [x] Investigation and human-review persistence
- [x] Model/evaluation registry persistence
- [x] Idempotency persistence
- [x] Agent budget state for transactional concurrency control
- [x] Payment order/provider-payment state
- [x] Webhook event deduplication key
- [x] Audit-event persistence
- [x] Schema contract tests
- [x] Alembic migration-chain tests
- [ ] Migration execution against a live local database
- [ ] Integration tests for transactions/concurrency/idempotency
- [ ] Database backup/restore verification

## M16 — Synthetic Dataset + Risk Model

- [x] Reproducible synthetic transaction generator
- [x] Legitimate hard-negative scenarios represented
- [x] Leakage-safe point-in-time feature pipeline
- [x] Chronological train/validation/frozen-test split
- [x] Baseline logistic-risk model pipeline
- [x] Precision/recall/F1/PR-AUC/ROC-AUC/confusion-matrix evaluation
- [x] Validation threshold selection with FP/FN costs
- [x] Model metadata/version/seed capture
- [x] Automated ML unit tests
- [ ] Runtime model training and measured validation/test metrics
- [ ] Candidate XGBoost comparison
- [ ] Calibration analysis
- [ ] Model artifact SHA-256 registry record

## Next checkpoint

M15.1 — Migration execution + persistence integration tests.

ML scaffolding is implemented without claiming measured performance. Runtime database verification remains the immediate gate; after it passes, execute the ML training pipeline and record real held-out metrics before integrating the model into the risk API.
