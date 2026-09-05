from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_single_head() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    heads = scripts.get_heads()
    assert heads == ["0003_policy_immutability"]


def test_migration_chain_is_linear() -> None:
    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "migrations"))
    scripts = ScriptDirectory.from_config(config)

    head = scripts.get_revision("0003_policy_immutability")
    assert head is not None
    assert head.down_revision == "0002_risk_ai_payment_schema"

    revision = scripts.get_revision("0002_risk_ai_payment_schema")
    assert revision is not None
    assert revision.down_revision == "0001_core_schema"

    root = scripts.get_revision("0001_core_schema")
    assert root is not None
    assert root.down_revision is None
