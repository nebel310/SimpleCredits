from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from simplecredits.ml.data.raw_features import TABLE_AS_OF_COLUMNS, build_raw_features
from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    RAW_NUMERIC_FEATURES,
    TARGET_COLUMN,
)

PIPELINE_VERSION = "raw-as-of-v4"
DEFAULT_DB_PATH = Path("data/raw/simplecredits_raw.db")
DEFAULT_OUTPUT_PATH = Path("ml/data/training_table.csv")
DEFAULT_HORIZON_DAYS = 30
APPROVED_STATUSES = frozenset(
    {"approved", "offer_sent", "offer_accepted", "issued", "disbursed", "active"}
)
STATEMENT_PUBLICATION_LAG_DAYS = 90

REQUIRED_TABLES: tuple[str, ...] = (
    "applications",
    "companies",
    "self_assessments",
    "financial_statements",
    "bank_accounts",
    "bank_products",
    "bank_transactions",
    "credit_bureau_reports",
    "credit_inquiries",
    "fns_status",
    "court_cases",
    "enforcement_proceedings",
    "bankruptcy_events",
    "bank_internal_history",
)

RAW_TABLES: tuple[str, ...] = REQUIRED_TABLES + (
    "accounting_entries",
    "accounting_systems",
    "application_events",
    "audit_log",
    "biometric_checks",
    "business_history",
    "certifications",
    "collateral_offers",
    "consents",
    "counterparty_checks",
    "credit_bureau_loans",
    "currency_operations",
    "customs_declarations",
    "documents",
    "domain_whois",
    "egrul_records",
    "founders",
    "franchise_contracts",
    "fuel_cards",
    "geo_metrics",
    "gosuslugi_events",
    "grants_subsidies",
    "hr_metrics",
    "industry_memberships",
    "insurance_policies",
    "intellectual_property",
    "iot_sensors",
    "licenses",
    "loan_contracts",
    "loan_default_events",
    "logistics",
    "management_reports",
    "managers",
    "marketplace_sales",
    "mobile_operator",
    "news_mentions",
    "ofd_receipts",
    "offers",
    "payment_services",
    "policy_decisions",
    "rating_agency_ratings",
    "real_estate",
    "reputation",
    "rosstat_indicators",
    "scoring_results",
    "sfr_reports",
    "sme_registry",
    "social_media",
    "tax_reports",
    "telematics",
    "tenders",
    "trade_networks",
    "users",
    "utilities",
    "vehicles",
    "warehouse_stock",
    "website_metrics",
)

DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    table: (column,) for table, column in TABLE_AS_OF_COLUMNS.items() if column
}
DATE_COLUMNS.update(
    {
        "applications": ("submitted_at", "decision_at"),
        "bank_internal_history": ("last_activity_at",),
        "bank_products": ("opened_at", "closed_at"),
        "court_cases": ("filed_at", "last_hearing_at"),
        "licenses": ("issued_at", "valid_until"),
        "insurance_policies": ("valid_from", "valid_until"),
    }
)

META_COLUMNS = [
    "application_id",
    "company_id",
    "submitted_at",
    "feature_cutoff",
    "label_horizon_end",
    "label_event",
    "label_event_at",
]

TRAINING_COLUMNS = META_COLUMNS + RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES + [TARGET_COLUMN]

REGION_RISK = {
    "\u043c\u043e\u0441\u043a\u0432\u0430": 0.10,
    "\u0441\u0430\u043d\u043a\u0442-\u043f\u0435\u0442\u0435\u0440\u0431\u0443\u0440\u0433": 0.15,
    "\u043c\u043e\u0441\u043a\u043e\u0432\u0441\u043a\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c": 0.20,
    "\u0440\u0435\u0441\u043f\u0443\u0431\u043b\u0438\u043a\u0430 \u0442\u0430\u0442\u0430\u0440\u0441\u0442\u0430\u043d": 0.25,
    "\u0441\u0432\u0435\u0440\u0434\u043b\u043e\u0432\u0441\u043a\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c": 0.30,
    "\u043d\u043e\u0432\u043e\u0441\u0438\u0431\u0438\u0440\u0441\u043a\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c": 0.30,
    "\u043a\u0440\u0430\u0441\u043d\u043e\u0434\u0430\u0440\u0441\u043a\u0438\u0439 \u043a\u0440\u0430\u0439": 0.32,
    "\u0440\u043e\u0441\u0442\u043e\u0432\u0441\u043a\u0430\u044f \u043e\u0431\u043b\u0430\u0441\u0442\u044c": 0.35,
    "\u0440\u0435\u0441\u043f\u0443\u0431\u043b\u0438\u043a\u0430 \u0431\u0430\u0448\u043a\u043e\u0440\u0442\u043e\u0441\u0442\u0430\u043d": 0.32,
}

STATEMENT_PERIOD_END_MONTH_DAY = {
    "H1": (6, 30),
    "FY": (12, 31),
}

OKVED_RISK = {
    "01": 0.55,
    "02": 0.60,
    "10": 0.35,
    "41": 0.40,
    "43": 0.45,
    "45": 0.45,
    "46": 0.35,
    "47": 0.50,
    "49": 0.40,
    "55": 0.55,
    "56": 0.55,
    "61": 0.30,
    "62": 0.20,
    "63": 0.25,
    "68": 0.45,
    "69": 0.30,
    "71": 0.30,
    "73": 0.35,
    "74": 0.35,
    "86": 0.25,
}


@dataclass(frozen=True)
class PipelineReport:
    pipeline_version: str
    generated_at: str
    db_path: str
    output_path: str
    db_sha256: str
    total_applications: int
    eligible_applications: int
    censored_applications: int
    training_rows: int
    positive_labels: int
    negative_labels: int
    default_rate: float
    observation_horizon_days: int
    dataset_cutoff: str
    label_event_counts: dict[str, int]
    table_counts: dict[str, int]

    def as_dict(self) -> dict:
        result = asdict(self)
        result["default_rate"] = round(self.default_rate, 6)
        return result


def _utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def _parse_utc(value: object) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, errors="coerce", utc=True, format="mixed")
    return pd.Timestamp(timestamp)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date_columns(frame: pd.DataFrame, table: str) -> pd.DataFrame:
    result = frame.copy()
    for column in DATE_COLUMNS.get(table, ()):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], errors="coerce", utc=True, format="mixed")
    return result


def _group_by_company(tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.DataFrame]]:
    grouped: dict[str, dict[str, pd.DataFrame]] = {}
    for table, frame in tables.items():
        if frame.empty or "company_id" not in frame.columns:
            grouped[table] = {}
            continue
        groups: dict[str, pd.DataFrame] = {}
        for company_id, group in frame.groupby("company_id", sort=False):
            groups[str(company_id)] = group.copy()
        grouped[table] = groups
    return grouped


def _company_frames(
    grouped: dict[str, dict[str, pd.DataFrame]],
    table: str,
    company_id: str,
) -> pd.DataFrame:
    return grouped.get(table, {}).get(company_id, pd.DataFrame())


def _as_of_rows(frame: pd.DataFrame, date_column: str, as_of: pd.Timestamp) -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.iloc[0:0]
    dates = pd.to_datetime(frame[date_column], errors="coerce", utc=True, format="mixed")
    return frame.loc[dates.notna() & (dates < as_of)].copy()


def _window_rows(frame: pd.DataFrame, date_column: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.iloc[0:0]
    dates = pd.to_datetime(frame[date_column], errors="coerce", utc=True, format="mixed")
    return frame.loc[dates.notna() & (dates >= start) & (dates <= end)].copy()


def _latest(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.iloc[0:0]
    dates = pd.to_datetime(frame[date_column], errors="coerce", utc=True, format="mixed")
    valid = frame.loc[dates.notna()]
    if valid.empty:
        return valid
    return valid.loc[[dates.loc[valid.index].idxmax()]]


def _statement_available_at(row: pd.Series) -> pd.Timestamp:
    year = pd.to_numeric(row.get("year"), errors="coerce")
    period = str(row.get("period", "")).strip().upper()
    month_day = STATEMENT_PERIOD_END_MONTH_DAY.get(period)
    if pd.isna(year) or month_day is None:
        return pd.NaT
    month, day = month_day
    period_end = pd.Timestamp(year=int(year), month=month, day=day, tz="UTC")
    return period_end + pd.Timedelta(days=STATEMENT_PUBLICATION_LAG_DAYS)


def _latest_statement(frame: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if frame.empty or "year" not in frame.columns or "period" not in frame.columns:
        return frame.iloc[0:0]
    valid = frame.copy()
    valid["_available_at"] = valid.apply(_statement_available_at, axis=1)
    valid["_year"] = pd.to_numeric(valid["year"], errors="coerce")
    valid = valid.loc[valid["_available_at"].notna() & (valid["_available_at"] < as_of)]
    if valid.empty:
        return valid
    valid = valid.sort_values(["_available_at", "_year"], ascending=False)
    return valid.iloc[[0]].drop(columns=["_available_at", "_year"], errors="ignore")


def _first_numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> float:
    if frame.empty or column not in frame.columns:
        return default
    value = frame.iloc[0].get(column, default)
    if pd.isna(value):
        return default
    return float(value)


def _numeric_sum(frame: pd.DataFrame, column: str, default: float = 0.0) -> float:
    if frame.empty or column not in frame.columns:
        return default
    values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return float(values.sum())


def _numeric_max(frame: pd.DataFrame, column: str, default: float = 0.0) -> float:
    if frame.empty or column not in frame.columns:
        return default
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.empty or values.isna().all():
        return default
    return float(values.max())


def _region_risk(region: object) -> float:
    normalized = str(region or "").strip().lower().replace("\u0433.", "").strip()
    return REGION_RISK.get(normalized, 0.40)


def _okved_risk(code: object) -> float:
    prefix = str(code or "").strip()[:2]
    return OKVED_RISK.get(prefix, 0.40)


def _active_products(products: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    opened = _as_of_rows(products, "opened_at", as_of)
    if opened.empty:
        return opened
    if "closed_at" not in opened.columns:
        return opened
    closed = pd.to_datetime(opened["closed_at"], errors="coerce", utc=True, format="mixed")
    return opened.loc[closed.isna() | (closed > as_of)].copy()


def _closed_products(products: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    opened = _as_of_rows(products, "opened_at", as_of)
    if opened.empty or "closed_at" not in opened.columns:
        return opened.iloc[0:0]
    closed = pd.to_datetime(opened["closed_at"], errors="coerce", utc=True, format="mixed")
    return opened.loc[closed.notna() & (closed <= as_of)].copy()


def _transaction_metrics(transactions: pd.DataFrame, as_of: pd.Timestamp) -> dict[str, float]:
    history = _as_of_rows(transactions, "transaction_date", as_of)
    if history.empty:
        return {
            "txn_inflow_90d": 0.0,
            "txn_outflow_90d": 0.0,
            "txn_net_90d": 0.0,
            "txn_count_90d": 0.0,
            "txn_inflow_180d": 0.0,
            "txn_outflow_180d": 0.0,
            "txn_balance_latest": 0.0,
        }

    metrics: dict[str, float] = {}
    for days in (90, 180):
        window = _window_rows(history, "transaction_date", as_of - pd.Timedelta(days=days), as_of)
        if window.empty:
            inflow = 0.0
            outflow = 0.0
        else:
            window_amounts = pd.to_numeric(window.get("amount_rub"), errors="coerce").fillna(0.0)
            window_direction = window.get("direction", pd.Series(index=window.index, dtype="object")).astype(str).str.lower()
            inflow = float(window_amounts.loc[window_direction.isin({"in", "credit", "\u043f\u0440\u0438\u0445\u043e\u0434"})].sum())
            outflow = float(window_amounts.loc[window_direction.isin({"out", "debit", "\u0440\u0430\u0441\u0445\u043e\u0434"})].sum())
        metrics[f"txn_inflow_{days}d"] = inflow
        metrics[f"txn_outflow_{days}d"] = outflow

    latest = _latest(history, "transaction_date")
    metrics["txn_net_90d"] = metrics["txn_inflow_90d"] - metrics["txn_outflow_90d"]
    metrics["txn_count_90d"] = float(
        len(_window_rows(history, "transaction_date", as_of - pd.Timedelta(days=90), as_of))
    )
    metrics["txn_balance_latest"] = _first_numeric(latest, "balance_after_rub", 0.0)
    return metrics


def _credit_utilization(products: pd.DataFrame) -> float:
    if products.empty or "amount_rub" not in products.columns or "outstanding_rub" not in products.columns:
        return 0.0
    amounts = pd.to_numeric(products["amount_rub"], errors="coerce").fillna(0.0)
    outstanding = pd.to_numeric(products["outstanding_rub"], errors="coerce").fillna(0.0)
    denominator = float(amounts.sum())
    if denominator <= 0:
        return 0.0
    return float(np.clip(outstanding.sum() / denominator, 0.0, 1.0))


def _company_snapshot(
    company: pd.Series,
    company_id: str,
    application: pd.Series,
    grouped: dict[str, dict[str, pd.DataFrame]],
    as_of: pd.Timestamp,
) -> dict[str, object]:
    statements_all = _company_frames(grouped, "financial_statements", company_id)
    statement = _latest_statement(statements_all, as_of)

    assessments_all = _company_frames(grouped, "self_assessments", company_id)
    assessment = _latest(_as_of_rows(assessments_all, "created_at", as_of), "created_at")

    products_all = _company_frames(grouped, "bank_products", company_id)
    products_opened = _as_of_rows(products_all, "opened_at", as_of)
    active_products = _active_products(products_all, as_of)
    closed_products = _closed_products(products_all, as_of)

    bki_all = _company_frames(grouped, "credit_bureau_reports", company_id)
    bki = _latest(_as_of_rows(bki_all, "report_date", as_of), "report_date")

    inquiries_all = _company_frames(grouped, "credit_inquiries", company_id)
    inquiries = _as_of_rows(inquiries_all, "inquiry_date", as_of)
    inquiries_6m = _window_rows(inquiries, "inquiry_date", as_of - pd.Timedelta(days=180), as_of)

    fns_all = _company_frames(grouped, "fns_status", company_id)
    fns = _latest(_as_of_rows(fns_all, "updated_at", as_of), "updated_at")

    courts_all = _company_frames(grouped, "court_cases", company_id)
    courts = _as_of_rows(courts_all, "filed_at", as_of)

    enforcement_all = _company_frames(grouped, "enforcement_proceedings", company_id)
    enforcement = _as_of_rows(enforcement_all, "opened_at", as_of)

    historical_bankruptcy = _as_of_rows(
        _company_frames(grouped, "bankruptcy_events", company_id), "filed_at", as_of
    )

    transactions_all = _company_frames(grouped, "bank_transactions", company_id)
    transaction_metrics = _transaction_metrics(transactions_all, as_of)

    annual_revenue = _first_numeric(statement, "revenue_rub")
    if annual_revenue == 0.0:
        annual_revenue = _first_numeric(assessment, "declared_annual_revenue_rub")
    if annual_revenue == 0.0:
        annual_revenue = float(company.get("annual_revenue_rub", 0.0) or 0.0)

    monthly_revenue = _first_numeric(assessment, "declared_monthly_revenue_rub")
    if monthly_revenue == 0.0:
        monthly_revenue = annual_revenue / 12.0
    if monthly_revenue == 0.0:
        monthly_revenue = transaction_metrics["txn_inflow_90d"] / 3.0

    monthly_expenses = _first_numeric(assessment, "declared_monthly_expenses_rub")
    if monthly_expenses == 0.0:
        monthly_expenses = _first_numeric(statement, "operating_expenses_rub") / 12.0
    if monthly_expenses == 0.0:
        monthly_expenses = transaction_metrics["txn_outflow_90d"] / 3.0
    if monthly_expenses == 0.0:
        monthly_revenue = monthly_revenue or 1.0
        monthly_expenses = monthly_revenue * 0.85

    total_debt = _first_numeric(statement, "debt_rub")
    if total_debt == 0.0:
        total_debt = _first_numeric(assessment, "declared_total_debt_rub")
    product_outstanding = _numeric_sum(active_products, "outstanding_rub")
    bki_outstanding = _first_numeric(bki, "total_outstanding_rub")
    if total_debt == 0.0:
        total_debt = bki_outstanding or product_outstanding

    monthly_debt = _first_numeric(assessment, "declared_monthly_debt_payment_rub")
    if monthly_debt == 0.0:
        monthly_debt = _first_numeric(bki, "monthly_payment_rub")
    if monthly_debt == 0.0:
        monthly_debt = _numeric_sum(active_products, "monthly_payment_rub")

    employee_count = _first_numeric(assessment, "declared_employees")
    if employee_count == 0.0:
        employee_count = float(company.get("employee_count", 0.0) or 0.0)

    active_obligations = _first_numeric(bki, "active_loans")
    if active_obligations == 0.0:
        active_obligations = float(len(active_products))

    max_days_past_due = _first_numeric(bki, "max_days_past_due_12m")
    if max_days_past_due == 0.0:
        max_days_past_due = _numeric_max(products_opened, "days_past_due")

    current_past_due = _first_numeric(bki, "current_past_due")
    if current_past_due == 0.0 and not products_opened.empty and "days_past_due" in products_opened.columns:
        current_past_due = float((pd.to_numeric(products_opened["days_past_due"], errors="coerce").fillna(0) > 0).any())

    applications_6m = float(len(inquiries_6m))
    if applications_6m == 0.0:
        applications_6m = _first_numeric(bki, "applications_6m")

    cash_balance = _first_numeric(statement, "cash_rub")
    if cash_balance == 0.0:
        cash_balance = transaction_metrics["txn_balance_latest"]

    registration_date = pd.to_datetime(company.get("registration_date"), errors="coerce", utc=True)
    company_age_months = 0.0
    if pd.notna(registration_date):
        company_age_months = max(0.0, (as_of - registration_date).days / 30.4375)

    active_enforcement = enforcement
    if not active_enforcement.empty and "status" in active_enforcement.columns:
        status = active_enforcement["status"].astype(str).str.strip().str.lower()
        active_enforcement = active_enforcement.loc[status.isin({"\u0432 \u0440\u0430\u0431\u043e\u0442\u0435", "active"})]

    history = _latest(
        _as_of_rows(
            _company_frames(grouped, "bank_internal_history", company_id),
            "last_activity_at",
            as_of,
        ),
        "last_activity_at",
    )
    client_rating = str(history.iloc[0].get("client_rating", "B") or "B") if not history.empty else "B"

    raw_features = build_raw_features(
        company,
        company_id,
        application if isinstance(application, dict) else application.to_dict(),
        grouped,
        as_of,
        annual_revenue=annual_revenue,
        monthly_revenue=monthly_revenue,
        employee_count=employee_count,
        total_outstanding=bki_outstanding or product_outstanding,
    )

    return {
        "company_age_months": company_age_months,
        "employee_count": employee_count,
        "okved_risk": _okved_risk(company.get("okved_main")),
        "region_risk": _region_risk(company.get("region")),
        "annual_revenue_rub": annual_revenue,
        "annual_net_profit_rub": _first_numeric(statement, "net_profit_rub", _first_numeric(assessment, "declared_net_profit_rub")),
        "ebitda_rub": _first_numeric(statement, "ebitda_rub"),
        "total_debt_rub": total_debt,
        "monthly_revenue_rub": monthly_revenue,
        "monthly_expenses_rub": monthly_expenses,
        "accounts_receivable_rub": _first_numeric(statement, "accounts_receivable_rub"),
        "cash_balance_rub": cash_balance,
        "requested_amount_rub": float(application.get("requested_amount_rub", 0.0) or 0.0),
        "term_months": float(application.get("term_months", 0.0) or 0.0),
        "active_obligations_count": active_obligations,
        "total_outstanding_rub": bki_outstanding or product_outstanding,
        "monthly_debt_payments_rub": monthly_debt,
        "max_days_past_due_12m": max_days_past_due,
        "has_current_past_due": current_past_due,
        "credit_utilization": _credit_utilization(active_products),
        "closed_obligations_count": float(len(closed_products)),
        "applications_last_6m": applications_6m,
        "tax_debt_rub": _first_numeric(fns, "tax_debt_rub"),
        "unpaid_tax_count": _first_numeric(fns, "unpaid_tax_count"),
        "blocked_accounts_count": _first_numeric(fns, "blocked_accounts_count"),
        "late_payments_12m": _first_numeric(fns, "late_payments_12m"),
        "active_enforcement_count": float(len(active_enforcement)),
        "enforcement_amount_rub": _numeric_sum(active_enforcement, "amount_rub"),
        "court_cases_count": float(len(courts)),
        "court_claims_rub": _numeric_sum(courts, "amount_rub"),
        "historical_bankruptcy_flag": float(not historical_bankruptcy.empty),
        "bki_credit_score": _first_numeric(bki, "credit_score"),
        "fraud_flag": _first_numeric(bki, "fraud_flag"),
        **transaction_metrics,
        **raw_features,
        "product_type": str(application.get("product_type", "other") or "other"),
        "purpose": str(application.get("purpose", "other") or "other"),
        "company_segment": str(company.get("segment", "micro") or "micro"),
        "legal_form": str(company.get("legal_form", "llc") or "llc"),
        "tax_regime": str(company.get("tax_regime", "usn") or "usn"),
        "client_rating": client_rating,
    }


def _label_for_application(
    company_id: str,
    application_id: str,
    submitted_at: pd.Timestamp,
    horizon_days: int,
    dataset_cutoff: pd.Timestamp,
    grouped: dict[str, dict[str, pd.DataFrame]],
) -> tuple[int | None, str, pd.Timestamp | None]:
    horizon_end = submitted_at + pd.Timedelta(days=horizon_days)
    matured = horizon_end <= dataset_cutoff

    default_events = _company_frames(grouped, "loan_default_events", company_id)
    if not default_events.empty and "event_at" in default_events.columns:
        events = default_events.loc[
            default_events["application_id"].astype(str).eq(str(application_id))
        ].copy()
        events["event_at"] = pd.to_datetime(events["event_at"], errors="coerce", utc=True, format="mixed")
        future_default = events.loc[
            events["event_at"].notna()
            & (events["event_at"] > submitted_at)
            & (events["event_at"] <= horizon_end)
        ]
        if not future_default.empty:
            event = future_default.sort_values("event_at").iloc[0]
            return 1, "future_default", pd.Timestamp(event["event_at"])

    bankruptcy = _company_frames(grouped, "bankruptcy_events", company_id)
    if not bankruptcy.empty and "filed_at" in bankruptcy.columns:
        events = bankruptcy.copy()
        events["filed_at"] = pd.to_datetime(events["filed_at"], errors="coerce", utc=True, format="mixed")
        future = events.loc[
            events["filed_at"].notna()
            & (events["filed_at"] > submitted_at)
            & (events["filed_at"] <= horizon_end)
        ]
        if not future.empty:
            event = future.sort_values("filed_at").iloc[0]
            return 1, "future_bankruptcy", pd.Timestamp(event["filed_at"])

    internal_history = _company_frames(grouped, "bank_internal_history", company_id)
    historical_defaults = 0
    internal_event_at = None
    if not internal_history.empty and "defaults_count" in internal_history.columns:
        defaults = pd.to_numeric(internal_history["defaults_count"], errors="coerce").fillna(0)
        historical_defaults = int(defaults.sum())
        last_activity = _latest(internal_history, "last_activity_at")
        if not last_activity.empty:
            internal_event_at = pd.Timestamp(last_activity.iloc[0]["last_activity_at"])

    if historical_defaults > 0 and internal_event_at is not None:
        event_at = pd.Timestamp(internal_event_at)
        if submitted_at < event_at <= horizon_end:
            return 1, "historical_defaults", event_at
    if matured:
        return 0, "no_default", None
    return None, "censored", None


CUTOFF_TABLES = (
    "applications",
    "loan_default_events",
    "bankruptcy_events",
    "bank_internal_history",
    "bank_transactions",
    "application_events",
    "audit_log",
    "documents",
    "scoring_results",
    "policy_decisions",
    "offers",
    "loan_contracts",
)


def _dataset_cutoff(tables: dict[str, pd.DataFrame]) -> pd.Timestamp:
    candidates: list[pd.Timestamp] = []
    for table in CUTOFF_TABLES:
        column = TABLE_AS_OF_COLUMNS.get(table)
        frame = tables.get(table, pd.DataFrame())
        if not column or column not in frame.columns:
            continue
        dates = pd.to_datetime(frame[column], errors="coerce", utc=True, format="mixed")
        if not dates.empty and dates.notna().any():
            candidates.append(pd.Timestamp(dates.max()))
    if not candidates:
        return _utc_now()
    return max(candidates)


def _required_tables_present(tables: dict[str, pd.DataFrame]) -> None:
    missing = [table for table in REQUIRED_TABLES if table not in tables]
    if missing:
        raise ValueError(f"missing raw tables: {missing}")


def _validate_training_frame(frame: pd.DataFrame) -> None:
    if frame["application_id"].isna().any() or frame["application_id"].duplicated().any():
        raise ValueError("training table must contain unique non-null application_id values")
    if not frame[TARGET_COLUMN].isin((0, 1)).all():
        raise ValueError("target must contain only binary labels")
    if not frame["label_event"].isin(
        {"future_default", "future_bankruptcy", "historical_defaults", "no_default"}
    ).all():
        raise ValueError("unsupported label_event values")

    submitted_at = pd.to_datetime(frame["submitted_at"], errors="coerce", utc=True, format="mixed")
    horizon_end = pd.to_datetime(frame["label_horizon_end"], errors="coerce", utc=True, format="mixed")
    if submitted_at.isna().any() or horizon_end.isna().any():
        raise ValueError("submitted_at and label_horizon_end must be valid timestamps")
    if not (horizon_end > submitted_at).all():
        raise ValueError("label_horizon_end must be after submitted_at")

    numeric = frame[RAW_NUMERIC_FEATURES].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("numeric features must be finite")

    positive = frame[TARGET_COLUMN] == 1
    event_at = pd.to_datetime(frame.loc[positive, "label_event_at"], errors="coerce", utc=True, format="mixed")
    if event_at.isna().any() or not (event_at > submitted_at.loc[positive]).all():
        raise ValueError("positive labels must have an event after submitted_at")


def build_training_table(
    tables: dict[str, pd.DataFrame],
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> tuple[pd.DataFrame, PipelineReport]:
    _required_tables_present(tables)
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")

    applications = tables["applications"].copy()
    if "submitted_at" not in applications.columns:
        raise ValueError("applications table must contain submitted_at")
    applications["submitted_at"] = pd.to_datetime(applications["submitted_at"], errors="coerce", utc=True, format="mixed")
    applications = applications.loc[applications["submitted_at"].notna()].copy()
    total_applications = int(len(applications))
    if "status" in applications.columns:
        statuses = applications["status"].astype(str).str.lower()
        applications = applications.loc[statuses.isin(APPROVED_STATUSES)].copy()
    applications = applications.sort_values("submitted_at").reset_index(drop=True)
    if applications.empty:
        raise ValueError("applications table has no valid submitted_at values")

    companies = tables["companies"].copy()
    if "company_id" not in companies.columns:
        raise ValueError("companies table must contain company_id")
    companies = companies.drop_duplicates("company_id").set_index("company_id")

    grouped = _group_by_company(tables)
    dataset_cutoff = _dataset_cutoff(tables)

    rows: list[dict[str, object]] = []
    censored = 0
    for application in applications.to_dict("records"):
        company_id = str(application.get("company_id", ""))
        if company_id not in companies.index:
            censored += 1
            continue

        company = companies.loc[company_id]
        if isinstance(company, pd.DataFrame):
            company = company.iloc[0]
        submitted_at = pd.Timestamp(application["submitted_at"])
        label, label_event, label_event_at = _label_for_application(
            company_id,
            str(application.get("application_id", "")),
            submitted_at,
            horizon_days,
            dataset_cutoff,
            grouped,
        )
        if label is None:
            censored += 1
            continue

        snapshot = _company_snapshot(company, company_id, application, grouped, submitted_at)
        horizon_end = submitted_at + pd.Timedelta(days=horizon_days)
        row: dict[str, object] = {
            "application_id": application.get("application_id"),
            "company_id": company_id,
            "submitted_at": submitted_at.isoformat(),
            "feature_cutoff": submitted_at.isoformat(),
            "label_horizon_end": horizon_end.isoformat(),
            "label_event": label_event,
            "label_event_at": label_event_at.isoformat() if label_event_at is not None else None,
            **snapshot,
            TARGET_COLUMN: label,
        }
        rows.append(row)

    if not rows:
        raise ValueError("no mature labeled applications; generate more history or reduce horizon")

    frame = pd.DataFrame(rows)
    frame[TARGET_COLUMN] = pd.to_numeric(frame[TARGET_COLUMN], errors="raise").astype(int)
    frame = frame.reindex(columns=TRAINING_COLUMNS)
    _validate_training_frame(frame)

    positives = int(frame[TARGET_COLUMN].sum())
    negatives = int(len(frame) - positives)
    label_event_counts = {
        str(event): int(count)
        for event, count in frame["label_event"].value_counts().sort_index().items()
    }
    generated_at = datetime.now(timezone.utc).isoformat()
    report = PipelineReport(
        pipeline_version=PIPELINE_VERSION,
        generated_at=generated_at,
        db_path="",
        output_path="",
        db_sha256="",
        total_applications=total_applications,
        eligible_applications=int(len(frame)),
        censored_applications=int(censored),
        training_rows=int(len(frame)),
        positive_labels=positives,
        negative_labels=negatives,
        default_rate=float(frame[TARGET_COLUMN].mean()),
        observation_horizon_days=int(horizon_days),
        dataset_cutoff=dataset_cutoff.isoformat(),
        label_event_counts=label_event_counts,
        table_counts={table: int(len(tables[table])) for table in RAW_TABLES},
    )
    return frame, report


def load_raw_tables(db_path: str | Path) -> dict[str, pd.DataFrame]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"raw database not found: {path}")

    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA query_only = ON")
        existing = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing_required = [table for table in REQUIRED_TABLES if table not in existing]
        if missing_required:
            raise ValueError(f"missing raw tables: {missing_required}")
        tables: dict[str, pd.DataFrame] = {}
        for table in RAW_TABLES:
            if table in existing:
                frame = pd.read_sql_query(f'SELECT * FROM "{table}"', connection)
                tables[table] = _parse_date_columns(frame, table)
            else:
                tables[table] = pd.DataFrame()
    finally:
        connection.close()
    _required_tables_present(tables)
    return tables


def run_pipeline(
    db_path: str | Path = DEFAULT_DB_PATH,
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> tuple[pd.DataFrame, PipelineReport]:
    db = Path(db_path)
    output = Path(output_path)
    tables = load_raw_tables(db)
    frame, report = build_training_table(tables, horizon_days=horizon_days)

    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    final_report = PipelineReport(
        pipeline_version=report.pipeline_version,
        generated_at=report.generated_at,
        db_path=str(db.resolve()),
        output_path=str(output.resolve()),
        db_sha256=_sha256(db),
        total_applications=report.total_applications,
        eligible_applications=report.eligible_applications,
        censored_applications=report.censored_applications,
        training_rows=report.training_rows,
        positive_labels=report.positive_labels,
        negative_labels=report.negative_labels,
        default_rate=report.default_rate,
        observation_horizon_days=report.observation_horizon_days,
        dataset_cutoff=report.dataset_cutoff,
        label_event_counts=report.label_event_counts,
        table_counts=report.table_counts,
    )
    manifest_path = output.with_suffix(".manifest.json")
    manifest_path.write_text(
        json.dumps(final_report.as_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return frame, final_report


def _default_db() -> Path:
    candidates = [
        Path.cwd() / DEFAULT_DB_PATH,
        Path.cwd().parent / DEFAULT_DB_PATH,
        Path(__file__).resolve().parents[4] / "data" / "raw" / "simplecredits_raw.db",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return DEFAULT_DB_PATH


def _default_output() -> Path:
    if (Path.cwd() / "ml").exists():
        return Path.cwd() / "ml" / "data" / "training_table.csv"
    if (Path.cwd().parent / "ml").exists():
        return Path.cwd().parent / "ml" / "data" / "training_table.csv"
    return DEFAULT_OUTPUT_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SimpleCredits training table from raw data")
    parser.add_argument("--db", type=Path, default=_default_db())
    parser.add_argument("--out", type=Path, default=_default_output())
    parser.add_argument("--horizon-days", type=int, default=DEFAULT_HORIZON_DAYS)
    args = parser.parse_args()

    frame, report = run_pipeline(args.db, args.out, args.horizon_days)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
