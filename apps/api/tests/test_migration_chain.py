from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    heads = scripts.get_heads()
    assert heads == ["0007_terminal_capture_immutable"]


def test_migration_chain_is_linear() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    expected_chain = {
        "0007_terminal_capture_immutable": "0006_single_active_model",
        "0006_single_active_model": "0005_payment_state_monotonic",
        "0005_payment_state_monotonic": "0004_payment_state_integrity",
        "0004_payment_state_integrity": "0003_policy_immutability",
        "0003_policy_immutability": "0002_risk_ai_payment_schema",
        "0002_risk_ai_payment_schema": "0001_core_schema",
        "0001_core_schema": None,
    }
    for revision_id, expected_parent in expected_chain.items():
        revision = scripts.get_revision(revision_id)
        assert revision is not None
        assert revision.down_revision == expected_parent
