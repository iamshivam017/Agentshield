from sqlalchemy import inspect

from agentshield_api.models import Base


REQUIRED_TABLES = {
    "agents",
    "agent_policies",
    "merchants",
    "transactions",
    "transaction_features",
    "risk_predictions",
    "policy_evaluations",
    "risk_decisions",
    "investigations",
    "reviews",
    "model_versions",
    "evaluation_runs",
    "idempotency_records",
    "agent_budget_state",
    "payment_orders",
    "provider_payments",
    "webhook_events",
    "audit_events",
}


def test_metadata_contains_required_tables() -> None:
    assert REQUIRED_TABLES.issubset(Base.metadata.tables.keys())


def test_money_fields_use_decimal_numeric_columns() -> None:
    transactions = Base.metadata.tables["transactions"]
    budget = Base.metadata.tables["agent_budget_state"]
    assert str(transactions.c.amount.type) == "NUMERIC(18, 2)"
    assert str(budget.c.spent.type) == "NUMERIC(18, 2)"
    assert str(budget.c.reserved.type) == "NUMERIC(18, 2)"


def test_idempotency_scope_is_unique() -> None:
    table = Base.metadata.tables["idempotency_records"]
    constraints = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if constraint.name == "uq_idempotency_scope_key"
    }
    assert ("scope", "key") in constraints
