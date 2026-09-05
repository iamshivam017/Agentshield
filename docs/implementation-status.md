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
- [x] CI workflow

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
- [x] Payment-state integrity constraints and terminal-capture guard
- [x] Audit-event persistence
- [x] Schema contract tests
- [x] Alembic migration-chain tests
- [x] Migration execution against a live PostgreSQL service in CI
- [x] PostgreSQL integration coverage for transaction/idempotency invariants
- [x] PostgreSQL integration coverage for terminal payment state
- [ ] Concurrent multi-request budget stress test
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
- [x] Runtime training pipeline implementation for measured validation/test metrics
- [x] Candidate XGBoost comparison implementation
- [x] Calibration analysis implementation (Brier + ECE)
- [x] Artifact SHA-256 checksum generation and registry metadata
- [x] CI runtime training smoke with verified artifact hand-off
- [x] API serving path verifies model artifact checksum before load
- [ ] Final trained model promoted to APPROVED/ACTIVE with persisted registry workflow

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
- [x] Read-only risk queue/detail APIs
- [x] Human review endpoint with audit event
- [x] Policy/model/audit read APIs
- [x] Risk metrics API
- [x] Production/staging control-plane authentication enforcement
- [x] Viewer/analyst/admin role separation
- [x] Server-trusted reviewer identity binding
- [ ] Redis-backed distributed rate limiting
- [ ] Full API integration suite in production-like environment

## M18 — Razorpay Test Mode Payment Integration

- [x] Razorpay Test Mode provider adapter
- [x] Provider protocol abstraction
- [x] Deterministic mock provider for tests
- [x] Non-Test-Mode credential rejection
- [x] Decimal-to-provider-subunit conversion
- [x] ALLOW-only order creation boundary
- [x] Payment order persistence
- [x] Budget reservation and settlement around order creation
- [x] Raw-body HMAC-SHA256 webhook verification
- [x] Provider event-id duplicate handling
- [x] Authorized/captured/failed state mapping
- [x] Explicit payment state machine
- [x] Terminal capture integrity enforced at database layer
- [x] Out-of-order regression protection for captured payments
- [ ] Live Razorpay Test Mode credential execution
- [ ] Webhook replay/out-of-order integration tests against webhook endpoint
- [ ] Provider reconciliation path

## M19 — Risk Analyst Command Center

- [x] Executive risk posture dashboard shell
- [x] Risk queue table with decision/risk metadata
- [x] Demo scenario simulator
- [x] Model health / decision mix / control-plane cards
- [x] Track 02 and Test Mode safety boundary in UI
- [x] Responsive layout foundations
- [x] Keyboard-focusable navigation controls
- [x] Real API data wiring for risk metrics and queue
- [x] Transaction investigation workspace
- [x] Human review actions from investigation workspace
- [x] Real audit trail rendering
- [x] API proxy configuration for local web/API split
- [x] Policy/model/audit/system-health control-plane screens
- [x] Browser E2E suite in CI
- [ ] Authenticated control-plane browser flow
- [ ] Accessibility automated audit

## Security & Operations

- [x] Operator role-specific credential configuration
- [x] Least-privilege control-plane routing
- [x] Reviewer identity cannot be selected independently of authenticated operator
- [x] Test Mode boundary enforced for Razorpay credentials
- [x] Model artifact integrity check via SHA-256
- [x] Prompt/LLM authority boundary documented
- [ ] Centralized metrics/telemetry backend
- [ ] Operational alert rules and runbooks
- [ ] Load/stress/soak benchmark suite
- [ ] IaC for target deployment environment
- [ ] Backup/restore drill

## CI verification

- [x] API lint
- [x] API type-check
- [x] API unit/security tests
- [x] API dependency audit
- [x] Web lint
- [x] Web type-check
- [x] Web production build
- [x] Web dependency audit
- [x] ML tests/compile
- [x] ML dependency audit
- [x] API + web container builds
- [x] Live PostgreSQL migration check
- [x] Browser E2E execution in CI
- [x] Runtime ML training smoke execution in CI
- [x] Trained smoke artifact checksum verification in API CI

## Next checkpoint

Complete the payment endpoint replay/out-of-order integration tests and provider reconciliation path, then build the investigation/evidence pipeline with explicit provenance and a non-authoritative LLM explanation layer. After that, add centralized observability, performance benchmarks, deployment/rollback artifacts, and the five-reviewer production gap audit.
