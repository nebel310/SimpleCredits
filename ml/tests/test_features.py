import numpy as np
import pandas as pd

from simplecredits.ml.data.generator import generate_dataset
from simplecredits.ml.data.schema import DEFAULT_RAW_ROW
from simplecredits.ml.features.features import FEATURE_COLUMNS, build_features


def test_build_features_has_expected_columns_and_no_invalid_values():
    frame = generate_dataset(n_samples=500, seed=5)
    features = build_features(frame)
    assert list(features.columns) == FEATURE_COLUMNS
    assert not features.isna().any().any()
    numeric = features.select_dtypes(include="number")
    assert np.isfinite(numeric.to_numpy()).all()


def test_build_features_handles_zero_denominators():
    row = {
        **DEFAULT_RAW_ROW,
        "company_age_months": 12,
        "employee_count": 0,
        "okved_risk": 0.5,
        "region_risk": 0.5,
        "annual_revenue_rub": 0,
        "annual_net_profit_rub": 0,
        "ebitda_rub": 0,
        "total_debt_rub": 0,
        "monthly_revenue_rub": 0,
        "monthly_expenses_rub": 0,
        "accounts_receivable_rub": 0,
        "cash_balance_rub": 0,
        "requested_amount_rub": 0,
        "term_months": 12,
        "active_obligations_count": 0,
        "total_outstanding_rub": 0,
        "monthly_debt_payments_rub": 0,
        "max_days_past_due_12m": 0,
        "has_current_past_due": 0,
        "credit_utilization": 0,
        "closed_obligations_count": 0,
        "applications_last_6m": 0,
        "product_type": "term_loan",
        "purpose": "working_capital",
    }
    features = build_features(pd.DataFrame([row]))
    assert np.isfinite(features.select_dtypes(include="number").to_numpy()).all()
