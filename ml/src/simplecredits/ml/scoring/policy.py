from __future__ import annotations

from dataclasses import dataclass, field

DECISION_APPROVE = "approve"
DECISION_APPROVE_WITH_CONDITIONS = "approve_with_conditions"
DECISION_MANUAL_REVIEW = "manual_review"
DECISION_DECLINE = "decline"

PD_DECLINE_THRESHOLD = 0.35
PD_REVIEW_THRESHOLD = 0.20
DEBT_SERVICE_REVIEW_THRESHOLD = 0.55
SEVERE_PAST_DUE_DAYS = 60
LOAN_TO_REVENUE_CONDITION_THRESHOLD = 0.60
MIN_AMOUNT_FOR_CONDITIONS_RUB = 3_000_000
MAX_LOAN_TO_REVENUE_AFTER_REDUCTION = 0.50


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reasons: tuple[str, ...] = field(default_factory=tuple)
    conditions: tuple[dict, ...] = field(default_factory=tuple)


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator) / max(float(denominator), 1.0)


def evaluate_policy(raw_row: dict, pd_value: float) -> PolicyDecision:
    requested_amount = float(raw_row.get("requested_amount_rub", 0) or 0)
    annual_revenue = float(raw_row.get("annual_revenue_rub", 0) or 0)
    monthly_revenue = float(raw_row.get("monthly_revenue_rub", 0) or 0)
    monthly_debt_payment = float(raw_row.get("monthly_debt_payments_rub", 0) or 0)
    max_days_past_due = int(raw_row.get("max_days_past_due_12m", 0) or 0)
    has_current_past_due = bool(raw_row.get("has_current_past_due", 0))

    if has_current_past_due:
        return PolicyDecision(
            decision=DECISION_DECLINE,
            reasons=("CURRENT_PAST_DUE",),
        )
    if max_days_past_due >= SEVERE_PAST_DUE_DAYS:
        return PolicyDecision(
            decision=DECISION_DECLINE,
            reasons=("SEVERE_PAST_DUE_HISTORY",),
        )
    if pd_value >= PD_DECLINE_THRESHOLD:
        return PolicyDecision(
            decision=DECISION_DECLINE,
            reasons=("HIGH_RISK_SCORE",),
        )
    if pd_value >= PD_REVIEW_THRESHOLD:
        return PolicyDecision(
            decision=DECISION_MANUAL_REVIEW,
            reasons=("RISK_IN_GREY_ZONE",),
        )

    debt_service_ratio = _ratio(monthly_debt_payment, monthly_revenue)
    if debt_service_ratio > DEBT_SERVICE_REVIEW_THRESHOLD:
        return PolicyDecision(
            decision=DECISION_MANUAL_REVIEW,
            reasons=("HIGH_DEBT_SERVICE_RATIO",),
        )

    loan_to_revenue = _ratio(requested_amount, annual_revenue)
    if (
        loan_to_revenue > LOAN_TO_REVENUE_CONDITION_THRESHOLD
        and requested_amount > MIN_AMOUNT_FOR_CONDITIONS_RUB
    ):
        recommended_amount = int(
            min(requested_amount, annual_revenue * MAX_LOAN_TO_REVENUE_AFTER_REDUCTION)
        )
        return PolicyDecision(
            decision=DECISION_APPROVE_WITH_CONDITIONS,
            reasons=("LOAN_TO_REVENUE_REDUCTION",),
            conditions=(
                {
                    "code": "REDUCE_AMOUNT",
                    "description": "Снизить сумму финансирования относительно запрошенной",
                    "recommended_amount_rub": recommended_amount,
                },
            ),
        )

    return PolicyDecision(decision=DECISION_APPROVE)
