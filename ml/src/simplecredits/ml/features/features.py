from __future__ import annotations

import numpy as np
import pandas as pd

from simplecredits.ml.data.schema import CATEGORICAL_FEATURES, RAW_NUMERIC_FEATURES

NUMERIC_FEATURES = [
    "company_age_months",
    "employee_count",
    "okved_risk",
    "region_risk",
    "log_annual_revenue",
    "log_requested_amount",
    "term_months",
    "debt_to_revenue",
    "debt_service_ratio",
    "requested_to_annual_revenue",
    "profitability",
    "ebitda_margin",
    "cash_coverage",
    "expense_ratio",
    "log_revenue_per_employee",
    "max_days_past_due_12m",
    "has_current_past_due",
    "credit_utilization",
    "active_obligations_count",
    "applications_last_6m",
    "closed_obligations_ratio",
]

FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _safe_ratio(numerator: pd.Series, denominator: pd.Series, lower: float, upper: float) -> pd.Series:
    ratio = numerator.astype(float) / denominator.astype(float).clip(lower=1.0)
    return ratio.clip(lower=lower, upper=upper)


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES if column not in frame.columns]
    if missing:
        raise ValueError(f"missing raw features: {missing}")

    source = frame.copy()
    for column in RAW_NUMERIC_FEATURES:
        source[column] = pd.to_numeric(source[column], errors="coerce").fillna(0.0).astype(float)
    for column in CATEGORICAL_FEATURES:
        source[column] = source[column].fillna("other").astype(str)

    annual_revenue = source["annual_revenue_rub"].clip(lower=1.0)
    monthly_revenue = source["monthly_revenue_rub"].clip(lower=1.0)
    monthly_expenses = source["monthly_expenses_rub"].clip(lower=1.0)

    result = pd.DataFrame(index=source.index)
    result["company_age_months"] = source["company_age_months"].clip(lower=0.0, upper=480.0)
    result["employee_count"] = source["employee_count"].clip(lower=0.0, upper=2000.0)
    result["okved_risk"] = source["okved_risk"].clip(0.0, 1.0)
    result["region_risk"] = source["region_risk"].clip(0.0, 1.0)
    result["log_annual_revenue"] = np.log1p(annual_revenue)
    result["log_requested_amount"] = np.log1p(source["requested_amount_rub"].clip(lower=0.0))
    result["term_months"] = source["term_months"].clip(lower=1.0, upper=120.0)
    result["debt_to_revenue"] = _safe_ratio(source["total_debt_rub"], annual_revenue, 0.0, 10.0)
    result["debt_service_ratio"] = _safe_ratio(
        source["monthly_debt_payments_rub"], monthly_revenue, 0.0, 3.0
    )
    result["requested_to_annual_revenue"] = _safe_ratio(
        source["requested_amount_rub"], annual_revenue, 0.0, 10.0
    )
    result["profitability"] = _safe_ratio(
        source["annual_net_profit_rub"], annual_revenue, -1.0, 1.0
    )
    result["ebitda_margin"] = _safe_ratio(source["ebitda_rub"], annual_revenue, -1.0, 1.0)
    result["cash_coverage"] = _safe_ratio(
        source["cash_balance_rub"] + source["accounts_receivable_rub"],
        3.0 * monthly_expenses,
        0.0,
        20.0,
    )
    result["expense_ratio"] = _safe_ratio(
        source["monthly_expenses_rub"], monthly_revenue, 0.0, 2.0
    )
    result["log_revenue_per_employee"] = np.log1p(
        monthly_revenue / source["employee_count"].clip(lower=1.0)
    )
    result["max_days_past_due_12m"] = source["max_days_past_due_12m"].clip(0.0, 365.0)
    result["has_current_past_due"] = (source["has_current_past_due"] > 0).astype(float)
    result["credit_utilization"] = source["credit_utilization"].clip(0.0, 1.0)
    result["active_obligations_count"] = source["active_obligations_count"].clip(0.0, 50.0)
    result["applications_last_6m"] = source["applications_last_6m"].clip(0.0, 50.0)
    result["closed_obligations_ratio"] = _safe_ratio(
        source["closed_obligations_count"],
        source["closed_obligations_count"] + source["active_obligations_count"] + 1.0,
        0.0,
        1.0,
    )

    for column in CATEGORICAL_FEATURES:
        result[column] = source[column]

    return result[FEATURE_COLUMNS]
