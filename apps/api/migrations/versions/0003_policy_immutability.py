"""Enforce immutable policy history and a single active policy per agent.

Revision ID: 0003_policy_immutability
Revises: 0002_risk_ai_payment_schema
"""
from alembic import op

revision = "0003_policy_immutability"
down_revision = "0002_risk_ai_payment_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_policies_one_active
        ON agent_policies (agent_id)
        WHERE is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_agent_policy_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'agent policy versions are immutable';
        END;
        $$
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_agent_policy_immutable ON agent_policies
        """
    )
    # Policy deletion remains governed by the owning agent's lifecycle.
    # Application APIs never expose policy deletion; UPDATE is blocked so
    # historical policy contents and activation state cannot be rewritten.
    op.execute(
        """
        CREATE TRIGGER trg_agent_policy_immutable
        BEFORE UPDATE ON agent_policies
        FOR EACH ROW
        EXECUTE FUNCTION prevent_agent_policy_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_agent_policy_immutable ON agent_policies")
    op.execute("DROP FUNCTION IF EXISTS prevent_agent_policy_mutation()")
    op.execute("DROP INDEX IF EXISTS uq_agent_policies_one_active")
