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

## Next checkpoint

M15.1 — Migration execution + persistence integration tests.

The schema and ORM foundations are committed, and static migration/schema contract coverage is in place. Runtime verification still requires executing Alembic against PostgreSQL and exercising transaction, concurrency, idempotency, and failure behavior.
