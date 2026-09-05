from decimal import Decimal

from agentshield_api.risk import (
    Decision,
    PolicyContext,
    RiskAssessment,
    RiskBand,
    classify_score,
    decide,
    evaluate_policy,
)


def test_classify_score_boundaries() -> None:
    assert classify_score(Decimal("0.29")) is RiskBand.LOW
    assert classify_score(Decimal("0.30")) is RiskBand.MEDIUM
    assert classify_score(Decimal("0.69")) is RiskBand.MEDIUM
    assert classify_score(Decimal("0.70")) is RiskBand.HIGH


def test_hard_policy_violation_blocks_even_low_risk() -> None:
    result = evaluate_policy(
        PolicyContext(
            agent_active=True,
            amount=Decimal("1200.00"),
            transaction_limit=Decimal("1000.00"),
            daily_spent=Decimal("0"),
            daily_limit=Decimal("5000.00"),
            verification_threshold=Decimal("0.25"),
            category_allowed=True,
        ),
        version=7,
    )
    decision = decide(
        RiskAssessment(Decimal("0.01"), RiskBand.LOW, "test", []),
        result,
        Decimal("0.25"),
    )
    assert result.version == 7
    assert "TRANSACTION_LIMIT_EXCEEDED" in result.violations
    assert decision is Decision.BLOCK


def test_medium_risk_requires_verification() -> None:
    result = evaluate_policy(
        PolicyContext(
            agent_active=True,
            amount=Decimal("100.00"),
            transaction_limit=Decimal("1000.00"),
            daily_spent=Decimal("0"),
            daily_limit=Decimal("5000.00"),
            verification_threshold=Decimal("0.25"),
            category_allowed=True,
        ),
        version=1,
    )
    assert decide(
        RiskAssessment(Decimal("0.45"), RiskBand.MEDIUM, "test", []),
        result,
        Decimal("0.25"),
    ) is Decision.VERIFY


def test_low_risk_below_verification_threshold_allows() -> None:
    result = evaluate_policy(
        PolicyContext(
            agent_active=True,
            amount=Decimal("100.00"),
            transaction_limit=Decimal("1000.00"),
            daily_spent=Decimal("0"),
            daily_limit=Decimal("5000.00"),
            verification_threshold=Decimal("0.25"),
            category_allowed=True,
        ),
        version=1,
    )
    assert decide(
        RiskAssessment(Decimal("0.10"), RiskBand.LOW, "test", []),
        result,
        Decimal("0.25"),
    ) is Decision.ALLOW
