"""Create AgentShield core schema.

Revision ID: 0001_core_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_core_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()

    op.create_table(
        "agents",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("metadata_json", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "merchants",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("metadata_json", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "agent_policies",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_id", uuid, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rules", jsonb, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_policy_version"),
    )
    op.create_index("ix_agent_policies_agent_active", "agent_policies", ["agent_id", "is_active"])

    op.create_table(
        "transactions",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("agent_id", uuid, sa.ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("merchant_id", uuid, sa.ForeignKey("merchants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("device_id", sa.String(160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_transactions_agent_occurred", "transactions", ["agent_id", "occurred_at"])
    op.create_index("ix_transactions_merchant_occurred", "transactions", ["merchant_id", "occurred_at"])

    op.create_table(
        "risk_decisions",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("risk_score", sa.Numeric(8, 6), nullable=False),
        sa.Column("risk_band", sa.String(16), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("reason_codes", jsonb, nullable=False),
        sa.UniqueConstraint("transaction_id", name="uq_risk_decision_transaction"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", uuid, primary_key=True, nullable=False),
        sa.Column("transaction_id", uuid, sa.ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=True),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_events_transaction_time", "audit_events", ["transaction_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_transaction_time", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("risk_decisions")
    op.drop_index("ix_transactions_merchant_occurred", table_name="transactions")
    op.drop_index("ix_transactions_agent_occurred", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_agent_policies_agent_active", table_name="agent_policies")
    op.drop_table("agent_policies")
    op.drop_table("merchants")
    op.drop_table("agents")
