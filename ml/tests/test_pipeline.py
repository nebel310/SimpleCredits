from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from simplecredits.ml.data.pipeline import (
    RAW_TABLES,
    build_training_table,
    load_raw_tables,
    run_pipeline,
)


@pytest.fixture
def raw_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "raw.db"
    connection = sqlite3.connect(db_path)

    companies = pd.DataFrame(
        [
            {
                "company_id": "C0001",
                "registration_date": "2020-01-01",
                "region": "Москва",
                "okved_main": "62",
                "employee_count": 10,
                "annual_revenue_rub": 12_000_000,
            },
            {
                "company_id": "C0002",
                "registration_date": "2018-01-01",
                "region": "Санкт-Петербург",
                "okved_main": "47",
                "employee_count": 50,
                "annual_revenue_rub": 50_000_000,
            },
        ]
    )
    applications = pd.DataFrame(
        [
            {
                "application_id": "A0001",
                "company_id": "C0001",
                "product_type": "term_loan",
                "purpose": "working_capital",
                "requested_amount_rub": 1_000_000,
                "term_months": 12,
                "submitted_at": "2026-01-01T10:00:00Z",
            },
            {
                "application_id": "A0002",
                "company_id": "C0002",
                "product_type": "overdraft",
                "purpose": "refinancing",
                "requested_amount_rub": 2_000_000,
                "term_months": 24,
                "submitted_at": "2026-01-02T11:00:00Z",
            },
        ]
    )
    self_assessments = pd.DataFrame(
        [
            {
                "assessment_id": "SA0001",
                "application_id": "A0001",
                "company_id": "C0001",
                "declared_annual_revenue_rub": 12_000_000,
                "declared_monthly_revenue_rub": 1_000_000,
                "declared_monthly_expenses_rub": 800_000,
                "declared_total_debt_rub": 1_500_000,
                "declared_monthly_debt_payment_rub": 100_000,
                "declared_employees": 10,
                "declared_net_profit_rub": 1_000_000,
                "created_at": "2026-01-01T09:00:00Z",
            },
            {
                "assessment_id": "SA0002",
                "application_id": "A0002",
                "company_id": "C0002",
                "declared_annual_revenue_rub": 50_000_000,
                "declared_monthly_revenue_rub": 4_000_000,
                "declared_monthly_expenses_rub": 3_000_000,
                "declared_total_debt_rub": 5_000_000,
                "declared_monthly_debt_payment_rub": 300_000,
                "declared_employees": 50,
                "declared_net_profit_rub": 5_000_000,
                "created_at": "2026-01-02T10:00:00Z",
            },
        ]
    )
    financial_statements = pd.DataFrame(
        [
            {
                "statement_id": "FS0001",
                "company_id": "C0001",
                "year": 2025,
                "period": "FY",
                "revenue_rub": 12_000_000,
                "operating_expenses_rub": 9_600_000,
                "ebitda_rub": 1_800_000,
                "net_profit_rub": 1_000_000,
                "cash_rub": 300_000,
                "accounts_receivable_rub": 400_000,
                "debt_rub": 1_500_000,
            },
            {
                "statement_id": "FS0002",
                "company_id": "C0002",
                "year": 2025,
                "period": "FY",
                "revenue_rub": 50_000_000,
                "operating_expenses_rub": 40_000_000,
                "ebitda_rub": 7_000_000,
                "net_profit_rub": 5_000_000,
                "cash_rub": 1_000_000,
                "accounts_receivable_rub": 1_500_000,
                "debt_rub": 5_000_000,
            },
        ]
    )
    bank_products = pd.DataFrame(
        [
            {
                "product_id": "BP0001",
                "company_id": "C0001",
                "product_type": "credit_line",
                "bank_name": "Bank A",
                "amount_rub": 2_000_000,
                "outstanding_rub": 500_000,
                "rate_percent": 15.0,
                "opened_at": "2025-01-01",
                "closed_at": None,
                "monthly_payment_rub": 50_000,
                "status": "active",
                "days_past_due": 0,
            },
        ]
    )
    bank_transactions = pd.DataFrame(
        [
            {
                "transaction_id": "TX0001",
                "account_id": "ACC1",
                "company_id": "C0001",
                "transaction_date": "2025-12-01",
                "direction": "in",
                "amount_rub": 100_000,
                "balance_after_rub": 200_000,
            },
            {
                "transaction_id": "TX0002",
                "account_id": "ACC1",
                "company_id": "C0001",
                "transaction_date": "2025-12-31",
                "direction": "out",
                "amount_rub": 50_000,
                "balance_after_rub": 150_000,
            },
            {
                "transaction_id": "TX0003",
                "account_id": "ACC2",
                "company_id": "C0002",
                "transaction_date": "2026-05-01",
                "direction": "in",
                "amount_rub": 10_000,
                "balance_after_rub": 20_000,
            },
        ]
    )
    credit_bureau_reports = pd.DataFrame(
        [
            {
                "report_id": "BKI0001",
                "company_id": "C0001",
                "bki_name": "BKI",
                "report_date": "2025-12-01",
                "credit_score": 700,
                "active_loans": 1,
                "total_outstanding_rub": 500_000,
                "monthly_payment_rub": 50_000,
                "max_days_past_due_12m": 0,
                "current_past_due": 0,
                "restructures_count": 0,
                "inquiries_6m": 1,
                "applications_6m": 1,
                "fraud_flag": 0,
            },
        ]
    )
    credit_inquiries = pd.DataFrame(
        [
            {
                "inquiry_id": "CI0001",
                "company_id": "C0001",
                "inquiry_date": "2025-12-01",
                "lender": "Bank A",
                "purpose": "credit",
                "approved": 1,
                "amount_rub": 500_000,
            },
        ]
    )
    fns_status = pd.DataFrame(
        [
            {
                "status_id": "FNS0001",
                "company_id": "C0001",
                "tax_debt_rub": 0,
                "unpaid_tax_count": 0,
                "blocked_accounts_count": 0,
                "late_payments_12m": 0,
                "special_regime": "USN",
                "risk_level": "low",
                "updated_at": "2025-12-01T12:00:00Z",
            },
        ]
    )
    court_cases = pd.DataFrame(
        columns=["case_id", "company_id", "filed_at", "amount_rub"]
    )
    enforcement_proceedings = pd.DataFrame(
        columns=["enforcement_id", "company_id", "opened_at", "amount_rub", "status"]
    )
    bankruptcy_events = pd.DataFrame(
        [
            {
                "event_id": "BNK0001",
                "company_id": "C0002",
                "event_type": "bankruptcy",
                "stage": "competition",
                "filed_at": "2026-02-01",
                "status": "in_progress",
                "creditor_claims_rub": 1_000_000,
                "manager_name": "Test",
                "source": "test",
            }
        ]
    )
    bank_accounts = pd.DataFrame(
        columns=["account_id", "company_id", "opened_at", "balance_rub"]
    )
    bank_internal_history = pd.DataFrame(
        [
            {
                "history_id": "HIST0001",
                "company_id": "C0001",
                "relationship_start": "2020-01-01",
                "segment": "small",
                "manager_name": "Manager",
                "previous_applications": 1,
                "approved_count": 1,
                "declined_count": 0,
                "defaults_count": 0,
                "restructures_count": 0,
                "aml_flags_json": "[]",
                "risk_flags_json": "[]",
                "digital_activity_score": 0.5,
                "last_activity_at": "2026-01-01T12:00:00Z",
                "client_rating": "A",
            },
            {
                "history_id": "HIST0002",
                "company_id": "C0002",
                "relationship_start": "2018-01-01",
                "segment": "small",
                "manager_name": "Manager",
                "previous_applications": 2,
                "approved_count": 2,
                "declined_count": 0,
                "defaults_count": 0,
                "restructures_count": 0,
                "aml_flags_json": "[]",
                "risk_flags_json": "[]",
                "digital_activity_score": 0.5,
                "last_activity_at": "2026-01-01T12:00:00Z",
                "client_rating": "A",
            },
        ]
    )

    tables = {
        "applications": applications,
        "companies": companies,
        "self_assessments": self_assessments,
        "financial_statements": financial_statements,
        "bank_accounts": bank_accounts,
        "bank_products": bank_products,
        "bank_transactions": bank_transactions,
        "credit_bureau_reports": credit_bureau_reports,
        "credit_inquiries": credit_inquiries,
        "fns_status": fns_status,
        "court_cases": court_cases,
        "enforcement_proceedings": enforcement_proceedings,
        "bankruptcy_events": bankruptcy_events,
        "bank_internal_history": bank_internal_history,
    }

    for table in RAW_TABLES:
        tables[table].to_sql(table, connection, if_exists="replace", index=False)
    connection.close()
    return db_path


def test_load_raw_tables_loads_all_required_tables(raw_db):
    tables = load_raw_tables(raw_db)
    assert set(tables.keys()) == set(RAW_TABLES)
    assert len(tables["applications"]) == 2
    assert len(tables["companies"]) == 2


def test_build_training_table_produces_features_and_labels(raw_db):
    tables = load_raw_tables(raw_db)
    frame, report = build_training_table(tables, horizon_days=90)

    assert len(frame) == 2
    assert report.total_applications == 2
    assert report.training_rows == 2
    assert report.positive_labels == 1
    assert report.negative_labels == 1
    assert 0.0 < report.default_rate < 1.0

    row = frame.loc[frame["application_id"] == "A0001"].iloc[0]
    assert row["company_id"] == "C0001"
    assert row["okved_risk"] == 0.20
    assert row["region_risk"] == 0.10
    assert row["annual_revenue_rub"] == 12_000_000
    assert row["monthly_revenue_rub"] == 1_000_000
    assert row["monthly_debt_payments_rub"] == 100_000
    assert row["active_obligations_count"] == 1
    assert row["txn_inflow_90d"] == 100_000
    assert row["txn_outflow_90d"] == 50_000
    assert row["txn_net_90d"] == 50_000
    assert row["txn_balance_latest"] == 150_000
    assert row["default"] == 0

    defaulted = frame.loc[frame["application_id"] == "A0002"].iloc[0]
    assert defaulted["default"] == 1
    assert defaulted["label_event"] == "future_bankruptcy"


def test_run_pipeline_writes_csv_and_manifest(raw_db, tmp_path):
    output = tmp_path / "training.csv"
    frame, report = run_pipeline(raw_db, output, horizon_days=90)

    assert output.exists()
    assert output.with_suffix(".manifest.json").exists()
    assert len(frame) == 2
    assert report.pipeline_version == "raw-as-of-v1"
    assert report.output_path == str(output.resolve())
    assert report.db_sha256
    assert report.observation_horizon_days == 90
