"""Enforce a single active model version.

Revision ID: 0006_single_active_model
Revises: 0005_payment_state_monotonic
"""

from alembic import op

revision = "0006_single_active_model"
down_revision = "0005_payment_state_monotonic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_one_active
        ON model_versions (status)
        WHERE status = 'ACTIVE'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_model_versions_one_active")
