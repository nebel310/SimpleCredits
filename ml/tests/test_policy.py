from simplecredits.ml.scoring.policy import (
    DECISION_APPROVE,
    DECISION_APPROVE_WITH_CONDITIONS,
    DECISION_DECLINE,
    DECISION_MANUAL_REVIEW,
    evaluate_policy,
)


def base_row(**overrides):
    row = {
        "requested_amount_rub": 1_000_000,
        "annual_revenue_rub": 12_000_000,
        "monthly_revenue_rub": 1_000_000,
        "monthly_debt_payments_rub": 50_000,
        "max_days_past_due_12m": 0,
        "has_current_past_due": 0,
    }
    row.update(overrides)
    return row


def test_declines_on_current_past_due():
    decision = evaluate_policy(base_row(has_current_past_due=1), pd_value=0.01)
    assert decision.decision == DECISION_DECLINE
    assert "CURRENT_PAST_DUE" in decision.reasons


def test_declines_on_severe_past_due_history():
    decision = evaluate_policy(base_row(max_days_past_due_12m=90), pd_value=0.01)
    assert decision.decision == DECISION_DECLINE
    assert "SEVERE_PAST_DUE_HISTORY" in decision.reasons


def test_declines_on_high_pd():
    decision = evaluate_policy(base_row(), pd_value=0.5)
    assert decision.decision == DECISION_DECLINE


def test_sends_grey_zone_to_manual_review():
    decision = evaluate_policy(base_row(), pd_value=0.25)
    assert decision.decision == DECISION_MANUAL_REVIEW


def test_reviews_high_debt_service_ratio():
    decision = evaluate_policy(base_row(monthly_debt_payments_rub=700_000), pd_value=0.05)
    assert decision.decision == DECISION_MANUAL_REVIEW


def test_offers_reduced_amount_for_high_loan_to_revenue():
    decision = evaluate_policy(
        base_row(requested_amount_rub=9_000_000, annual_revenue_rub=10_000_000),
        pd_value=0.03,
    )
    assert decision.decision == DECISION_APPROVE_WITH_CONDITIONS
    assert decision.conditions[0]["recommended_amount_rub"] == 5_000_000


def test_approves_healthy_application():
    decision = evaluate_policy(base_row(), pd_value=0.02)
    assert decision.decision == DECISION_APPROVE
