import pytest

from services.scoring import decision_to_status


@pytest.mark.parametrize("decision,product_type,expected", [
    ("approve", "term_loan", "confirmed"),
    ("approve", None, "different"),
    ("approve_with_conditions", "term_loan", "different"),
    ("approve_with_conditions", None, "different"),
    ("manual_review", "term_loan", "different"),
    ("manual_review", None, "different"),
    ("decline", "term_loan", "declined"),
    ("decline", None, "declined"),
])
def test_decision_to_status_known(decision, product_type, expected):
    """Все известные decision мапятся корректно"""
    assert decision_to_status(decision, product_type) == expected


def test_decision_to_status_none():
    """decision=None → failed"""
    assert decision_to_status(None, "term_loan") == "failed"


def test_decision_to_status_unknown():
    """Неизвестный decision → failed"""
    assert decision_to_status("unknown", "term_loan") == "failed"