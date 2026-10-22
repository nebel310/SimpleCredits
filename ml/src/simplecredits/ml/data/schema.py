from __future__ import annotations

from typing import Any

TARGET_COLUMN = "default"

RAW_NUMERIC_FEATURES = [
    "company_age_months",
    "employee_count",
    "okved_risk",
    "region_risk",
    "annual_revenue_rub",
    "annual_net_profit_rub",
    "ebitda_rub",
    "total_debt_rub",
    "monthly_revenue_rub",
    "monthly_expenses_rub",
    "accounts_receivable_rub",
    "cash_balance_rub",
    "requested_amount_rub",
    "term_months",
    "active_obligations_count",
    "total_outstanding_rub",
    "monthly_debt_payments_rub",
    "max_days_past_due_12m",
    "has_current_past_due",
    "credit_utilization",
    "closed_obligations_count",
    "applications_last_6m",
]

CATEGORICAL_FEATURES = ["product_type", "purpose"]

RAW_FEATURES = RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES

PRODUCT_TYPES = ["microloan", "term_loan", "overdraft", "credit_line", "leasing"]

FINANCING_PURPOSES = [
    "working_capital",
    "equipment",
    "expansion",
    "refinancing",
    "other",
]

DEFAULT_RAW_ROW: dict[str, Any] = {
    "company_age_months": 36,
    "employee_count": 5,
    "okved_risk": 0.4,
    "region_risk": 0.3,
    "annual_revenue_rub": 12_000_000,
    "annual_net_profit_rub": 1_200_000,
    "ebitda_rub": 1_800_000,
    "total_debt_rub": 2_000_000,
    "monthly_revenue_rub": 1_000_000,
    "monthly_expenses_rub": 850_000,
    "accounts_receivable_rub": 600_000,
    "cash_balance_rub": 400_000,
    "requested_amount_rub": 1_000_000,
    "term_months": 12,
    "active_obligations_count": 1,
    "total_outstanding_rub": 500_000,
    "monthly_debt_payments_rub": 45_000,
    "max_days_past_due_12m": 0,
    "has_current_past_due": 0,
    "credit_utilization": 0.25,
    "closed_obligations_count": 2,
    "applications_last_6m": 1,
    "product_type": "term_loan",
    "purpose": "working_capital",
}


def normalize_raw_row(row: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(DEFAULT_RAW_ROW)
    if row:
        for key, value in row.items():
            if key in DEFAULT_RAW_ROW and value is not None:
                result[key] = value
    return result
