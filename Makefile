.PHONY: install dev lint format typecheck test test-unit test-integration test-e2e security build db-migrate db-seed ml-all perf-smoke production-check verify verify-all infra-up infra-down

PYTHONPATH := apps/api/src:apps/api

install:
	python -m pip install -r apps/api/requirements.txt
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

test-unit:
	PYTHONPATH=$(PYTHONPATH) pytest -q apps/api/tests/unit

test-integration:
	PYTHONPATH=$(PYTHONPATH) pytest -q apps/api/tests/integration

test-e2e:
	cd apps/web && npm run test:e2e

security:
	PYTHONPATH=$(PYTHONPATH) python -m pip_audit -r apps/api/requirements.txt
	cd apps/web && npm audit --audit-level=high

build:
	cd apps/web && npm run build

db-migrate:
	cd apps/api && PYTHONPATH=src:app alembic upgrade head

db-seed:
	PYTHONPATH=$(PYTHONPATH) python scripts/seed.py

ml-all:
	PYTHONPATH=$(PYTHONPATH) python scripts/ml_pipeline.py

perf-smoke:
	PYTHONPATH=$(PYTHONPATH) python scripts/perf_smoke.py

production-check:
	PYTHONPATH=$(PYTHONPATH) python scripts/production_check.py

verify: lint typecheck test build
verify-all: verify security
