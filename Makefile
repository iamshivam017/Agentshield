.PHONY: install dev lint format typecheck test test-unit test-integration test-e2e security build db-migrate ml-all ml-verify perf-smoke db-backup-restore-smoke production-check verify verify-all infra-up infra-down

PYTHONPATH := apps/api/src:apps/api
ML_PYTHONPATH := ml/src

install:
	python -m pip install -r apps/api/requirements.txt
	python -m pip install -r ml/requirements.txt
	cd apps/web && npm ci

dev:
	docker compose up -d

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down

lint:
	PYTHONPATH=$(PYTHONPATH) python -m ruff check apps/api
	cd apps/web && npm run lint

format:
	PYTHONPATH=$(PYTHONPATH) python -m ruff format apps/api
	cd apps/web && npm run format

typecheck:
	PYTHONPATH=$(PYTHONPATH) python -m mypy apps/api/app apps/api/src
	cd apps/web && npm run typecheck

test:
	PYTHONPATH=$(PYTHONPATH) pytest -q
	PYTHONPATH=$(ML_PYTHONPATH) pytest -q ml/tests

test-unit:
	PYTHONPATH=$(PYTHONPATH) pytest -q apps/api/tests/unit

test-integration:
	PYTHONPATH=$(PYTHONPATH) pytest -q apps/api/tests/integration

test-e2e:
	cd apps/web && npm run test:e2e

security:
	PYTHONPATH=$(PYTHONPATH) python -m pip_audit -r apps/api/requirements.txt
	python -m pip_audit -r ml/requirements.txt
	cd apps/web && npm audit --audit-level=high

build:
	cd apps/web && npm run build

db-migrate:
	cd apps/api && PYTHONPATH=src:app alembic upgrade head

ml-all:
	PYTHONPATH=$(ML_PYTHONPATH) python -m agentshield_ml.train

ml-verify:
	PYTHONPATH=$(ML_PYTHONPATH) python scripts/verify_model_artifact.py artifacts/risk

perf-smoke:
	k6 run --env AGENTSHIELD_BASE_URL="$(AGENTSHIELD_BASE_URL)" --env AGENT_ID="$(AGENT_ID)" --env MERCHANT_ID="$(MERCHANT_ID)" --env AGENT_API_KEY="$(AGENT_API_KEY)" --env K6_PROFILE=smoke perf/k6/risk-evaluate.js

db-backup-restore-smoke:
	bash scripts/backup_restore_smoke.sh

production-check:
	curl --fail --silent --show-error "$(or $(AGENTSHIELD_BASE_URL),http://127.0.0.1:8000)/health/live"
	curl --fail --silent --show-error "$(or $(AGENTSHIELD_BASE_URL),http://127.0.0.1:8000)/health/ready"
	@echo "AgentShield health checks passed"

verify: lint typecheck test build
verify-all: verify security
