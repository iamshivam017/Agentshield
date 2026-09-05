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

### Development status

Repository foundation in progress. No production secrets or real payment credentials belong in this repository.

### Safety boundary

AgentShield is defense-only. Payment demonstrations use provider test/sandbox environments. Never commit API keys, private credentials, payment card data, or other secrets.

See `AGENTS.md` for engineering rules and `docs/` for the system specification.
