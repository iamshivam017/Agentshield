"""Enforce monotonic payment state updates at the database boundary.

Revision ID: 0005_payment_state_monotonic
Revises: 0004_payment_state_integrity
"""

from alembic import op

revision = "0005_payment_state_monotonic"
down_revision = "0004_payment_state_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION payment_state_rank(state text)
        RETURNS integer
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE state
                WHEN 'PAYMENT_UNKNOWN' THEN 0
                WHEN 'ORDER_CREATED' THEN 1
                WHEN 'PAYMENT_PENDING' THEN 2
                WHEN 'PAYMENT_AUTHORIZED' THEN 3
                WHEN 'PAYMENT_FAILED' THEN 4
                WHEN 'PAYMENT_CAPTURED' THEN 5
                ELSE -1
            END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_payment_state_monotonic()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF payment_state_rank(NEW.state) < payment_state_rank(OLD.state) THEN
                NEW.state := OLD.state;
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS payment_orders_state_monotonic ON payment_orders")
    op.execute("DROP TRIGGER IF EXISTS provider_payments_state_monotonic ON provider_payments")
    op.execute(
        """
        CREATE TRIGGER payment_orders_state_monotonic
        BEFORE UPDATE OF state ON payment_orders
        FOR EACH ROW
        EXECUTE FUNCTION guard_payment_state_monotonic();
        """
    )
    op.execute(
        """
        CREATE TRIGGER provider_payments_state_monotonic
        BEFORE UPDATE OF state ON provider_payments
        FOR EACH ROW
        EXECUTE FUNCTION guard_payment_state_monotonic();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS provider_payments_state_monotonic ON provider_payments")
    op.execute("DROP TRIGGER IF EXISTS payment_orders_state_monotonic ON payment_orders")
    op.execute("DROP FUNCTION IF EXISTS guard_payment_state_monotonic()")
    op.execute("DROP FUNCTION IF EXISTS payment_state_rank(text)")
