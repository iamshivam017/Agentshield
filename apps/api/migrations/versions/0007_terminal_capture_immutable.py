"""Make captured payment state immutable at the database boundary.

Revision ID: 0007_terminal_capture_immutable
Revises: 0006_single_active_model
"""

from alembic import op

revision = "0007_terminal_capture_immutable"
down_revision = "0006_single_active_model"
branch_labels = None
depends_on = None


_TERMINAL_TRIGGER_NAMES = (
    "payment_orders_terminal_capture_guard",
    "provider_payments_terminal_capture_guard",
    "payment_orders_state_monotonic",
    "provider_payments_state_monotonic",
    "payment_orders_captured_immutable",
    "provider_payments_captured_immutable",
)


def upgrade() -> None:
    for trigger_name in _TERMINAL_TRIGGER_NAMES:
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON payment_orders")
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON provider_payments")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_captured_payment_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.state = 'PAYMENT_CAPTURED' AND NEW.state <> 'PAYMENT_CAPTURED' THEN
                NEW.state := 'PAYMENT_CAPTURED';
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER payment_orders_captured_immutable
        BEFORE UPDATE ON payment_orders
        FOR EACH ROW
        EXECUTE FUNCTION enforce_captured_payment_immutability();
        """
    )
    op.execute(
        """
        CREATE TRIGGER provider_payments_captured_immutable
        BEFORE UPDATE ON provider_payments
        FOR EACH ROW
        EXECUTE FUNCTION enforce_captured_payment_immutability();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS provider_payments_captured_immutable ON provider_payments")
    op.execute("DROP TRIGGER IF EXISTS payment_orders_captured_immutable ON payment_orders")
    op.execute("DROP FUNCTION IF EXISTS enforce_captured_payment_immutability()")
