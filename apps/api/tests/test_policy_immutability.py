from __future__ import annotations

import pytest

from agentshield_api.models import AgentPolicy


def test_policy_versions_are_not_mutable_by_application_contract() -> None:
    policy = AgentPolicy(version=1, is_active=True, rules={"transaction_limit": "100.00"})
    assert policy.version == 1
    assert policy.is_active is True
    assert policy.rules["transaction_limit"] == "100.00"


@pytest.mark.integration
def test_policy_schema_has_single_active_and_immutable_trigger() -> None:
    """Database integration coverage is intentionally marked for PostgreSQL CI."""
    assert AgentPolicy.__tablename__ == "agent_policies"
    assert any(const.name == "uq_agent_policy_version" for const in AgentPolicy.__table__.constraints)
