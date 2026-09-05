from __future__ import annotations

import pytest

from app.investigation_service import EvidenceItem, ReadOnlyLLMProvider, build_evidence, evidence_digest


class Obj:
    pass


def test_evidence_digest_is_deterministic_and_provenance_preserving() -> None:
    first = [EvidenceItem("E1", "Decision", "risk_decisions", "AUTHORITATIVE", "BLOCK")]
    second = [EvidenceItem("E1", "Decision", "risk_decisions", "AUTHORITATIVE", "BLOCK")]
    assert evidence_digest(first) == evidence_digest(second)
    assert evidence_digest(first) != evidence_digest([EvidenceItem("E1", "Decision", "risk_decisions", "MODEL_SIGNAL", "BLOCK")])


def test_build_evidence_marks_authoritative_and_model_sources() -> None:
    tx = Obj()
    tx.amount = "100.00"
    tx.currency = "INR"
    tx.device_id = "device"
    decision = Obj()
    decision.decision = "VERIFY"
    decision.reason_codes = ["new_device"]
    prediction = Obj()
    prediction.score = "0.62"
    prediction.risk_band = "MEDIUM"
    prediction.model_version = "baseline-logistic-v1"
    policy = Obj()
    policy.result = "VERIFY"
    policy.violations = []
    features = Obj()
    features.values = {"new_device": 1}

    evidence = build_evidence(
        transaction=tx,
        decision=decision,
        prediction=prediction,
        policy_evaluation=policy,
        features=features,
        audits=[],
    )
    assert next(item for item in evidence if item.id == "E1").trust == "AUTHORITATIVE"
    assert next(item for item in evidence if item.id == "E2").trust == "MODEL_SIGNAL"
    assert next(item for item in evidence if item.id == "E10").trust == "DERIVED"


@pytest.mark.asyncio
async def test_unconfigured_llm_uses_deterministic_fallback() -> None:
    evidence = [EvidenceItem("E1", "Authoritative decision", "risk_decisions", "AUTHORITATIVE", "BLOCK")]
    result = await ReadOnlyLLMProvider().investigate(evidence=evidence, authoritative_decision="BLOCK")
    assert result.provider == "deterministic-fallback"
    assert result.status == "COMPLETED"
    assert "BLOCK" in result.summary
    assert result.evidence_hash == evidence_digest(evidence)
