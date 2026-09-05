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

## M17 — Risk Decision API

- [x] Request/response contract for `/api/v1/risk/evaluate`
- [x] Risk band classification boundary
- [x] Policy evaluation boundary
- [x] Deterministic ALLOW/VERIFY/BLOCK decision boundary
- [x] Versioned model-provider serving interface
- [x] Development-only heuristic provider
- [x] Agent/merchant/policy persistence lookup
- [x] Risk prediction and decision persistence
- [x] Policy evaluation persistence
- [x] Risk decision audit event
- [x] Hard policy violations override model outcome
- [x] Production mode refuses service without an active model artifact
- [x] Idempotency enforcement with request fingerprinting
- [x] PostgreSQL advisory-lock serialization for same idempotency key
- [x] Agent API-key authentication boundary
- [x] Agent identity binding to request body
- [x] Transactional daily budget reservation primitive
- [x] Structured validation error envelope
- [x] Request ID propagation
- [x] Security response headers
- [x] Bounded in-process rate limiting
- [x] Unit coverage for security-control invariants
- [ ] Runtime API integration tests against PostgreSQL
- [ ] Redis-backed distributed rate limiting
- [ ] Trained model artifact integration

## M18 — Razorpay Test Mode Payment Integration

- [x] Razorpay Test Mode provider adapter
- [x] Non-Test-Mode credential rejection
- [x] Decimal-to-provider-subunit conversion
- [x] ALLOW-only order creation boundary
- [x] Payment order persistence
- [x] Budget reservation and settlement around order creation
- [x] Raw-body HMAC-SHA256 webhook verification
- [x] Provider event-id duplicate handling
- [x] Authorized/captured/failed state mapping
- [ ] Live Razorpay Test Mode credential execution
- [ ] Webhook replay/out-of-order integration tests
- [ ] Provider reconciliation path

## M19 — Risk Analyst Command Center

- [x] Executive risk posture dashboard shell
- [x] Risk queue table with decision/risk metadata
- [x] Demo scenario simulator
- [x] Model health / decision mix / control-plane cards
- [x] Track 02 and Test Mode safety boundary in UI
- [x] Responsive layout foundations
- [x] Keyboard-focusable navigation controls
- [ ] Real API data wiring
- [ ] Investigation workspace
- [ ] Policy management UI
- [ ] Model evaluation UI
- [ ] Audit explorer
- [ ] System health detail page
- [ ] Accessibility automated audit
- [ ] Browser E2E tests

## Next checkpoint

M15.1 — Live PostgreSQL migration + persistence integration verification, while M19 continues through real API wiring.

The first polished Risk Analyst Command Center experience is now committed. It intentionally uses clearly labeled sandbox/demo values until backend endpoints are wired; it does not present demo statistics as measured production metrics.
