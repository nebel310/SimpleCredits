from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    FINANCING_PURPOSES,
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
        "product_type": product_type,
        "purpose": purpose,
        TARGET_COLUMN: target,
    }
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
