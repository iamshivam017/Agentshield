"""Add risk, investigation, model, idempotency, budget, and payment tables.

Revision ID: 0002_risk_ai_payment_schema
Revises: 0001_core_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_risk_ai_payment_schema"
down_revision = "0001_core_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    ts = sa.DateTime(timezone=True)
    now = sa.func.now()

    op.create_table(
        "transaction_features",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feature_version", sa.String(80), nullable=False),
        sa.Column("values", jsonb, nullable=False),
        sa.Column("computed_at", ts, server_default=now, nullable=False),
        sa.UniqueConstraint("transaction_id", "feature_version", name="uq_transaction_feature_version"),
    )
    op.create_table(
        "risk_predictions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("score", sa.Numeric(8, 6), nullable=False),
        sa.Column("risk_band", sa.String(16), nullable=False),
        sa.Column("signals", jsonb, nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_index("ix_risk_predictions_transaction", "risk_predictions", ["transaction_id"])
    op.create_table(
        "policy_evaluations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("violations", jsonb, nullable=False),
        sa.Column("evaluated_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "investigations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=True),
        sa.Column("evidence_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", jsonb, nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
        sa.Column("updated_at", ts, server_default=now, nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_investigation_transaction"),
    )
    op.create_table(
        "reviews",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(160), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "model_versions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("version", sa.String(80), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("metrics", jsonb, nullable=False),
        sa.Column("training_config", jsonb, nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("dataset_version", sa.String(80), nullable=False),
        sa.Column("metrics", jsonb, nullable=False),
        sa.Column("threshold", sa.Numeric(8, 6), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("scope", sa.String(80), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", jsonb, nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_table(
        "agent_budget_state",
        sa.Column("agent_id", uuid, sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("period_key", sa.String(32), primary_key=True),
        sa.Column("spent", sa.Numeric(18, 2), nullable=False),
        sa.Column("reserved", sa.Numeric(18, 2), nullable=False),
        sa.Column("updated_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "payment_orders",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_order_id", sa.String(160), nullable=False, unique=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "provider_payments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("provider_payment_id", sa.String(160), nullable=False, unique=True),
        sa.Column("payment_order_id", uuid, sa.ForeignKey("payment_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("raw_event", jsonb, nullable=False),
        sa.Column("created_at", ts, server_default=now, nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_event_id", sa.String(160), nullable=False),
        sa.Column("signature_valid", sa.Boolean(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("processed", sa.Boolean(), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("received_at", ts, server_default=now, nullable=False),
        sa.UniqueConstraint("provider", "provider_event_id", name="uq_webhook_provider_event"),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("provider_payments")
    op.drop_table("payment_orders")
    op.drop_table("agent_budget_state")
    op.drop_table("idempotency_records")
    op.drop_table("evaluation_runs")
    op.drop_table("model_versions")
    op.drop_table("reviews")
    op.drop_table("investigations")
    op.drop_table("policy_evaluations")
    op.drop_index("ix_risk_predictions_transaction", table_name="risk_predictions")
    op.drop_table("risk_predictions")
    op.drop_table("transaction_features")
