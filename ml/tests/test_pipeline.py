from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from simplecredits.ml.data.pipeline import (
    RAW_TABLES,
    _credit_utilization,
    _dataset_cutoff,
    _first_numeric,
    _latest_statement,
    _numeric_max,
    _statement_available_at,
    _transaction_metrics,
    _validate_training_frame,
    build_training_table,
    load_raw_tables,
    main as run_pipeline_cli,
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
            {
                "statement_id": "FS0003",
                "company_id": "C0001",
                "year": 2026,
                "period": "H1",
                "revenue_rub": 99_000_000,
                "operating_expenses_rub": 80_000_000,
                "ebitda_rub": 15_000_000,
                "net_profit_rub": 10_000_000,
                "cash_rub": 5_000_000,
                "accounts_receivable_rub": 4_000_000,
                "debt_rub": 9_000_000,
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
            {
                "transaction_id": "TX0004",
                "account_id": "ACC1",
                "company_id": "C0001",
                "transaction_date": "2026-01-01T10:00:00Z",
                "direction": "in",
                "amount_rub": 999_999,
                "balance_after_rub": 2_000_000,
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

    for table, frame in tables.items():
        frame.to_sql(table, connection, if_exists="replace", index=False)
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
    assert row["txn_count_90d"] == 2
    assert row["txn_balance_latest"] == 150_000
    assert row["default"] == 0

    defaulted = frame.loc[frame["application_id"] == "A0002"].iloc[0]
    assert defaulted["default"] == 1
    assert defaulted["label_event"] == "future_bankruptcy"


def test_historical_default_label_respects_horizon(raw_db):
    tables = load_raw_tables(raw_db)
    history = tables["bank_internal_history"]
    mask = history["company_id"] == "C0001"
    history.loc[mask, "defaults_count"] = 1
    history.loc[mask, "last_activity_at"] = pd.Timestamp("2026-01-20T12:00:00Z")

    short_frame, _ = build_training_table(tables, horizon_days=10)
    short_row = short_frame.loc[short_frame["application_id"] == "A0001"].iloc[0]
    assert short_row["default"] == 0
    assert short_row["label_event"] == "no_default"

    full_frame, _ = build_training_table(tables, horizon_days=30)
    full_row = full_frame.loc[full_frame["application_id"] == "A0001"].iloc[0]
    assert full_row["default"] == 1
    assert full_row["label_event"] == "historical_defaults"


def test_run_pipeline_writes_csv_and_manifest(raw_db, tmp_path):
    output = tmp_path / "training.csv"
    frame, report = run_pipeline(raw_db, output, horizon_days=90)

    assert output.exists()
    assert output.with_suffix(".manifest.json").exists()
    assert len(frame) == 2
    assert report.pipeline_version == "raw-as-of-v4"
    assert report.output_path == str(output.resolve())
    assert report.db_sha256
    assert report.observation_horizon_days == 90
    assert report.label_event_counts == {"future_bankruptcy": 1, "no_default": 1}


def test_load_raw_tables_rejects_missing_database(tmp_path):
    with pytest.raises(FileNotFoundError, match="raw database not found"):
        load_raw_tables(tmp_path / "missing.db")


def test_load_raw_tables_rejects_missing_required_tables(tmp_path):
    db_path = tmp_path / "empty.db"
    sqlite3.connect(db_path).close()

    with pytest.raises(ValueError, match="missing raw tables"):
        load_raw_tables(db_path)


def test_build_training_table_requires_positive_horizon(raw_db):
    tables = load_raw_tables(raw_db)

    with pytest.raises(ValueError, match="horizon_days must be positive"):
        build_training_table(tables, horizon_days=0)


def test_build_training_table_requires_submitted_at(raw_db):
    tables = load_raw_tables(raw_db)
    tables["applications"] = tables["applications"].drop(columns=["submitted_at"])

    with pytest.raises(ValueError, match="must contain submitted_at"):
        build_training_table(tables)


def test_build_training_table_requires_mature_rows(raw_db):
    tables = load_raw_tables(raw_db)
    tables["applications"]["submitted_at"] = "2027-01-01T00:00:00Z"

    with pytest.raises(ValueError, match="no mature labeled applications"):
        build_training_table(tables)


def test_build_training_table_rejects_empty_applications(raw_db):
    tables = load_raw_tables(raw_db)
    tables["applications"] = tables["applications"].iloc[0:0]

    with pytest.raises(ValueError, match="no valid submitted_at"):
        build_training_table(tables)


def test_validate_training_frame_rejects_invalid_rows(raw_db):
    frame, _ = build_training_table(load_raw_tables(raw_db), horizon_days=90)
    _validate_training_frame(frame)

    duplicate = frame.copy()
    duplicate.loc[duplicate.index[1], "application_id"] = duplicate.loc[duplicate.index[0], "application_id"]
    with pytest.raises(ValueError, match="unique non-null application_id"):
        _validate_training_frame(duplicate)

    bad_target = frame.copy()
    bad_target.loc[bad_target.index[0], "default"] = 2
    with pytest.raises(ValueError, match="binary labels"):
        _validate_training_frame(bad_target)

    bad_event = frame.copy()
    bad_event.loc[bad_event.index[0], "label_event"] = "unknown"
    with pytest.raises(ValueError, match="unsupported label_event"):
        _validate_training_frame(bad_event)

    bad_date = frame.copy()
    bad_date.loc[bad_date.index[0], "submitted_at"] = "not-a-date"
    with pytest.raises(ValueError, match="must be valid timestamps"):
        _validate_training_frame(bad_date)

    bad_horizon = frame.copy()
    bad_horizon.loc[bad_horizon.index[0], "label_horizon_end"] = bad_horizon.loc[bad_horizon.index[0], "submitted_at"]
    with pytest.raises(ValueError, match="must be after submitted_at"):
        _validate_training_frame(bad_horizon)

    bad_numeric = frame.copy()
    bad_numeric.loc[bad_numeric.index[0], "annual_revenue_rub"] = np.inf
    with pytest.raises(ValueError, match="numeric features must be finite"):
        _validate_training_frame(bad_numeric)

    bad_positive = frame.copy()
    positive_index = bad_positive.index[bad_positive["default"] == 1][0]
    bad_positive.loc[positive_index, "label_event_at"] = bad_positive.loc[positive_index, "submitted_at"]
    with pytest.raises(ValueError, match="event after submitted_at"):
        _validate_training_frame(bad_positive)


def test_statement_helpers_handle_missing_and_future_data():
    as_of = pd.Timestamp("2026-01-01", tz="UTC")

    assert pd.isna(_statement_available_at(pd.Series({"year": "bad", "period": "FY"})))
    assert pd.isna(_statement_available_at(pd.Series({"year": 2025, "period": "unknown"})))
    assert _latest_statement(pd.DataFrame(), as_of).empty
    assert _latest_statement(pd.DataFrame({"year": [2025]}), as_of).empty
    assert _latest_statement(
        pd.DataFrame([{"year": 2025, "period": "FY"}]),
        pd.Timestamp("2025-01-01", tz="UTC"),
    ).empty


def test_numeric_helpers_return_defaults():
    assert _first_numeric(pd.DataFrame(), "value") == 0.0
    assert _first_numeric(pd.DataFrame([{"value": np.nan}]), "value") == 0.0
    assert _first_numeric(pd.DataFrame([{"value": 3.0}]), "missing") == 0.0
    assert _numeric_max(pd.DataFrame(), "value") == 0.0
    assert _numeric_max(pd.DataFrame([{"value": np.nan}]), "value") == 0.0
    assert _numeric_max(pd.DataFrame([{"value": 2.0}, {"value": 5.0}]), "value") == 5.0


def test_credit_utilization_edge_cases():
    assert _credit_utilization(pd.DataFrame()) == 0.0
    assert _credit_utilization(
        pd.DataFrame([{"amount_rub": 0, "outstanding_rub": 100}])
    ) == 0.0
    assert _credit_utilization(
        pd.DataFrame([{"amount_rub": 200, "outstanding_rub": 50}])
    ) == 0.25


def test_transaction_metrics_without_history():
    metrics = _transaction_metrics(
        pd.DataFrame(),
        pd.Timestamp("2026-01-01", tz="UTC"),
    )

    assert set(metrics) == {
        "txn_inflow_90d",
        "txn_outflow_90d",
        "txn_net_90d",
        "txn_count_90d",
        "txn_inflow_180d",
        "txn_outflow_180d",
        "txn_balance_latest",
    }
    assert all(value == 0.0 for value in metrics.values())


def test_dataset_cutoff_defaults_to_current_time():
    cutoff = _dataset_cutoff({})

    assert cutoff.tzinfo is not None
    assert cutoff.year >= 2026


def test_pipeline_cli_writes_output(raw_db, tmp_path, monkeypatch, capsys):
    output = tmp_path / "training.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-pipeline",
            "--db",
            str(raw_db),
            "--out",
            str(output),
            "--horizon-days",
            "90",
        ],
    )

    run_pipeline_cli()

    report = json.loads(capsys.readouterr().out)
    assert output.exists()
    assert report["training_rows"] == 2
    assert report["label_event_counts"] == {"future_bankruptcy": 1, "no_default": 1}
