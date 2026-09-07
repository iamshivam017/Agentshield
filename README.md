# AgentShield

## AI Risk & Trust Layer for Agentic Payments

AgentShield is a defense-only risk and authorization layer for AI-initiated payment requests. It separates **risk prediction**, **policy authority**, **decisioning**, and **investigation/explanation** so that an LLM never becomes the source of payment authorization truth.

### Core principle

> ML predicts risk. Policy defines authority. The decision engine enforces both. AI explains evidence; it does not authorize payments.

### Primary loss class

Unauthorized or anomalous agent-initiated transactions.

### Architecture

```text
AI Agent
   ↓
Authentication + Request Validation
   ↓
Agent Authorization
   ↓
Idempotency
   ↓
Feature Generation
   ↓
ML Risk Model
   ↓
Policy Engine
   ↓
Decision Engine
   ├── ALLOW  → Payment provider adapter
   ├── VERIFY → Human / step-up verification
   └── BLOCK  → No external order
   ↓
Persistence + Audit
   ↓
Investigation / LLM explanation (non-authoritative)
```

### Repository layout

```text
apps/
  web/                 # Risk Analyst Command Center
  api/                 # FastAPI risk, policy, payment and audit API
ml/                    # Dataset generation, training, evaluation, serving
packages/              # Shared contracts/utilities
infra/                 # Deployment/IaC configuration
tests/                 # Cross-service and end-to-end tests
docs/                  # Architecture, threat model, runbooks, decisions
scripts/               # Developer and data/ML utilities
.github/workflows/     # CI/CD
```

### Local development

Prerequisites: Docker Desktop, Python 3.12+, and Node.js 24+.

```bash
# Install API/ML and web dependencies
make install

# Start PostgreSQL + Redis and the application stack
make dev
```

For infrastructure-only startup:

```bash
make infra-up
```

Common verification commands:

```bash
make db-migrate
make ml-all
make ml-verify
make test
make test-e2e
make verify-all
```

For a running environment, use `make production-check` for health/readiness probes or `make perf-smoke` with `AGENTSHIELD_BASE_URL`, `AGENT_ID`, `MERCHANT_ID`, and `AGENT_API_KEY` set.

The Makefile is the source of truth for these local workflows. Keep real credentials out of committed `.env` files; use the repository environment template and local secret storage instead.

### Render deployment

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/iamshivam017/Agentshield)

The repository includes a Render Blueprint at `render.yaml` for the API, web UI, PostgreSQL, and Redis services. Render's Blueprint flow provisions the interconnected resources from that file; the unresolved values marked `sync: false` must be supplied in the Render dashboard.

### Current status

**Repository engineering gate: PASS.** CI run **#280** on commit `98e2a4bacf9d22f35e56cd1a05a25cb924166fba` completed successfully across API, ML, web, performance-script validation, and container builds.

**Production release: not yet declared.** The remaining gates are intentionally environment-specific: persistent model activation, Razorpay Test Mode execution and webhook replay, target deployment evidence, target load/stress/soak measurements, centralized production telemetry, and rollback evidence.

The durable `Release Risk Model` workflow requires an explicit `APPROVE` input, verifies the exact CI model artifact and metadata, and publishes an approved release copy. The published release artifact must still be activated in the running model registry through the protected admin lifecycle path.

No production secrets or real payment credentials belong in this repository.

### Safety boundary

AgentShield is defense-only. Payment demonstrations use provider test/sandbox environments. Never commit API keys, private credentials, payment card data, or other secrets.

See `AGENTS.md` for engineering rules and `docs/` for the system specification and release runbooks.
