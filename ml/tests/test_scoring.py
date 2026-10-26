import pytest

from simplecredits.ml.scoring.model import CreditScorer, pd_to_risk_grade, pd_to_score

GOOD_APPLICATION = {
    "company_age_months": 120,
    "employee_count": 30,
    "okved_risk": 0.15,
    "region_risk": 0.10,
    "annual_revenue_rub": 120_000_000,
    "annual_net_profit_rub": 18_000_000,
    "ebitda_rub": 24_000_000,
    "total_debt_rub": 10_000_000,
    "monthly_revenue_rub": 10_000_000,
    "monthly_expenses_rub": 7_500_000,
    "accounts_receivable_rub": 4_000_000,
    "cash_balance_rub": 5_000_000,
    "requested_amount_rub": 3_000_000,
    "term_months": 24,
    "active_obligations_count": 1,
    "total_outstanding_rub": 2_000_000,
    "monthly_debt_payments_rub": 150_000,
    "max_days_past_due_12m": 0,
    "has_current_past_due": 0,
    "credit_utilization": 0.20,
    "closed_obligations_count": 5,
    "applications_last_6m": 0,
    "product_type": "term_loan",
    "purpose": "equipment",
}

BAD_APPLICATION = {
    "company_age_months": 6,
    "employee_count": 2,
    "okved_risk": 0.90,
    "region_risk": 0.85,
    "annual_revenue_rub": 1_200_000,
    "annual_net_profit_rub": -100_000,
    "ebitda_rub": -50_000,
    "total_debt_rub": 2_000_000,
    "monthly_revenue_rub": 100_000,
    "monthly_expenses_rub": 95_000,
    "accounts_receivable_rub": 20_000,
    "cash_balance_rub": 10_000,
    "requested_amount_rub": 5_000_000,
    "term_months": 60,
    "active_obligations_count": 5,
    "total_outstanding_rub": 1_800_000,
    "monthly_debt_payments_rub": 80_000,
    "max_days_past_due_12m": 45,
    "has_current_past_due": 1,
    "credit_utilization": 0.95,
    "closed_obligations_count": 0,
    "applications_last_6m": 5,
    "product_type": "microloan",
    "purpose": "refinancing",
}


def test_score_is_bounded(scorer):
    result = scorer.score(GOOD_APPLICATION)
    assert 0 <= result.score <= 1000
    assert 0.0 <= result.pd <= 1.0
    assert result.risk_grade in {"A", "B", "C", "D", "E"}


def test_bad_application_scores_worse(scorer):
    good = scorer.score(GOOD_APPLICATION)
    bad = scorer.score(BAD_APPLICATION)
    assert good.pd < bad.pd
    assert good.score > bad.score


def test_reason_codes_are_explainable(scorer):
    result = scorer.score(GOOD_APPLICATION)
    assert result.reasons
    for reason in result.reasons:
        assert reason["code"]
        assert reason["description"]
        assert reason["impact"] in {"positive", "negative", "neutral"}
        assert isinstance(reason["contribution"], float)


def test_policy_is_applied(scorer):
    good = scorer.score(GOOD_APPLICATION)
    bad = scorer.score(BAD_APPLICATION)
    assert good.policy.decision == "approve"
    assert bad.policy.decision == "decline"


def test_grade_and_score_mapping():
    assert pd_to_risk_grade(0.01) == "A"
    assert pd_to_risk_grade(0.19) == "D"
    assert pd_to_risk_grade(0.50) == "E"
    assert pd_to_score(0.0) == 1000
    assert pd_to_score(1.0) == 0


@pytest.mark.parametrize(
    ("pd_value", "grade"),
    [
        (0.0, "A"),
        (0.0199, "A"),
        (0.02, "B"),
        (0.0499, "B"),
        (0.05, "C"),
        (0.0999, "C"),
        (0.10, "D"),
        (0.1999, "D"),
        (0.20, "E"),
        (2.0, "E"),
    ],
)
def test_risk_grade_thresholds(pd_value, grade):
    assert pd_to_risk_grade(pd_value) == grade


def test_score_mapping_clamps_and_rounds():
    assert pd_to_score(-0.5) == 1000
    assert pd_to_score(1.5) == 0
    assert pd_to_score(0.1234) == 877


def test_artifact_requires_model_or_pipeline():
    with pytest.raises(ValueError, match="either model or pipeline"):
        CreditScorer({})


def test_model_info_uses_artifact_defaults():
    scorer = CreditScorer({"model": object()})
    info = scorer.model_info()

    assert info["model_version"] == "unknown"
    assert info["model_type"] == "logistic_scorecard"
    assert info["trained_at"] is None
    assert info["metrics"] == {}
    assert info["feature_columns"] == []
    assert info["training"] == {}
