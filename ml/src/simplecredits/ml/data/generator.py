from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    FINANCING_PURPOSES,
    HISTORY_NUMERIC_FEATURES,
    NEW_NUMERIC_FEATURES,
    PRODUCT_TYPES,
    RAW_NUMERIC_FEATURES,
    TARGET_COLUMN,
)


def _clip(values: np.ndarray, low: float, high: float) -> np.ndarray:
    return np.clip(values, low, high)


def _sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def _calibrated_intercept(
    risk: np.ndarray, target_rate: float, low: float = -20.0, high: float = 20.0
) -> float:
    for _ in range(100):
        middle = (low + high) / 2.0
        rate = float(_sigmoid(risk + middle).mean())
        if rate > target_rate:
            high = middle
        else:
            low = middle
    return (low + high) / 2.0


def _count(rng, n_samples: int, lam: float, upper: float) -> np.ndarray:
    return np.clip(rng.poisson(lam, size=n_samples), 0, upper).astype(float)


def _ratio(rng, n_samples: int, low: float, high: float) -> np.ndarray:
    return _clip(rng.beta(2.0, 3.0, size=n_samples) * (high - low) + low, low, high)


def _new_feature_data(
    rng,
    n_samples: int,
    annual_revenue_rub: np.ndarray,
    monthly_revenue_rub: np.ndarray,
    annual_net_profit_rub: np.ndarray,
    total_debt_rub: np.ndarray,
    employee_count: np.ndarray,
    company_age_months: np.ndarray,
    credit_utilization: np.ndarray,
    has_current_past_due: np.ndarray,
) -> dict[str, np.ndarray]:
    data: dict[str, np.ndarray] = {}
    for name in NEW_NUMERIC_FEATURES:
        if name.endswith("_flag"):
            data[name] = (rng.random(n_samples) < 0.18).astype(float)
        elif name.endswith(("_count", "_visits", "_followers", "_orders", "_outlets", "_headcount")):
            data[name] = _count(rng, n_samples, 3.0, 100_000)
        elif name.endswith(("_share", "_ratio", "_rate", "_margin", "_conversion", "_quality", "_score", "_engagement", "_delinquency")):
            data[name] = _ratio(rng, n_samples, 0.0, 1.0)
        elif name.endswith(("_days", "_months")):
            data[name] = _clip(rng.gamma(2.0, 20.0, size=n_samples), 0.0, 3600.0)
        elif name.endswith(("_to_annual", "_to_revenue", "_to_monthly_revenue", "_per_employee")):
            data[name] = _clip(rng.lognormal(-2.0, 1.0, size=n_samples), 0.0, 10.0)
        elif name.startswith("log_"):
            data[name] = rng.normal(8.0, 2.0, size=n_samples)
        else:
            data[name] = rng.normal(0.0, 1.0, size=n_samples)

    data["user_count"] = _count(rng, n_samples, 3.0, 20)
    data["founder_count"] = _count(rng, n_samples, 1.5, 10)
    data["max_founder_share"] = _ratio(rng, n_samples, 0.1, 1.0)
    data["manager_count"] = _count(rng, n_samples, 1.2, 10)
    data["consent_count"] = _count(rng, n_samples, 4.0, 30)
    data["tax_report_count"] = _count(rng, n_samples, 8.0, 100)
    data["tax_paid_ratio"] = _ratio(rng, n_samples, 0.2, 1.0)
    data["tax_debt_ratio"] = _ratio(rng, n_samples, 0.0, 0.8)
    data["sfr_employee_ratio"] = _ratio(rng, n_samples, 0.2, 1.5)
    data["payroll_per_employee"] = _clip(rng.normal(60_000, 20_000, n_samples), 10_000, 300_000)
    data["sfr_debt_ratio"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["rosstat_revenue_to_annual"] = _ratio(rng, n_samples, 0.1, 2.0)
    data["rosstat_revenue_growth"] = rng.normal(0.05, 0.15, n_samples)
    data["statement_count"] = _count(rng, n_samples, 3.0, 20)
    data["equity_ratio"] = _ratio(rng, n_samples, 0.05, 0.9)
    data["current_ratio"] = _clip(rng.lognormal(0.7, 0.6, n_samples), 0.1, 20.0)
    data["debt_to_equity"] = _clip(rng.lognormal(0.2, 0.8, n_samples), 0.0, 20.0)
    data["revenue_growth_yoy"] = rng.normal(0.08, 0.2, n_samples)
    data["inventory_ratio"] = _ratio(rng, n_samples, 0.0, 0.6)
    data["interest_coverage"] = _clip(rng.lognormal(1.0, 0.8, n_samples), 0.0, 50.0)
    data["account_count"] = _count(rng, n_samples, 2.0, 20)
    data["account_age_months"] = _clip(rng.gamma(3.0, 20.0, n_samples), 0.0, 480.0)
    data["txn_counterparty_count"] = _count(rng, n_samples, 20.0, 500)
    data["txn_cash_share"] = _ratio(rng, n_samples, 0.0, 0.8)
    data["txn_tax_share"] = _ratio(rng, n_samples, 0.0, 0.3)
    data["txn_loan_payment_share"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["txn_salary_share"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["product_count"] = _count(rng, n_samples, 2.0, 20)
    data["loan_product_count"] = _count(rng, n_samples, 1.2, 20)
    data["overdue_product_count"] = _count(rng, n_samples, 0.2, 10)
    data["bki_loan_count"] = _count(rng, n_samples, 2.0, 20)
    data["bki_active_loan_count"] = _count(rng, n_samples, 1.2, 20)
    data["bki_closed_ratio"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["bki_collateralized_share"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["bki_dpd_ratio"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["court_defendant_count"] = _count(rng, n_samples, 0.3, 20)
    data["court_recent_count"] = _count(rng, n_samples, 0.2, 20)
    data["enforcement_active_count"] = _count(rng, n_samples, 0.2, 20)
    data["license_count"] = _count(rng, n_samples, 0.5, 10)
    data["tender_count"] = _count(rng, n_samples, 0.8, 20)
    data["tender_win_rate"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["insurance_coverage_to_revenue"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["insurance_premium_to_revenue"] = _ratio(rng, n_samples, 0.0, 0.1)
    data["telematics_mileage"] = _clip(rng.gamma(3.0, 5_000.0, n_samples), 0.0, 500_000)
    data["telematics_harsh_events"] = _count(rng, n_samples, 3.0, 500)
    data["iot_alert_count"] = _count(rng, n_samples, 1.0, 100)
    data["accounting_entry_count"] = _count(rng, n_samples, 20.0, 500)
    data["marketplace_orders"] = _count(rng, n_samples, 50.0, 10_000)
    data["marketplace_return_rate"] = _ratio(rng, n_samples, 0.0, 0.3)
    data["marketplace_rating"] = _ratio(rng, n_samples, 1.0, 5.0)
    data["ofd_receipt_count"] = _count(rng, n_samples, 50.0, 10_000)
    data["warehouse_turnover_days"] = _clip(rng.gamma(2.0, 20.0, n_samples), 0.0, 365.0)
    data["website_visits"] = _count(rng, n_samples, 1_000.0, 1_000_000)
    data["website_conversion"] = _ratio(rng, n_samples, 0.0, 0.2)
    data["domain_age_months"] = _clip(rng.gamma(2.0, 30.0, n_samples), 0.0, 480.0)
    data["reputation_rating"] = _ratio(rng, n_samples, 1.0, 5.0)
    data["negative_review_share"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["hr_headcount"] = _count(rng, n_samples, 20.0, 2_000)
    data["hr_turnover"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["hr_vacancy_rate"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["logistics_delivery_days"] = _clip(rng.gamma(2.0, 2.0, n_samples), 0.0, 30.0)
    data["utilities_debt_ratio"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["mobile_tenure_months"] = _clip(rng.gamma(2.0, 30.0, n_samples), 0.0, 360.0)
    data["social_followers"] = _count(rng, n_samples, 2_000.0, 1_000_000)
    data["social_engagement"] = _ratio(rng, n_samples, 0.0, 0.2)
    data["franchise_outlets"] = _count(rng, n_samples, 0.5, 20)
    data["certification_count"] = _count(rng, n_samples, 1.0, 20)
    data["industry_membership_count"] = _count(rng, n_samples, 0.5, 10)
    data["customs_declaration_count"] = _count(rng, n_samples, 2.0, 100)
    data["intellectual_property_count"] = _count(rng, n_samples, 0.5, 20)
    data["gosuslugi_event_count"] = _count(rng, n_samples, 2.0, 50)
    data["geo_reviews_count"] = _count(rng, n_samples, 50.0, 10_000)
    data["prior_application_count"] = _count(rng, n_samples, 1.0, 20)
    data["prior_approval_rate"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["prior_decline_rate"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["prior_offer_acceptance_rate"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["prior_contract_count"] = _count(rng, n_samples, 0.8, 20)
    data["prior_scoring_pd_mean"] = _ratio(rng, n_samples, 0.0, 0.5)
    data["prior_scoring_score_mean"] = _ratio(rng, n_samples, 0.0, 1.0) * 1000.0
    data["document_count"] = _count(rng, n_samples, 3.0, 50)
    data["verified_document_share"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["rejected_document_share"] = _ratio(rng, n_samples, 0.0, 0.3)
    data["prior_application_event_count"] = _count(rng, n_samples, 4.0, 100)
    data["prior_time_to_decision_days"] = _clip(rng.gamma(2.0, 1.0, n_samples), 0.0, 30.0)
    data["collateral_offer_count"] = _count(rng, n_samples, 0.5, 10)
    data["collateral_coverage_ratio"] = _ratio(rng, n_samples, 0.0, 3.0)
    data["audit_event_count"] = _count(rng, n_samples, 5.0, 100)
    data["audit_last_event_days"] = _clip(rng.gamma(2.0, 20.0, n_samples), 0.0, 730.0)
    data["applicant_age_years"] = _clip(rng.normal(40.0, 10.0, n_samples), 18.0, 80.0)
    data["applicant_consent_count"] = _count(rng, n_samples, 3.0, 20)
    data["applicant_biometric_success_rate"] = _ratio(rng, n_samples, 0.0, 1.0)
    data["applicant_biometric_liveness_score"] = _ratio(rng, n_samples, 0.7, 1.0)
    data["employee_ratio_proxy"] = employee_count / np.maximum(company_age_months, 1.0)
    for name in HISTORY_NUMERIC_FEATURES:
        data[name] = np.zeros(n_samples)
    return data


def generate_dataset(
    n_samples: int = 20_000,
    seed: int = 42,
    target_default_rate: float = 0.14,
) -> pd.DataFrame:
    if n_samples < 100:
        raise ValueError("n_samples must be at least 100")

    rng = np.random.default_rng(seed)

    product_type = rng.choice(PRODUCT_TYPES, size=n_samples, p=[0.30, 0.34, 0.10, 0.16, 0.10])
    purpose = rng.choice(
        FINANCING_PURPOSES, size=n_samples, p=[0.42, 0.22, 0.14, 0.12, 0.10]
    )
    company_segment = rng.choice(["micro", "small", "medium"], size=n_samples, p=[0.55, 0.30, 0.15])
    legal_form = rng.choice(["llc", "ip", "jsc"], size=n_samples, p=[0.65, 0.25, 0.10])
    tax_regime = rng.choice(["osn", "usn", "patent", "eshn"], size=n_samples, p=[0.35, 0.45, 0.15, 0.05])
    client_rating = rng.choice(["A", "B", "C", "D", "E"], size=n_samples, p=[0.20, 0.35, 0.25, 0.15, 0.05])

    company_age_months = np.clip(rng.gamma(shape=2.2, scale=32.0, size=n_samples), 1, 360).astype(int)
    employee_count = np.clip(rng.lognormal(mean=1.6, sigma=1.0, size=n_samples), 1, 800).astype(int)
    okved_risk = rng.beta(2.0, 3.0, size=n_samples)
    region_risk = rng.beta(2.0, 5.0, size=n_samples)

    annual_revenue_rub = _clip(
        rng.lognormal(mean=15.2, sigma=1.15, size=n_samples), 500_000, 3_000_000_000
    ).round().astype(np.int64)
    revenue_noise = _clip(rng.normal(1.0, 0.12, size=n_samples), 0.6, 1.4)
    monthly_revenue_rub = (annual_revenue_rub / 12.0 * revenue_noise).round().astype(np.int64)

    margin = _clip(rng.normal(0.08, 0.08, size=n_samples), -0.25, 0.40)
    annual_net_profit_rub = (annual_revenue_rub * margin).round().astype(np.int64)
    ebitda_margin = _clip(margin + rng.normal(0.03, 0.02, size=n_samples), -0.20, 0.45)
    ebitda_rub = (annual_revenue_rub * ebitda_margin).round().astype(np.int64)

    debt_ratio = _clip(rng.lognormal(mean=-1.3, sigma=0.95, size=n_samples), 0.0, 8.0)
    total_debt_rub = (annual_revenue_rub * debt_ratio).round().astype(np.int64)
    monthly_expenses_rub = (
        monthly_revenue_rub * _clip(rng.normal(0.82, 0.12, size=n_samples), 0.50, 1.15)
    ).round().astype(np.int64)
    accounts_receivable_rub = (
        monthly_revenue_rub * _clip(rng.normal(0.60, 0.30, size=n_samples), 0.05, 2.00)
    ).round().astype(np.int64)
    cash_balance_rub = (
        monthly_revenue_rub * _clip(rng.lognormal(-0.9, 0.6, size=n_samples), 0.0, 5.0)
    ).round().astype(np.int64)

    requests_per_revenue = _clip(rng.uniform(0.4, 5.5, size=n_samples), 0.2, 6.0)
    requested_amount_rub = _clip(
        monthly_revenue_rub * requests_per_revenue, 50_000, 50_000_000
    ).round().astype(np.int64)
    term_months = rng.choice([6, 12, 24, 36, 60], size=n_samples, p=[0.15, 0.30, 0.20, 0.20, 0.15])

    active_obligations_count = rng.poisson(1.8, size=n_samples)
    closed_obligations_count = rng.poisson(2.5, size=n_samples)
    total_outstanding_rub = (
        total_debt_rub * _clip(rng.uniform(0.35, 0.95, size=n_samples), 0.1, 1.0)
    ).round().astype(np.int64)
    monthly_debt_payments_rub = (
        total_debt_rub / 36.0 * _clip(rng.normal(1.0, 0.25, size=n_samples), 0.5, 2.0)
    ).round().astype(np.int64)

    credit_utilization = _clip(rng.beta(2.0, 3.0, size=n_samples), 0.0, 1.0)
    applications_last_6m = rng.poisson(1.2, size=n_samples)

    debt_to_revenue = total_debt_rub / np.maximum(annual_revenue_rub, 1)
    debt_service_ratio = monthly_debt_payments_rub / np.maximum(monthly_revenue_rub, 1)
    current_past_due_probability = _clip(
        0.03 + 0.14 * credit_utilization + 0.06 * _clip(debt_to_revenue, 0, 3) / 3.0,
        0.01,
        0.55,
    )
    has_current_past_due = (rng.random(n_samples) < current_past_due_probability).astype(int)
    historical_days = rng.choice([0, 5, 15, 30, 60], size=n_samples, p=[0.78, 0.09, 0.06, 0.04, 0.03])
    current_days = rng.choice([5, 15, 30, 45, 60, 90], size=n_samples, p=[0.38, 0.25, 0.17, 0.10, 0.06, 0.04])
    max_days_past_due_12m = np.where(has_current_past_due == 1, current_days, historical_days).astype(int)

    tax_debt_rub = (
        annual_revenue_rub * _clip(rng.beta(1.5, 8.0, size=n_samples) * 0.08, 0.0, 0.08)
    ).round().astype(np.int64)
    unpaid_tax_count = rng.poisson(0.4, size=n_samples)
    blocked_accounts_count = (rng.random(n_samples) < 0.03).astype(int)
    late_payments_12m = rng.poisson(0.8, size=n_samples)
    active_enforcement_count = rng.poisson(0.2, size=n_samples)
    enforcement_amount_rub = (annual_revenue_rub * rng.beta(1.2, 20.0, size=n_samples) * 0.05).round().astype(np.int64)
    court_cases_count = rng.poisson(0.3, size=n_samples)
    court_claims_rub = (annual_revenue_rub * rng.beta(1.2, 25.0, size=n_samples) * 0.06).round().astype(np.int64)
    historical_bankruptcy_flag = (rng.random(n_samples) < 0.02).astype(int)
    bki_credit_score = _clip(
        700.0 - 250.0 * credit_utilization - 40.0 * has_current_past_due + rng.normal(0, 40, n_samples),
        300.0,
        900.0,
    ).astype(int)
    fraud_flag = (rng.random(n_samples) < 0.01).astype(int)
    txn_inflow_90d = (monthly_revenue_rub * rng.uniform(2.4, 3.6, n_samples)).round().astype(np.int64)
    txn_outflow_90d = (txn_inflow_90d * rng.uniform(0.55, 1.05, n_samples)).round().astype(np.int64)
    txn_inflow_180d = (txn_inflow_90d * rng.uniform(1.8, 2.2, n_samples)).round().astype(np.int64)
    txn_outflow_180d = (txn_outflow_90d * rng.uniform(1.8, 2.2, n_samples)).round().astype(np.int64)
    txn_net_90d = txn_inflow_90d - txn_outflow_90d
    txn_count_90d = rng.poisson(90, size=n_samples)
    txn_balance_latest = (monthly_revenue_rub * rng.uniform(0.05, 0.60, n_samples)).round().astype(np.int64)

    new_features = _new_feature_data(
        rng,
        n_samples,
        annual_revenue_rub,
        monthly_revenue_rub,
        annual_net_profit_rub,
        total_debt_rub,
        employee_count,
        company_age_months,
        credit_utilization,
        has_current_past_due,
    )

    product_effect = {
        "microloan": 0.20,
        "term_loan": -0.10,
        "overdraft": 0.40,
        "credit_line": 0.10,
        "leasing": -0.20,
    }
    purpose_effect = {
        "working_capital": 0.10,
        "equipment": -0.10,
        "expansion": 0.20,
        "refinancing": 0.30,
        "other": 0.10,
    }
    product_component = np.array([product_effect[value] for value in product_type])
    purpose_component = np.array([purpose_effect[value] for value in purpose])

    profitability = annual_net_profit_rub / np.maximum(annual_revenue_rub, 1)
    cash_coverage = (cash_balance_rub + accounts_receivable_rub) / np.maximum(
        3.0 * monthly_expenses_rub, 1.0
    )
    requested_to_revenue = requested_amount_rub / np.maximum(annual_revenue_rub, 1)

    risk = (
        product_component
        + purpose_component
        + 1.6 * okved_risk
        + 1.2 * region_risk
        - 0.45 * np.log1p(company_age_months)
        - 0.15 * np.log1p(employee_count)
        + 2.0 * _clip(debt_to_revenue, 0, 5)
        + 3.5 * _clip(debt_service_ratio, 0, 2)
        + 0.012 * max_days_past_due_12m
        + 1.5 * has_current_past_due
        + 1.3 * credit_utilization
        + 0.18 * applications_last_6m
        - 2.2 * profitability
        - 0.35 * _clip(cash_coverage, 0, 10)
        + 1.0 * _clip(requested_to_revenue, 0, 5)
    )
    risk = risk + rng.normal(0.0, 0.45, size=n_samples)

    intercept = _calibrated_intercept(risk, target_default_rate)
    default_probability = _sigmoid(risk + intercept)
    target = (rng.random(n_samples) < default_probability).astype(int)

    data: dict[str, np.ndarray | pd.Series] = {
        "company_age_months": company_age_months,
        "employee_count": employee_count,
        "okved_risk": okved_risk.round(4),
        "region_risk": region_risk.round(4),
        "annual_revenue_rub": annual_revenue_rub,
        "annual_net_profit_rub": annual_net_profit_rub,
        "ebitda_rub": ebitda_rub,
        "total_debt_rub": total_debt_rub,
        "monthly_revenue_rub": monthly_revenue_rub,
        "monthly_expenses_rub": monthly_expenses_rub,
        "accounts_receivable_rub": accounts_receivable_rub,
        "cash_balance_rub": cash_balance_rub,
        "requested_amount_rub": requested_amount_rub,
        "term_months": term_months,
        "active_obligations_count": active_obligations_count,
        "total_outstanding_rub": total_outstanding_rub,
        "monthly_debt_payments_rub": monthly_debt_payments_rub,
        "max_days_past_due_12m": max_days_past_due_12m,
        "has_current_past_due": has_current_past_due,
        "credit_utilization": credit_utilization.round(4),
        "closed_obligations_count": closed_obligations_count,
        "applications_last_6m": applications_last_6m,
        "tax_debt_rub": tax_debt_rub,
        "unpaid_tax_count": unpaid_tax_count,
        "blocked_accounts_count": blocked_accounts_count,
        "late_payments_12m": late_payments_12m,
        "active_enforcement_count": active_enforcement_count,
        "enforcement_amount_rub": enforcement_amount_rub,
        "court_cases_count": court_cases_count,
        "court_claims_rub": court_claims_rub,
        "historical_bankruptcy_flag": historical_bankruptcy_flag,
        "bki_credit_score": bki_credit_score,
        "fraud_flag": fraud_flag,
        "txn_inflow_90d": txn_inflow_90d,
        "txn_outflow_90d": txn_outflow_90d,
        "txn_net_90d": txn_net_90d,
        "txn_count_90d": txn_count_90d,
        "txn_inflow_180d": txn_inflow_180d,
        "txn_outflow_180d": txn_outflow_180d,
        "txn_balance_latest": txn_balance_latest,
        "product_type": product_type,
        "purpose": purpose,
        "company_segment": company_segment,
        "legal_form": legal_form,
        "tax_regime": tax_regime,
        "client_rating": client_rating,
        TARGET_COLUMN: target,
    }
    data.update(new_features)
    frame = pd.DataFrame(data)
    return frame[RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN]]


def save_dataset(path: str | Path, n_samples: int = 20_000, seed: int = 42) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    generate_dataset(n_samples=n_samples, seed=seed).to_csv(destination, index=False)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic credit dataset")
    parser.add_argument("--out", default="data/synthetic_applications.csv")
    parser.add_argument("--samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    destination = save_dataset(args.out, n_samples=args.samples, seed=args.seed)
    frame = pd.read_csv(destination)
    rate = float(frame[TARGET_COLUMN].mean())
    print(f"saved {len(frame)} rows to {destination}, default_rate={rate:.3f}")


if __name__ == "__main__":
    main()
