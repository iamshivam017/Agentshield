from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.model_routes import _validate_transition


def test_model_lifecycle_requires_approved_sequence() -> None:
    _validate_transition("TRAINED", "EVALUATED")
    _validate_transition("EVALUATED", "CANDIDATE")
    _validate_transition("CANDIDATE", "APPROVED")
    _validate_transition("APPROVED", "ACTIVE")
    _validate_transition("ACTIVE", "RETIRED")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("TRAINED", "ACTIVE"),
        ("EVALUATED", "APPROVED"),
        ("CANDIDATE", "ACTIVE"),
        ("APPROVED", "RETIRED"),
        ("RETIRED", "ACTIVE"),
        ("ACTIVE", "APPROVED"),
    ],
)
def test_model_lifecycle_rejects_skipped_or_regressive_transitions(current: str, target: str) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_transition(current, target)
    assert exc_info.value.status_code == 409
