# AgentShield Infrastructure

## Reference deployment target: Render

`render.yaml` defines the current hackathon/staging deployment target for AgentShield using Render Docker web services, managed PostgreSQL, and Redis-compatible Key Value. Render supports Docker services in a monorepo and Blueprint-managed Postgres/Key Value resources. Free instances are suitable for a temporary demo/staging environment; they are not production-grade because free web services spin down and free Postgres expires after 30 days and has no backups.

The Blueprint intentionally does not contain secret values. Agent credentials, operator credentials, model artifact paths/checksums, Razorpay Test Mode credentials, and webhook secrets must be supplied through the Render dashboard/secret configuration.

The production model artifact remains an external release input. The deployment is not considered release-ready until a verified model artifact and matching SHA-256 metadata are supplied and the persisted model is promoted to `APPROVED`/`ACTIVE`.

## Deployment model

AgentShield is packaged as separate API and web containers with PostgreSQL as the system of record. Redis is optional and reserved for distributed rate limiting/cache work; the core risk decision path must not depend on Redis availability.

The repository provides portable container artifacts, a Render deployment Blueprint, and observability configuration. A different cloud target can be added later without changing the application architecture.

## Production promotion

Promote an immutable image/artifact identified by the Git SHA. Never rebuild the same release tag from a changed source tree. Before promotion:

1. Verify CI is green, including API, ML, Web/E2E, security/dependency checks, migration execution, and container builds.
2. Verify the model artifact SHA-256 and model metadata match the release manifest.
3. Run database migrations using the exact release artifact.
4. Start the new API/web containers and verify `/health/live` and `/health/ready`.
5. Verify authenticated control-plane access, risk evaluation, policy enforcement, and payment lifecycle smoke tests.
6. Promote traffic only after smoke checks pass.

## Rollback

Application rollback and model rollback are independent:

- Application: redeploy the previous immutable image SHA.
- Model: activate the previously approved model version without changing application code.
- Configuration: restore the previous versioned secret/configuration set.
- Database: use forward-compatible expand/contract migrations. Do not use destructive schema rollback as the normal incident response.

## Database backup/restore drill

A production environment must schedule encrypted PostgreSQL backups and periodically restore one into an isolated database. The restore drill should verify migration compatibility, row counts for critical tables, audit-chain readability, model registry integrity, and application readiness against the restored database. Record the observed RPO/RTO; repository documentation does not claim a recovery objective that has not been measured.

## Required production secrets

Store operator credentials, agent credentials, Razorpay Test Mode credentials, webhook secret, database credentials, and model artifact integrity metadata in a managed secret/configuration system. Never commit real credentials to the repository.

## Observability

Prometheus-compatible scraping and baseline alert rules live under `infra/observability`. Production should persist metrics outside individual API instances so restarts do not erase operational history.
