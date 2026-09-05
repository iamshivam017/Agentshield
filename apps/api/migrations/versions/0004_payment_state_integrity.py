"""Harden payment state integrity.

Revision ID: 0004_payment_state_integrity
Revises: 0003_policy_immutability
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_payment_state_integrity"
down_revision = "0003_policy_immutability"
branch_labels = None
depends_on = None

_PAYMENT_STATES = (
    "ORDER_CREATED",
    "PAYMENT_PENDING",
    "PAYMENT_AUTHORIZED",
    "PAYMENT_CAPTURED",
    "PAYMENT_FAILED",
    "PAYMENT_UNKNOWN",
)


def upgrade() -> None:
    state_values = ", ".join(f"'{value}'" for value in _PAYMENT_STATES)
    op.create_check_constraint(
        "ck_payment_orders_state_valid",
        "payment_orders",
        f"state IN ({state_values})",
    )
    op.create_check_constraint(
        "ck_provider_payments_state_valid",
        "provider_payments",
        f"state IN ({state_values})",
    )

    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION preserve_captured_payment_state()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF OLD.state = 'PAYMENT_CAPTURED' AND NEW.state <> 'PAYMENT_CAPTURED' THEN
                    NEW.state := OLD.state;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER payment_orders_terminal_capture_guard
            BEFORE UPDATE OF state ON payment_orders
            FOR EACH ROW
            EXECUTE FUNCTION preserve_captured_payment_state();
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER provider_payments_terminal_capture_guard
            BEFORE UPDATE OF state ON provider_payments
            FOR EACH ROW
            EXECUTE FUNCTION preserve_captured_payment_state();
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS provider_payments_terminal_capture_guard ON provider_payments"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS payment_orders_terminal_capture_guard ON payment_orders"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS preserve_captured_payment_state()"))
    op.drop_constraint("ck_provider_payments_state_valid", "provider_payments", type_="check")
    op.drop_constraint("ck_payment_orders_state_valid", "payment_orders", type_="check")
