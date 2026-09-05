.PHONY: install dev lint format typecheck test test-unit test-integration test-e2e security build db-migrate db-seed ml-all perf-smoke production-check verify verify-all infra-up infra-down

install:
	python -m pip install -r apps/api/requirements.txt
	cd apps/web && npm install

dev:
	docker compose up -d

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down

lint:
	python -m ruff check apps/api
	cd apps/web && npm run lint

format:
	python -m ruff format apps/api
	cd apps/web && npm run format

typecheck:
	python -m mypy apps/api/app
	cd apps/web && npm run typecheck

test:
	pytest -q

test-unit:
	pytest -q apps/api/tests/unit

test-integration:
	pytest -q apps/api/tests/integration

test-e2e:
	cd apps/web && npm run test:e2e

security:
	python -m pip_audit -r apps/api/requirements.txt
	cd apps/web && npm audit --audit-level=high

build:
	cd apps/web && npm run build

db-migrate:
	cd apps/api && alembic upgrade head

db-seed:
	python scripts/seed.py

ml-all:
	python scripts/ml_pipeline.py

perf-smoke:
	python scripts/perf_smoke.py

production-check:
	python scripts/production_check.py

verify: lint typecheck test build
verify-all: verify security
