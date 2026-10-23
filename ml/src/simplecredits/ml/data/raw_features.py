from __future__ import annotations

import json
from typing import Any

import numpy as np
import pandas as pd

from simplecredits.ml.data.schema import NEW_NUMERIC_FEATURES

TABLE_AS_OF_COLUMNS: dict[str, str | None] = {
    "users": None,
    "founders": "since_date",
    "managers": "since_date",
    "consents": "granted_at",
    "egrul_records": "updated_at",
    "sme_registry": "included_at",
    "tax_reports": "submitted_at",
    "sfr_reports": None,
    "fns_status": "updated_at",
    "rosstat_indicators": "period",
    "intellectual_property": "registered_at",
    "customs_declarations": "declaration_date",
    "gosuslugi_events": "requested_at",
    "rating_agency_ratings": "assigned_at",
    "counterparty_checks": "checked_at",
    "business_history": "event_date",
    "domain_whois": "created_at",
    "geo_metrics": "last_updated_at",
    "bank_accounts": "opened_at",
    "bank_transactions": "transaction_date",
    "currency_operations": "operation_date",
    "bank_products": "opened_at",
    "credit_bureau_reports": "report_date",
    "credit_bureau_loans": "opened_at",
    "credit_inquiries": "inquiry_date",
    "court_cases": "filed_at",
    "enforcement_proceedings": "opened_at",
    "bankruptcy_events": "filed_at",
    "real_estate": "registered_at",
    "vehicles": None,
    "licenses": "issued_at",
    "tenders": "published_at",
    "insurance_policies": "valid_from",
    "fuel_cards": "last_transaction_at",
    "telematics": "last_signal_at",
    "iot_sensors": "recorded_at",
    "accounting_entries": "period",
    "management_reports": "period",
    "accounting_systems": "last_sync_at",
    "marketplace_sales": "period",
    "payment_services": "connected_at",
    "ofd_receipts": "receipt_date",
    "warehouse_stock": "period",
    "website_metrics": "period",
    "reputation": "last_review_at",
    "hr_metrics": "period",
    "logistics": "period",
    "utilities": "period",
    "mobile_operator": None,
    "social_media": "last_post_at",
    "news_mentions": "mention_date",
    "franchise_contracts": "contract_date",
    "grants_subsidies": "received_at",
    "certifications": "issued_at",
    "industry_memberships": "member_since",
    "trade_networks": "contract_date",
    "biometric_checks": "checked_at",
    "application_events": "created_at",
    "scoring_results": "created_at",
    "policy_decisions": "created_at",
    "loan_contracts": "issued_at",
    "documents": "uploaded_at",
    "audit_log": "created_at",
    "loan_default_events": "event_at",
}

TAX_REGIME_RISK = {
    "osn": 0.25,
    "usn": 0.35,
    "patent": 0.30,
    "eshn": 0.40,
}

RATING_SCORE = {
    "A-": 0.95,
    "BBB+": 0.85,
    "BBB": 0.78,
    "BBB-": 0.70,
    "BB+": 0.62,
    "BB": 0.55,
    "BB-": 0.48,
}

CLIENT_RATING_RISK = {
    "A": 0.10,
    "B": 0.25,
    "C": 0.45,
    "D": 0.65,
    "E": 0.85,
}


def _company_frame(
    grouped: dict[str, dict[str, pd.DataFrame]], table: str, company_id: str
) -> pd.DataFrame:
    return grouped.get(table, {}).get(company_id, pd.DataFrame())


def _parse_dates(values: pd.Series) -> pd.Series:
    direct = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    missing = direct.isna() & values.notna()
    if missing.any():
        text = values.loc[missing].astype(str)
        monthly = pd.to_datetime(text + "-01", errors="coerce", utc=True, format="mixed")
        monthly = monthly + pd.offsets.MonthEnd(0)
        direct.loc[missing] = monthly
    return direct


def _as_of(
    frame: pd.DataFrame,
    table: str,
    as_of: pd.Timestamp,
    column: str | None = None,
) -> pd.DataFrame:
    if frame.empty:
        return frame
    date_column = column or TABLE_AS_OF_COLUMNS.get(table)
    if not date_column or date_column not in frame.columns:
        return frame.copy()
    dates = _parse_dates(frame[date_column])
    return frame.loc[dates.notna() & (dates < as_of)].copy()


def _latest(frame: pd.DataFrame, table: str, as_of: pd.Timestamp) -> pd.DataFrame:
    history = _as_of(frame, table, as_of)
    if history.empty:
        return history
    date_column = TABLE_AS_OF_COLUMNS.get(table)
    if not date_column or date_column not in history.columns:
        return history.iloc[[-1]]
    dates = _parse_dates(history[date_column])
    valid = history.loc[dates.notna()].copy()
    if valid.empty:
        return valid
    dates = dates.loc[valid.index]
    return valid.loc[[dates.idxmax()]]


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0).astype(float)


def _sum(frame: pd.DataFrame, column: str) -> float:
    values = _numeric(frame, column)
    return float(values.sum()) if not values.empty else 0.0


def _mean(frame: pd.DataFrame, column: str) -> float:
    values = _numeric(frame, column)
    return float(values.mean()) if not values.empty else 0.0


def _max(frame: pd.DataFrame, column: str) -> float:
    values = _numeric(frame, column)
    return float(values.max()) if not values.empty else 0.0


def _first(frame: pd.DataFrame, column: str) -> float:
    values = _numeric(frame, column)
    return float(values.iloc[0]) if not values.empty else 0.0


def _ratio(numerator: float, denominator: float, cap: float = 10.0) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator <= 0:
        return 0.0
    return float(np.clip(numerator / denominator, -cap, cap))


def _share(numerator: float, denominator: float) -> float:
    return float(np.clip(_ratio(numerator, denominator, 1.0), 0.0, 1.0))


def _sum_masked(values: pd.Series, mask: pd.Series) -> float:
    if values.empty or mask.empty:
        return 0.0
    aligned = mask.reindex(values.index, fill_value=False).astype(bool)
    return float(values.loc[aligned].sum())


def _json_length(value: Any) -> float:
    if isinstance(value, (list, tuple, dict)):
        return float(len(value))
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return 0.0
        if isinstance(parsed, (list, tuple, dict)):
            return float(len(parsed))
    return 0.0


def _flag(condition: bool) -> float:
    return 1.0 if bool(condition) else 0.0


def _growth(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return float(np.clip((current - previous) / previous, -1.0, 2.0))


def _period_rows(frame: pd.DataFrame, table: str, as_of: pd.Timestamp) -> pd.DataFrame:
    return _as_of(frame, table, as_of)


def build_raw_features(
    company: pd.Series,
    company_id: str,
    application: dict[str, Any],
    grouped: dict[str, dict[str, pd.DataFrame]],
    as_of: pd.Timestamp,
    annual_revenue: float,
    monthly_revenue: float,
    employee_count: float,
    total_outstanding: float,
) -> dict[str, float]:
    revenue = max(float(annual_revenue or 0.0), 1.0)
    monthly = max(float(monthly_revenue or 0.0), 1.0)
    employees = max(float(employee_count or 0.0), 1.0)
    values: dict[str, float] = {}

    def put(name: str, value: float) -> None:
        numeric = float(value) if value is not None else 0.0
        if not np.isfinite(numeric):
            numeric = 0.0
        values[name] = numeric

    users = _company_frame(grouped, "users", company_id)
    founders = _as_of(_company_frame(grouped, "founders", company_id), "founders", as_of)
    managers = _as_of(_company_frame(grouped, "managers", company_id), "managers", as_of)
    consents = _as_of(_company_frame(grouped, "consents", company_id), "consents", as_of)
    if not consents.empty and "status" in consents.columns and "expires_at" in consents.columns:
        active = consents["status"].astype(str).str.lower().eq("granted")
        expiry = _parse_dates(consents["expires_at"])
        consents = consents.loc[active & (expiry.isna() | (expiry > as_of))]
    egrul = _latest(_company_frame(grouped, "egrul_records", company_id), "egrul_records", as_of)
    sme = _latest(_company_frame(grouped, "sme_registry", company_id), "sme_registry", as_of)

    put("user_count", len(users))
    put("founder_count", len(founders))
    put(
        "legal_entity_founder_flag",
        _flag(not founders.empty and founders["founder_type"].astype(str).eq("legal_entity").any())
        if "founder_type" in founders.columns
        else 0.0,
    )
    founder_shares = _numeric(founders, "share_percent") / 100.0
    put("max_founder_share", float(founder_shares.max()) if not founder_shares.empty else 0.0)
    put("manager_count", len(managers))
    manager_since = _parse_dates(managers["since_date"]) if "since_date" in managers.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not manager_since.empty and manager_since.notna().any():
        oldest = manager_since.min()
        put("manager_tenure_months", max(0.0, (as_of - oldest).days / 30.4375))
    else:
        put("manager_tenure_months", 0.0)
    put(
        "disqualified_manager_flag",
        _flag(not managers.empty and _numeric(managers, "is_disqualified").max() > 0)
        if "is_disqualified" in managers.columns
        else 0.0,
    )
    put("consent_count", len(consents))
    consent_types = consents["consent_type"].astype(str).str.lower() if "consent_type" in consents.columns else pd.Series(dtype=str)
    put("pdn_consent_flag", _flag(consent_types.str.contains("personal_data|pdn", regex=True).any()))
    put("marketing_consent_flag", _flag(consent_types.str.contains("marketing", regex=True).any()))
    put("egrul_change_count", len(egrul) if "changes_json" not in egrul.columns else 0.0)
    if not egrul.empty and "changes_json" in egrul.columns:
        put("egrul_change_count", _json_length(egrul.iloc[0]["changes_json"]))
    put("egrul_unreliable_flag", _first(egrul, "unreliable_record_flag"))
    put("mass_address_flag", _first(egrul, "mass_address_flag"))
    put("mass_manager_flag", _first(egrul, "mass_manager_flag"))
    put("log_authorized_capital", np.log1p(max(0.0, _first(egrul, "authorized_capital_rub"))))
    put("sme_registered_flag", _flag(not sme.empty))
    excluded = False
    if not sme.empty and "excluded_at" in sme.columns:
        excluded = _parse_dates(sme["excluded_at"]).notna().any()
    put("sme_excluded_flag", _flag(excluded))
    tax_regime = str(company.get("tax_regime", "") or "").lower()
    put("tax_regime_risk", TAX_REGIME_RISK.get(tax_regime, 0.4))

    tax_reports = _as_of(_company_frame(grouped, "tax_reports", company_id), "tax_reports", as_of)
    tax_amount = _sum(tax_reports, "tax_amount_rub")
    put("tax_report_count", len(tax_reports))
    put("tax_paid_ratio", _share(_sum(tax_reports, "paid_amount_rub"), tax_amount))
    put("tax_debt_ratio", _share(_sum(tax_reports, "debt_amount_rub"), tax_amount))
    status = tax_reports["status"].astype(str).str.lower() if "status" in tax_reports.columns else pd.Series(dtype=str)
    put("tax_late_report_count", float(status.eq("debt").sum()))

    sfr = _latest(_company_frame(grouped, "sfr_reports", company_id), "sfr_reports", as_of)
    payroll = _first(sfr, "payroll_fund_rub")
    put("sfr_employee_ratio", _ratio(_first(sfr, "insured_employees"), employees))
    put("payroll_per_employee", _ratio(payroll, employees, cap=1e9))
    put("sfr_debt_ratio", _share(_first(sfr, "debt_rub"), payroll))
    rosstat = _as_of(_company_frame(grouped, "rosstat_indicators", company_id), "rosstat_indicators", as_of)
    rosstat_revenue = 0.0
    rosstat_growth = 0.0
    if not rosstat.empty and "indicator" in rosstat.columns:
        candidates = rosstat
        if "unit" in rosstat.columns:
            indicators = rosstat["indicator"].astype(str)
            revenue_like = rosstat.loc[
                indicators.str.contains("revenue|выруч", case=False, regex=True)
            ]
            rub_values = rosstat.loc[rosstat["unit"].astype(str).str.lower().eq("rub")]
            if not revenue_like.empty:
                candidates = revenue_like
            elif not rub_values.empty:
                candidates = rub_values
        rows = candidates.copy()
        rows["_period"] = _parse_dates(rows["period"])
        rows = rows.loc[rows["_period"].notna()].sort_values("_period")
        if not rows.empty:
            indicator = rows.iloc[-1]["indicator"]
            history = rows.loc[rows["indicator"].astype(str).eq(str(indicator))]
            rosstat_revenue = _first(history.iloc[[-1]], "value")
            if len(history) > 1:
                previous = _first(history.iloc[[-2]], "value")
                rosstat_growth = _growth(rosstat_revenue, previous)
    put("rosstat_revenue_to_annual", _ratio(rosstat_revenue, revenue))
    put("rosstat_revenue_growth", rosstat_growth)

    statements = _company_frame(grouped, "financial_statements", company_id)
    available = statements.copy()
    if not available.empty and {"year", "period"}.issubset(available.columns):
        available["_available_at"] = pd.to_datetime(
            available["year"].astype(str) + "-12-31", errors="coerce", utc=True
        ) + pd.Timedelta(days=90)
        available = available.loc[available["_available_at"] < as_of].sort_values("_available_at")
    latest_statement = available.iloc[[-1]] if not available.empty else available
    previous_statement = available.iloc[[-2]] if len(available) > 1 else available.iloc[0:0]
    put("statement_count", len(available))
    if not latest_statement.empty and "_available_at" in latest_statement.columns:
        available_at = pd.Timestamp(latest_statement.iloc[0]["_available_at"])
        put("statement_freshness_days", max(0.0, (as_of - available_at).days))
    else:
        put("statement_freshness_days", 0.0)
    assets = _first(latest_statement, "total_assets_rub")
    liabilities = _first(latest_statement, "total_liabilities_rub")
    equity = _first(latest_statement, "equity_rub")
    current_assets = _first(latest_statement, "current_assets_rub")
    current_liabilities = _first(latest_statement, "current_liabilities_rub")
    debt = _first(latest_statement, "debt_rub")
    put("equity_ratio", _ratio(equity, assets))
    put("current_ratio", _ratio(current_assets, current_liabilities, cap=20.0))
    put("debt_to_equity", _ratio(debt, equity, cap=20.0))
    put("audited_statement_flag", _first(latest_statement, "audit_flag"))
    put("revenue_growth_yoy", _growth(_first(latest_statement, "revenue_rub"), _first(previous_statement, "revenue_rub")))
    put("inventory_ratio", _ratio(_first(latest_statement, "inventory_rub"), assets))
    put("interest_coverage", _ratio(_first(latest_statement, "ebitda_rub"), _first(latest_statement, "interest_rub"), cap=50.0))

    accounts = _as_of(_company_frame(grouped, "bank_accounts", company_id), "bank_accounts", as_of)
    put("account_count", len(accounts))
    opened = _parse_dates(accounts["opened_at"]) if "opened_at" in accounts.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not opened.empty and opened.notna().any():
        put("account_age_months", max(0.0, (as_of - opened.min()).days / 30.4375))
    else:
        put("account_age_months", 0.0)
    put("overdraft_limit_ratio", _ratio(_sum(accounts, "overdraft_limit_rub"), revenue))

    transactions = _as_of(_company_frame(grouped, "bank_transactions", company_id), "bank_transactions", as_of)
    transactions_90 = pd.DataFrame()
    if not transactions.empty and "transaction_date" in transactions.columns:
        dates = _parse_dates(transactions["transaction_date"])
        transactions_90 = transactions.loc[dates >= as_of - pd.Timedelta(days=90)].copy()
        transactions_180 = transactions.loc[dates >= as_of - pd.Timedelta(days=180)].copy()
        transactions_previous = transactions.loc[
            (dates >= as_of - pd.Timedelta(days=180)) & (dates < as_of - pd.Timedelta(days=90))
        ]
    else:
        transactions_180 = transactions
        transactions_previous = transactions.iloc[0:0]
    directions = (
        transactions_90["direction"].astype(str).str.lower()
        if "direction" in transactions_90.columns
        else pd.Series(dtype=str)
    )
    amounts = _numeric(transactions_90, "amount_rub")
    inflow = _sum_masked(amounts, directions.isin({"in", "credit", "приход"}))
    outflow = _sum_masked(amounts, directions.isin({"out", "debit", "расход"}))
    previous_directions = (
        transactions_previous["direction"].astype(str).str.lower()
        if "direction" in transactions_previous.columns
        else pd.Series(dtype=str)
    )
    previous_amounts = _numeric(transactions_previous, "amount_rub")
    previous_inflow = _sum_masked(previous_amounts, previous_directions.isin({"in", "credit", "приход"}))
    previous_outflow = _sum_masked(previous_amounts, previous_directions.isin({"out", "debit", "расход"}))
    put("txn_inflow_mom_growth", _growth(inflow, previous_inflow))
    put("txn_outflow_mom_growth", _growth(outflow, previous_outflow))
    put("txn_balance_volatility", _ratio(_numeric(transactions_90, "balance_after_rub").std(ddof=0), monthly))
    put("txn_counterparty_count", float(_numeric(transactions_90, "counterparty_inn").nunique()))
    categories = transactions_90["category"].astype(str).str.lower() if "category" in transactions_90.columns else pd.Series(dtype=str)
    total_amount = float(amounts.sum())
    put("txn_cash_share", _share(_sum_masked(amounts, categories.str.contains("cash|налич", regex=True)), total_amount))
    put("txn_tax_share", _share(_sum_masked(amounts, categories.str.contains("tax|налог", regex=True)), total_amount))
    put("txn_loan_payment_share", _share(_sum_masked(amounts, categories.str.contains("loan|credit|кредит", regex=True)), total_amount))
    put("txn_salary_share", _share(_sum_masked(amounts, categories.str.contains("salary|зарплат", regex=True)), total_amount))
    put("txn_avg_ticket_to_monthly_revenue", _ratio(_mean(transactions_90, "amount_rub"), monthly))
    put("txn_inflow_per_employee", _ratio(inflow, employees * 3.0, cap=1e9))

    currency = _as_of(_company_frame(grouped, "currency_operations", company_id), "currency_operations", as_of)
    put("fx_operation_count", len(currency))
    put("fx_turnover_to_annual", _ratio(_sum(currency, "amount_rub"), revenue))
    currency_directions = currency["direction"].astype(str).str.lower() if "direction" in currency.columns else pd.Series(dtype=str)
    put("fx_import_share", _share(_sum_masked(_numeric(currency, "amount_rub"), currency_directions.isin({"out", "debit", "расход"})), _sum(currency, "amount_rub")))

    products = _as_of(_company_frame(grouped, "bank_products", company_id), "bank_products", as_of)
    product_types = products["product_type"].astype(str).str.lower() if "product_type" in products.columns else pd.Series(dtype=str)
    put("product_count", len(products))
    put("loan_product_count", float(product_types.isin({"loan", "overdraft", "leasing", "factoring"}).sum()))
    put("overdue_product_count", float((_numeric(products, "days_past_due") > 0).sum()))
    put("product_outstanding_ratio", _share(_sum(products, "outstanding_rub"), _sum(products, "amount_rub")))
    product_opened = _parse_dates(products["opened_at"]) if "opened_at" in products.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not product_opened.empty and product_opened.notna().any():
        put("product_age_months", max(0.0, (as_of - product_opened.min()).days / 30.4375))
    else:
        put("product_age_months", 0.0)
    put("has_leasing", _flag(product_types.eq("leasing").any()))
    put("has_acquiring", _flag(product_types.eq("acquiring").any()))
    put("has_salary_project", _flag(product_types.eq("salary_project").any()))

    bki_loans = _as_of(_company_frame(grouped, "credit_bureau_loans", company_id), "credit_bureau_loans", as_of)
    bki_status = bki_loans["status"].astype(str).str.lower() if "status" in bki_loans.columns else pd.Series(dtype=str)
    put("bki_loan_count", len(bki_loans))
    put("bki_active_loan_count", float((~bki_status.eq("closed")).sum()))
    put("bki_closed_ratio", _share(float(bki_status.eq("closed").sum()), len(bki_loans)))
    put("bki_collateralized_share", _share(float(bki_loans["collateral"].notna().sum()), len(bki_loans)) if "collateral" in bki_loans.columns else 0.0)
    bki_opened = _parse_dates(bki_loans["opened_at"]) if "opened_at" in bki_loans.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not bki_opened.empty and bki_opened.notna().any():
        put("bki_avg_loan_age_months", max(0.0, (as_of - bki_opened.mean()).days / 30.4375))
    else:
        put("bki_avg_loan_age_months", 0.0)
    put("bki_dpd_ratio", _share(_sum(bki_loans, "days_past_due"), 365.0 * max(1.0, len(bki_loans))))
    bki_report = _latest(_company_frame(grouped, "credit_bureau_reports", company_id), "credit_bureau_reports", as_of)
    report_date = _parse_dates(bki_report["report_date"]) if "report_date" in bki_report.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not report_date.empty and report_date.notna().any():
        put("bki_report_age_days", max(0.0, (as_of - report_date.max()).days))
    else:
        put("bki_report_age_days", 0.0)

    courts = _as_of(_company_frame(grouped, "court_cases", company_id), "court_cases", as_of)
    roles = courts["role"].astype(str).str.lower() if "role" in courts.columns else pd.Series(dtype=str)
    put("court_defendant_count", float(roles.str.contains("defendant|ответчик", regex=True).sum()))
    court_dates = _parse_dates(courts["filed_at"]) if "filed_at" in courts.columns else pd.Series(dtype="datetime64[ns, UTC]")
    put("court_recent_count", float((court_dates >= as_of - pd.Timedelta(days=365)).sum()))
    put("court_amount_to_revenue", _ratio(_sum(courts, "amount_rub"), revenue))

    enforcement = _as_of(_company_frame(grouped, "enforcement_proceedings", company_id), "enforcement_proceedings", as_of)
    enforcement_status = enforcement["status"].astype(str).str.lower() if "status" in enforcement.columns else pd.Series(dtype=str)
    put("enforcement_active_count", float(enforcement_status.isin({"active", "в работе"}).sum()))
    put("enforcement_paid_ratio", _share(_sum(enforcement, "paid_amount_rub"), _sum(enforcement, "amount_rub")))

    bankruptcy = _as_of(_company_frame(grouped, "bankruptcy_events", company_id), "bankruptcy_events", as_of)
    put("bankruptcy_notice_flag", _flag(not bankruptcy.empty))
    bankruptcy_stage = bankruptcy["stage"].astype(str).str.lower() if "stage" in bankruptcy.columns else pd.Series(dtype=str)
    put("bankruptcy_stage_risk", _share(float(bankruptcy_stage.str.contains("monitoring|конкурс|наблюд", regex=True).sum()), len(bankruptcy)))

    real_estate = _as_of(_company_frame(grouped, "real_estate", company_id), "real_estate", as_of)
    put("real_estate_value_to_revenue", _ratio(_sum(real_estate, "market_value_rub"), revenue))
    encumbrances = real_estate["encumbrances_json"] if "encumbrances_json" in real_estate.columns else pd.Series(dtype=object)
    encumbered = sum(1 for value in encumbrances if value not in (None, "", "[]", [], {}))
    put("real_estate_encumbered_share", _share(float(encumbered), len(real_estate)))
    vehicles = _company_frame(grouped, "vehicles", company_id)
    put("vehicle_value_to_revenue", _ratio(_sum(vehicles, "market_value_rub"), revenue))
    restrictions = vehicles["restrictions_json"] if "restrictions_json" in vehicles.columns else pd.Series(dtype=object)
    restricted = sum(1 for value in restrictions if value not in (None, "", "[]", [], {}))
    put("vehicle_restricted_share", _share(float(restricted), len(vehicles)))
    licenses = _as_of(_company_frame(grouped, "licenses", company_id), "licenses", as_of)
    put("license_count", len(licenses))
    valid_until = _parse_dates(licenses["valid_until"]) if "valid_until" in licenses.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not valid_until.empty and valid_until.notna().any():
        put("license_days_to_expiry", max(0.0, (valid_until.min() - as_of).days))
    else:
        put("license_days_to_expiry", 0.0)
    tenders = _as_of(_company_frame(grouped, "tenders", company_id), "tenders", as_of)
    put("tender_count", len(tenders))
    results = tenders["status"].astype(str).str.lower() if "status" in tenders.columns else pd.Series(dtype=str)
    put("tender_win_rate", _share(float(results.str.contains("won|выигран|исполнен", regex=True).sum()), len(tenders)))
    put("tender_amount_to_revenue", _ratio(_sum(tenders, "amount_rub"), revenue))

    insurance = _as_of(_company_frame(grouped, "insurance_policies", company_id), "insurance_policies", as_of)
    put("insurance_coverage_to_revenue", _ratio(_sum(insurance, "insured_amount_rub"), revenue))
    put("insurance_premium_to_revenue", _ratio(_sum(insurance, "premium_rub"), revenue))
    fuel = _as_of(_company_frame(grouped, "fuel_cards", company_id), "fuel_cards", as_of)
    put("fuel_spend_to_monthly_revenue", _ratio(_sum(fuel, "monthly_spend_rub"), monthly))
    telematics = _as_of(_company_frame(grouped, "telematics", company_id), "telematics", as_of)
    put("telematics_mileage", _sum(telematics, "mileage_km"))
    put("telematics_harsh_events", _sum(telematics, "harsh_events"))
    iot = _as_of(_company_frame(grouped, "iot_sensors", company_id), "iot_sensors", as_of)
    iot_status = iot["status"].astype(str).str.lower() if "status" in iot.columns else pd.Series(dtype=str)
    put("iot_alert_count", float((~iot_status.isin({"ok", "normal", "active"})).sum()))

    accounting = _as_of(_company_frame(grouped, "accounting_entries", company_id), "accounting_entries", as_of)
    debit = accounting["debit_account"].astype(str) if "debit_account" in accounting.columns else pd.Series(dtype=str)
    credit = accounting["credit_account"].astype(str) if "credit_account" in accounting.columns else pd.Series(dtype=str)
    accounting_amounts = _numeric(accounting, "amount_rub")
    accounting_revenue = _sum_masked(accounting_amounts, debit.str.startswith("90") | credit.str.startswith("90"))
    accounting_expense = _sum_masked(accounting_amounts, debit.str.startswith(("20", "26", "44", "60", "68", "69")))
    put("accounting_revenue_to_annual", _ratio(accounting_revenue, revenue))
    put("accounting_expense_to_annual", _ratio(accounting_expense, revenue))
    put("accounting_margin", _ratio(accounting_revenue - accounting_expense, accounting_revenue, cap=1.0))
    put("accounting_entry_count", len(accounting))

    management = _latest(_company_frame(grouped, "management_reports", company_id), "management_reports", as_of)
    put("management_revenue_to_annual", _ratio(_first(management, "revenue_rub"), revenue))
    management_revenue = _first(management, "revenue_rub")
    put("management_margin", _ratio(_first(management, "profit_rub"), management_revenue, cap=1.0))

    marketplace = _as_of(_company_frame(grouped, "marketplace_sales", company_id), "marketplace_sales", as_of)
    put("marketplace_revenue_to_annual", _ratio(_sum(marketplace, "revenue_rub"), revenue))
    put("marketplace_orders", _sum(marketplace, "orders_count"))
    put("marketplace_return_rate", _share(_sum(marketplace, "returns_count"), _sum(marketplace, "orders_count")))
    put("marketplace_rating", _mean(marketplace, "rating"))

    ofd = _as_of(_company_frame(grouped, "ofd_receipts", company_id), "ofd_receipts", as_of)
    put("ofd_revenue_to_annual", _ratio(_sum(ofd, "amount_rub"), revenue))
    put("ofd_receipt_count", len(ofd))

    warehouse = _latest(_company_frame(grouped, "warehouse_stock", company_id), "warehouse_stock", as_of)
    put("warehouse_stock_to_revenue", _ratio(_first(warehouse, "stock_value_rub"), revenue))
    put("warehouse_turnover_days", _first(warehouse, "turnover_days"))

    payments = _latest(_company_frame(grouped, "payment_services", company_id), "payment_services", as_of)
    put("payment_turnover_to_annual", _ratio(_first(payments, "monthly_turnover_rub") * 12.0, revenue))

    accounting_systems = _latest(_company_frame(grouped, "accounting_systems", company_id), "accounting_systems", as_of)
    put("accounting_data_quality", _first(accounting_systems, "data_quality"))

    website = _latest(_company_frame(grouped, "website_metrics", company_id), "website_metrics", as_of)
    website_all = _as_of(_company_frame(grouped, "website_metrics", company_id), "website_metrics", as_of).copy()
    if not website_all.empty:
        website_all["_period"] = _parse_dates(website_all["period"])
        website_all = website_all.sort_values("_period")
    put("website_visits", _first(website, "visits"))
    put("website_conversion", _first(website, "conversion_rate"))
    put("website_traffic_growth", _growth(_first(website, "visits"), _first(website_all.iloc[[-2]] if len(website_all) > 1 else website_all.iloc[0:0], "visits")))
    put("domain_age_months", _max(_company_frame(grouped, "website_metrics", company_id), "domain_age_months") if "domain_age_months" in _company_frame(grouped, "website_metrics", company_id).columns else 0.0)

    reputation = _as_of(_company_frame(grouped, "reputation", company_id), "reputation", as_of)
    put("reputation_rating", _mean(reputation, "rating"))
    put("negative_review_share", _share(_sum(reputation, "negative_mentions"), _sum(reputation, "reviews_count")))

    hr = _latest(_company_frame(grouped, "hr_metrics", company_id), "hr_metrics", as_of)
    hr_headcount = _first(hr, "headcount")
    put("hr_headcount", hr_headcount)
    put("hr_turnover", _share(_first(hr, "fires"), hr_headcount))
    put("hr_vacancy_rate", _share(_first(hr, "vacancies"), hr_headcount))
    put("hr_avg_salary_to_monthly_revenue", _ratio(_first(hr, "average_salary_rub"), monthly))

    logistics = _latest(_company_frame(grouped, "logistics", company_id), "logistics", as_of)
    put("logistics_delivery_days", _first(logistics, "average_delivery_days"))
    put("logistics_cost_ratio", _ratio(_first(logistics, "logistics_cost_rub") * 12.0, revenue))

    utilities = _latest(_company_frame(grouped, "utilities", company_id), "utilities", as_of)
    put("utilities_debt_ratio", _share(_first(utilities, "debt_rub"), _first(utilities, "amount_rub")))

    mobile = _latest(_company_frame(grouped, "mobile_operator", company_id), "mobile_operator", as_of)
    put("mobile_tenure_months", _first(mobile, "tenure_months"))
    put("mobile_payment_delinquency", _flag(_first(mobile, "debt_rub") > 0))

    social = _company_frame(grouped, "social_media", company_id)
    put("social_followers", _sum(social, "followers"))
    put("social_engagement", _mean(social, "engagement_rate"))

    news = _as_of(_company_frame(grouped, "news_mentions", company_id), "news_mentions", as_of)
    sentiment = news["sentiment"].astype(str).str.lower() if "sentiment" in news.columns else pd.Series(dtype=str)
    put("news_negative_share", _share(float(sentiment.eq("negative").sum()), len(news)))

    franchise = _as_of(_company_frame(grouped, "franchise_contracts", company_id), "franchise_contracts", as_of)
    put("franchise_outlets", _sum(franchise, "outlets_count"))
    grants = _as_of(_company_frame(grouped, "grants_subsidies", company_id), "grants_subsidies", as_of)
    grant_status = grants["status"].astype(str).str.lower() if "status" in grants.columns else pd.Series(dtype=str)
    put("grant_total_to_revenue", _ratio(_sum_masked(_numeric(grants, "amount_rub"), grant_status.eq("received")), revenue))
    certifications = _as_of(_company_frame(grouped, "certifications", company_id), "certifications", as_of)
    put("certification_count", len(certifications))
    memberships = _as_of(_company_frame(grouped, "industry_memberships", company_id), "industry_memberships", as_of)
    put("industry_membership_count", len(memberships))
    trade_networks = _as_of(_company_frame(grouped, "trade_networks", company_id), "trade_networks", as_of)
    put("trade_network_revenue_share", _sum(trade_networks, "revenue_share_percent") / 100.0)

    customs = _as_of(_company_frame(grouped, "customs_declarations", company_id), "customs_declarations", as_of)
    put("customs_declaration_count", len(customs))
    put("customs_value_to_revenue", _ratio(_sum(customs, "value_rub"), revenue))
    intellectual = _as_of(_company_frame(grouped, "intellectual_property", company_id), "intellectual_property", as_of)
    put("intellectual_property_count", len(intellectual))
    gosuslugi = _as_of(_company_frame(grouped, "gosuslugi_events", company_id), "gosuslugi_events", as_of)
    put("gosuslugi_event_count", len(gosuslugi))
    ratings = _as_of(_company_frame(grouped, "rating_agency_ratings", company_id), "rating_agency_ratings", as_of)
    rating_values = ratings["rating"].astype(str).str.upper() if "rating" in ratings.columns else pd.Series(dtype=str)
    put("rating_score", float(rating_values.map(RATING_SCORE).fillna(0.0).max()) if not rating_values.empty else 0.0)
    checks = _as_of(_company_frame(grouped, "counterparty_checks", company_id), "counterparty_checks", as_of)
    put("counterparty_risk_share", _mean(checks, "risk_score"))
    business = _as_of(_company_frame(grouped, "business_history", company_id), "business_history", as_of)
    business_types = business["event_type"].astype(str).str.lower() if "event_type" in business.columns else pd.Series(dtype=str)
    put("business_negative_share", _share(float(business_types.str.contains("negative|risk|bankrupt", regex=True).sum()), len(business)))
    geo = _as_of(_company_frame(grouped, "geo_metrics", company_id), "geo_metrics", as_of)
    put("geo_rating", _mean(geo, "rating"))
    put("geo_reviews_count", _sum(geo, "reviews_count"))

    applications = _company_frame(grouped, "applications", company_id)
    prior_apps = pd.DataFrame()
    if not applications.empty and "submitted_at" in applications.columns:
        app_dates = _parse_dates(applications["submitted_at"])
        prior_apps = applications.loc[app_dates < as_of].copy()
    prior_ids = set(prior_apps["application_id"].astype(str)) if "application_id" in prior_apps.columns else set()
    put("prior_application_count", len(prior_apps))
    prior_status = prior_apps["status"].astype(str).str.lower() if "status" in prior_apps.columns else pd.Series(dtype=str)
    approved = prior_status.isin({"approved", "offer_sent", "offer_accepted", "issued"}).sum()
    declined = prior_status.isin({"rejected", "declined"}).sum()
    put("prior_approval_rate", _share(float(approved), len(prior_apps)))
    put("prior_decline_rate", _share(float(declined), len(prior_apps)))

    offers = _company_frame(grouped, "offers", company_id)
    prior_offers = offers.loc[offers["application_id"].astype(str).isin(prior_ids)] if not offers.empty and "application_id" in offers.columns else offers.iloc[0:0]
    offer_status = prior_offers["status"].astype(str).str.lower() if "status" in prior_offers.columns else pd.Series(dtype=str)
    put("prior_offer_acceptance_rate", _share(float(offer_status.str.contains("accept|принят", regex=True).sum()), len(prior_offers)))

    contracts = _company_frame(grouped, "loan_contracts", company_id)
    prior_contracts = contracts.loc[contracts["application_id"].astype(str).isin(prior_ids)] if not contracts.empty and "application_id" in contracts.columns else contracts.iloc[0:0]
    put("prior_contract_count", len(prior_contracts))
    put("prior_contract_amount_to_revenue", _ratio(_sum(prior_contracts, "amount_rub"), revenue))
    put("prior_contract_avg_rate", _mean(prior_contracts, "rate_percent"))

    scoring = _company_frame(grouped, "scoring_results", company_id)
    prior_scoring = scoring.loc[scoring["application_id"].astype(str).isin(prior_ids)] if not scoring.empty and "application_id" in scoring.columns else scoring.iloc[0:0]
    put("prior_scoring_pd_mean", _mean(prior_scoring, "pd"))
    put("prior_scoring_score_mean", _mean(prior_scoring, "score"))

    documents = _as_of(_company_frame(grouped, "documents", company_id), "documents", as_of)
    put("document_count", len(documents))
    document_status = documents["status"].astype(str).str.lower() if "status" in documents.columns else pd.Series(dtype=str)
    put("verified_document_share", _share(float(document_status.isin({"verified", "accepted"}).sum()), len(documents)))
    put("rejected_document_share", _share(float(document_status.eq("rejected").sum()), len(documents)))

    events = _company_frame(grouped, "application_events", company_id)
    prior_events = events.loc[events["application_id"].astype(str).isin(prior_ids)] if not events.empty and "application_id" in events.columns else events.iloc[0:0]
    put("prior_application_event_count", len(prior_events))
    decision_apps = prior_apps.loc[prior_apps["decision_at"].notna()] if "decision_at" in prior_apps.columns else prior_apps.iloc[0:0]
    if not decision_apps.empty and "submitted_at" in decision_apps.columns:
        durations = (_parse_dates(decision_apps["decision_at"]) - _parse_dates(decision_apps["submitted_at"])).dt.total_seconds() / 86400.0
        put("prior_time_to_decision_days", float(durations.mean()) if durations.notna().any() else 0.0)
    else:
        put("prior_time_to_decision_days", 0.0)

    collateral = _company_frame(grouped, "collateral_offers", company_id)
    current_id = str(application.get("application_id", ""))
    current_collateral = collateral.loc[collateral["application_id"].astype(str).eq(current_id)] if not empty_frame(collateral) and "application_id" in collateral.columns else collateral.iloc[0:0]
    put("collateral_offer_count", len(current_collateral))
    put("collateral_coverage_ratio", _ratio(_sum(current_collateral, "market_value_rub"), float(application.get("requested_amount_rub", 0.0) or 0.0)))

    audit = _as_of(_company_frame(grouped, "audit_log", company_id), "audit_log", as_of)
    put("audit_event_count", len(audit))
    audit_dates = _parse_dates(audit["created_at"]) if "created_at" in audit.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not audit_dates.empty and audit_dates.notna().any():
        put("audit_last_event_days", max(0.0, (as_of - audit_dates.max()).days))
    else:
        put("audit_last_event_days", 0.0)

    user_id = str(application.get("user_id", ""))
    applicant = users.loc[users["user_id"].astype(str).eq(user_id)] if not users.empty and "user_id" in users.columns else users.iloc[0:0]
    if applicant.empty and not users.empty:
        applicant = users.iloc[[0]]
    birth_date = _parse_dates(applicant["birth_date"]) if "birth_date" in applicant.columns else pd.Series(dtype="datetime64[ns, UTC]")
    if not birth_date.empty and birth_date.notna().any():
        put("applicant_age_years", max(0.0, (as_of - birth_date.iloc[0]).days / 365.25))
    else:
        put("applicant_age_years", 0.0)
    put("applicant_is_signer", _first(applicant, "is_signer"))
    put("applicant_is_beneficial_owner", _first(applicant, "is_beneficial_owner"))
    applicant_consents = consents.loc[consents["user_id"].astype(str).eq(user_id)] if not consents.empty and "user_id" in consents.columns else consents.iloc[0:0]
    put("applicant_consent_count", len(applicant_consents))
    biometrics = _as_of(_company_frame(grouped, "biometric_checks", company_id), "biometric_checks", as_of)
    applicant_biometrics = biometrics.loc[biometrics["user_id"].astype(str).eq(user_id)] if not biometrics.empty and "user_id" in biometrics.columns else biometrics.iloc[0:0]
    biometric_status = applicant_biometrics["status"].astype(str).str.lower() if "status" in applicant_biometrics.columns else pd.Series(dtype=str)
    put("applicant_biometric_success_rate", _share(float(biometric_status.eq("passed").sum()), len(applicant_biometrics)))
    put("applicant_biometric_liveness_score", _mean(applicant_biometrics, "liveness_score"))

    for name in NEW_NUMERIC_FEATURES:
        values.setdefault(name, 0.0)
    return values


def empty_frame(frame: pd.DataFrame) -> bool:
    return frame is None or frame.empty
