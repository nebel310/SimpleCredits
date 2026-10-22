CREATE TABLE IF NOT EXISTS "companies" (
    "company_id" TEXT PRIMARY KEY,
    "inn" TEXT,
    "ogrn" TEXT,
    "kpp" TEXT,
    "legal_name" TEXT,
    "short_name" TEXT,
    "legal_form" TEXT,
    "segment" TEXT,
    "status" TEXT,
    "registration_date" TEXT,
    "region" TEXT,
    "city" TEXT,
    "address" TEXT,
    "okved_main" TEXT,
    "okved_name" TEXT,
    "industry" TEXT,
    "employee_count" INTEGER,
    "annual_revenue_rub" INTEGER,
    "website" TEXT,
    "phone" TEXT,
    "email" TEXT,
    "tax_regime" TEXT,
    "created_at" TEXT
);

CREATE TABLE IF NOT EXISTS "users" (
    "user_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "role" TEXT,
    "full_name" TEXT,
    "birth_date" TEXT,
    "inn" TEXT,
    "phone" TEXT,
    "email" TEXT,
    "position" TEXT,
    "is_signer" INTEGER,
    "is_beneficial_owner" INTEGER
);

CREATE TABLE IF NOT EXISTS "founders" (
    "founder_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "founder_type" TEXT,
    "name" TEXT,
    "inn" TEXT,
    "share_percent" REAL,
    "is_beneficial_owner" INTEGER,
    "since_date" TEXT
);

CREATE TABLE IF NOT EXISTS "managers" (
    "manager_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "full_name" TEXT,
    "position" TEXT,
    "inn" TEXT,
    "since_date" TEXT,
    "is_disqualified" INTEGER
);

CREATE TABLE IF NOT EXISTS "consents" (
    "consent_id" TEXT PRIMARY KEY,
    "user_id" TEXT,
    "company_id" TEXT,
    "consent_type" TEXT,
    "granted_at" TEXT,
    "expires_at" TEXT,
    "status" TEXT,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "egrul_records" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "inn" TEXT,
    "ogrn" TEXT,
    "full_name" TEXT,
    "short_name" TEXT,
    "status" TEXT,
    "registration_date" TEXT,
    "address" TEXT,
    "okved_main" TEXT,
    "okved_additional" TEXT,
    "authorized_capital_rub" INTEGER,
    "founders_json" TEXT,
    "managers_json" TEXT,
    "changes_json" TEXT,
    "unreliable_record_flag" INTEGER,
    "mass_address_flag" INTEGER,
    "mass_manager_flag" INTEGER,
    "disqualified_manager_flag" INTEGER,
    "updated_at" TEXT
);

CREATE TABLE IF NOT EXISTS "sme_registry" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "category" TEXT,
    "included_at" TEXT,
    "excluded_at" TEXT,
    "employee_count" INTEGER,
    "revenue_rub" INTEGER,
    "region" TEXT,
    "okved_main" TEXT,
    "status" TEXT,
    "benefits_json" TEXT
);

CREATE TABLE IF NOT EXISTS "financial_statements" (
    "statement_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "year" INTEGER,
    "period" TEXT,
    "form" TEXT,
    "revenue_rub" INTEGER,
    "cost_of_sales_rub" INTEGER,
    "gross_profit_rub" INTEGER,
    "operating_expenses_rub" INTEGER,
    "ebitda_rub" INTEGER,
    "depreciation_rub" INTEGER,
    "interest_rub" INTEGER,
    "tax_rub" INTEGER,
    "net_profit_rub" INTEGER,
    "total_assets_rub" INTEGER,
    "current_assets_rub" INTEGER,
    "cash_rub" INTEGER,
    "accounts_receivable_rub" INTEGER,
    "inventory_rub" INTEGER,
    "total_liabilities_rub" INTEGER,
    "current_liabilities_rub" INTEGER,
    "debt_rub" INTEGER,
    "equity_rub" INTEGER,
    "audit_flag" INTEGER,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "tax_reports" (
    "report_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "year" INTEGER,
    "quarter" INTEGER,
    "tax_type" TEXT,
    "taxable_base_rub" INTEGER,
    "tax_amount_rub" INTEGER,
    "paid_amount_rub" INTEGER,
    "debt_amount_rub" INTEGER,
    "status" TEXT,
    "submitted_at" TEXT
);

CREATE TABLE IF NOT EXISTS "sfr_reports" (
    "report_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "year" INTEGER,
    "insured_employees" INTEGER,
    "payroll_fund_rub" INTEGER,
    "contributions_rub" INTEGER,
    "debt_rub" INTEGER,
    "risk_class" TEXT,
    "benefits_json" TEXT
);

CREATE TABLE IF NOT EXISTS "fns_status" (
    "status_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "tax_debt_rub" INTEGER,
    "unpaid_tax_count" INTEGER,
    "blocked_accounts_count" INTEGER,
    "late_payments_12m" INTEGER,
    "special_regime" TEXT,
    "risk_level" TEXT,
    "risk_flags_json" TEXT,
    "updated_at" TEXT
);

CREATE TABLE IF NOT EXISTS "rosstat_indicators" (
    "indicator_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "indicator" TEXT,
    "value" REAL,
    "unit" TEXT,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "intellectual_property" (
    "ip_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "ip_type" TEXT,
    "number" TEXT,
    "title" TEXT,
    "status" TEXT,
    "registered_at" TEXT,
    "valid_until" TEXT
);

CREATE TABLE IF NOT EXISTS "customs_declarations" (
    "declaration_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "declaration_number" TEXT,
    "declaration_date" TEXT,
    "direction" TEXT,
    "country" TEXT,
    "hs_code" TEXT,
    "goods_json" TEXT,
    "value_rub" INTEGER,
    "currency" TEXT,
    "customs_payments_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "gosuslugi_events" (
    "event_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "user_id" TEXT,
    "service" TEXT,
    "status" TEXT,
    "requested_at" TEXT,
    "completed_at" TEXT,
    "payload_json" TEXT
);

CREATE TABLE IF NOT EXISTS "rating_agency_ratings" (
    "rating_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "agency" TEXT,
    "rating" TEXT,
    "outlook" TEXT,
    "assigned_at" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "counterparty_checks" (
    "check_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "service" TEXT,
    "checked_at" TEXT,
    "risk_score" REAL,
    "risk_level" TEXT,
    "risk_flags_json" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "business_history" (
    "history_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "event_date" TEXT,
    "event_type" TEXT,
    "description" TEXT,
    "source" TEXT,
    "payload_json" TEXT
);

CREATE TABLE IF NOT EXISTS "domain_whois" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "domain" TEXT,
    "registrar" TEXT,
    "created_at" TEXT,
    "expires_at" TEXT,
    "status" TEXT,
    "privacy_flag" INTEGER
);

CREATE TABLE IF NOT EXISTS "geo_metrics" (
    "metric_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "source" TEXT,
    "rating" REAL,
    "reviews_count" INTEGER,
    "checkins_month" INTEGER,
    "photos_count" INTEGER,
    "last_updated_at" TEXT
);

CREATE TABLE IF NOT EXISTS "bank_accounts" (
    "account_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "bank_name" TEXT,
    "account_number" TEXT,
    "currency" TEXT,
    "account_type" TEXT,
    "opened_at" TEXT,
    "status" TEXT,
    "balance_rub" INTEGER,
    "average_balance_rub" INTEGER,
    "min_balance_rub" INTEGER,
    "max_balance_rub" INTEGER,
    "overdraft_limit_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "bank_transactions" (
    "transaction_id" TEXT PRIMARY KEY,
    "account_id" TEXT,
    "company_id" TEXT,
    "transaction_date" TEXT,
    "direction" TEXT,
    "amount_rub" INTEGER,
    "currency" TEXT,
    "counterparty_name" TEXT,
    "counterparty_inn" TEXT,
    "purpose" TEXT,
    "category" TEXT,
    "channel" TEXT,
    "mcc" TEXT,
    "balance_after_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "currency_operations" (
    "operation_id" TEXT PRIMARY KEY,
    "account_id" TEXT,
    "company_id" TEXT,
    "operation_date" TEXT,
    "direction" TEXT,
    "currency" TEXT,
    "amount_original" REAL,
    "rate" REAL,
    "amount_rub" INTEGER,
    "purpose" TEXT,
    "counterparty_name" TEXT
);

CREATE TABLE IF NOT EXISTS "bank_products" (
    "product_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "product_type" TEXT,
    "bank_name" TEXT,
    "amount_rub" INTEGER,
    "outstanding_rub" INTEGER,
    "rate_percent" REAL,
    "opened_at" TEXT,
    "closed_at" TEXT,
    "monthly_payment_rub" INTEGER,
    "status" TEXT,
    "days_past_due" INTEGER
);

CREATE TABLE IF NOT EXISTS "bank_internal_history" (
    "history_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "relationship_start" TEXT,
    "segment" TEXT,
    "manager_name" TEXT,
    "previous_applications" INTEGER,
    "approved_count" INTEGER,
    "declined_count" INTEGER,
    "defaults_count" INTEGER,
    "restructures_count" INTEGER,
    "aml_flags_json" TEXT,
    "risk_flags_json" TEXT,
    "digital_activity_score" REAL,
    "last_activity_at" TEXT,
    "client_rating" TEXT
);

CREATE TABLE IF NOT EXISTS "credit_bureau_reports" (
    "report_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "bki_name" TEXT,
    "report_date" TEXT,
    "credit_score" INTEGER,
    "active_loans" INTEGER,
    "total_outstanding_rub" INTEGER,
    "monthly_payment_rub" INTEGER,
    "max_days_past_due_12m" INTEGER,
    "current_past_due" INTEGER,
    "restructures_count" INTEGER,
    "inquiries_6m" INTEGER,
    "applications_6m" INTEGER,
    "fraud_flag" INTEGER
);

CREATE TABLE IF NOT EXISTS "credit_bureau_loans" (
    "loan_id" TEXT PRIMARY KEY,
    "report_id" TEXT,
    "company_id" TEXT,
    "lender" TEXT,
    "loan_type" TEXT,
    "amount_rub" INTEGER,
    "outstanding_rub" INTEGER,
    "monthly_payment_rub" INTEGER,
    "opened_at" TEXT,
    "closed_at" TEXT,
    "status" TEXT,
    "days_past_due" INTEGER,
    "currency" TEXT,
    "collateral" TEXT
);

CREATE TABLE IF NOT EXISTS "credit_inquiries" (
    "inquiry_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "inquiry_date" TEXT,
    "lender" TEXT,
    "purpose" TEXT,
    "approved" INTEGER,
    "amount_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "court_cases" (
    "case_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "role" TEXT,
    "court_name" TEXT,
    "case_number" TEXT,
    "category" TEXT,
    "amount_rub" INTEGER,
    "filed_at" TEXT,
    "status" TEXT,
    "outcome" TEXT,
    "last_hearing_at" TEXT,
    "opponent_name" TEXT
);

CREATE TABLE IF NOT EXISTS "enforcement_proceedings" (
    "enforcement_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "fssp_number" TEXT,
    "amount_rub" INTEGER,
    "opened_at" TEXT,
    "status" TEXT,
    "department" TEXT,
    "subject" TEXT,
    "paid_amount_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "bankruptcy_events" (
    "event_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "event_type" TEXT,
    "stage" TEXT,
    "filed_at" TEXT,
    "status" TEXT,
    "creditor_claims_rub" INTEGER,
    "manager_name" TEXT,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "real_estate" (
    "property_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "property_type" TEXT,
    "cadastral_number" TEXT,
    "address" TEXT,
    "area_sqm" REAL,
    "cadastral_value_rub" INTEGER,
    "market_value_rub" INTEGER,
    "ownership_type" TEXT,
    "encumbrances_json" TEXT,
    "registered_at" TEXT
);

CREATE TABLE IF NOT EXISTS "vehicles" (
    "vehicle_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "vehicle_type" TEXT,
    "brand" TEXT,
    "model" TEXT,
    "year" INTEGER,
    "vin" TEXT,
    "plate_number" TEXT,
    "market_value_rub" INTEGER,
    "pledge_flag" INTEGER,
    "restrictions_json" TEXT
);

CREATE TABLE IF NOT EXISTS "licenses" (
    "license_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "license_type" TEXT,
    "number" TEXT,
    "issued_at" TEXT,
    "valid_until" TEXT,
    "status" TEXT,
    "regulator" TEXT,
    "activity" TEXT
);

CREATE TABLE IF NOT EXISTS "tenders" (
    "tender_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "platform" TEXT,
    "procurement_number" TEXT,
    "customer_name" TEXT,
    "amount_rub" INTEGER,
    "status" TEXT,
    "published_at" TEXT,
    "result" TEXT,
    "contract_amount_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "insurance_policies" (
    "policy_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "insurance_type" TEXT,
    "insurer" TEXT,
    "premium_rub" INTEGER,
    "insured_amount_rub" INTEGER,
    "valid_from" TEXT,
    "valid_until" TEXT,
    "status" TEXT,
    "coverage_json" TEXT
);

CREATE TABLE IF NOT EXISTS "fuel_cards" (
    "card_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "provider" TEXT,
    "cards_count" INTEGER,
    "monthly_spend_rub" INTEGER,
    "last_transaction_at" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "telematics" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "vehicle_id" TEXT,
    "provider" TEXT,
    "period" TEXT,
    "mileage_km" REAL,
    "idle_hours" REAL,
    "fuel_consumption_l" REAL,
    "harsh_events" INTEGER,
    "last_signal_at" TEXT
);

CREATE TABLE IF NOT EXISTS "iot_sensors" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "sensor_type" TEXT,
    "metric_name" TEXT,
    "value" REAL,
    "unit" TEXT,
    "recorded_at" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "accounting_entries" (
    "entry_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "debit_account" TEXT,
    "credit_account" TEXT,
    "amount_rub" INTEGER,
    "counterparty_name" TEXT,
    "document_name" TEXT,
    "description" TEXT
);

CREATE TABLE IF NOT EXISTS "management_reports" (
    "report_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "revenue_rub" INTEGER,
    "expenses_rub" INTEGER,
    "profit_rub" INTEGER,
    "cash_rub" INTEGER,
    "accounts_receivable_rub" INTEGER,
    "accounts_payable_rub" INTEGER,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "accounting_systems" (
    "connection_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "system" TEXT,
    "connected" INTEGER,
    "last_sync_at" TEXT,
    "data_quality" REAL,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "marketplace_sales" (
    "sale_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "marketplace" TEXT,
    "period" TEXT,
    "orders_count" INTEGER,
    "revenue_rub" INTEGER,
    "returns_count" INTEGER,
    "returns_amount_rub" INTEGER,
    "average_check_rub" INTEGER,
    "rating" REAL,
    "commission_rub" INTEGER,
    "penalties_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "payment_services" (
    "service_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "provider" TEXT,
    "connected" INTEGER,
    "monthly_turnover_rub" INTEGER,
    "average_ticket_rub" INTEGER,
    "refund_rate" REAL,
    "connected_at" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "ofd_receipts" (
    "receipt_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "receipt_date" TEXT,
    "amount_rub" INTEGER,
    "items_count" INTEGER,
    "payment_type" TEXT,
    "mcc" TEXT,
    "city" TEXT
);

CREATE TABLE IF NOT EXISTS "warehouse_stock" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "sku_count" INTEGER,
    "stock_value_rub" INTEGER,
    "turnover_days" REAL,
    "slow_moving_share" REAL,
    "stockout_rate" REAL
);

CREATE TABLE IF NOT EXISTS "website_metrics" (
    "metric_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "visits" INTEGER,
    "unique_visitors" INTEGER,
    "conversion_rate" REAL,
    "average_order_value_rub" INTEGER,
    "ad_spend_rub" INTEGER,
    "traffic_sources_json" TEXT,
    "domain_age_months" INTEGER
);

CREATE TABLE IF NOT EXISTS "reputation" (
    "reputation_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "source" TEXT,
    "rating" REAL,
    "reviews_count" INTEGER,
    "negative_mentions" INTEGER,
    "last_review_at" TEXT,
    "sentiment" TEXT
);

CREATE TABLE IF NOT EXISTS "hr_metrics" (
    "metric_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "headcount" INTEGER,
    "vacancies" INTEGER,
    "hires" INTEGER,
    "fires" INTEGER,
    "average_salary_rub" INTEGER,
    "source" TEXT
);

CREATE TABLE IF NOT EXISTS "logistics" (
    "metric_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "shipments_count" INTEGER,
    "returns_count" INTEGER,
    "average_delivery_days" REAL,
    "regions_json" TEXT,
    "logistics_cost_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "utilities" (
    "metric_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "period" TEXT,
    "electricity_kwh" REAL,
    "water_m3" REAL,
    "amount_rub" INTEGER,
    "debt_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "mobile_operator" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "operator" TEXT,
    "tenure_months" INTEGER,
    "monthly_spend_rub" INTEGER,
    "payments_on_time" INTEGER,
    "debt_rub" INTEGER
);

CREATE TABLE IF NOT EXISTS "social_media" (
    "record_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "platform" TEXT,
    "followers" INTEGER,
    "posts_per_month" INTEGER,
    "engagement_rate" REAL,
    "last_post_at" TEXT
);

CREATE TABLE IF NOT EXISTS "news_mentions" (
    "mention_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "mention_date" TEXT,
    "source" TEXT,
    "title" TEXT,
    "sentiment" TEXT,
    "url" TEXT
);

CREATE TABLE IF NOT EXISTS "franchise_contracts" (
    "contract_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "franchisor" TEXT,
    "contract_date" TEXT,
    "outlets_count" INTEGER,
    "royalty_percent" REAL,
    "status" TEXT,
    "terms_json" TEXT
);

CREATE TABLE IF NOT EXISTS "grants_subsidies" (
    "grant_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "program" TEXT,
    "amount_rub" INTEGER,
    "received_at" TEXT,
    "status" TEXT,
    "purpose" TEXT
);

CREATE TABLE IF NOT EXISTS "certifications" (
    "certification_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "standard" TEXT,
    "certificate_number" TEXT,
    "issued_at" TEXT,
    "valid_until" TEXT,
    "status" TEXT,
    "certification_body" TEXT
);

CREATE TABLE IF NOT EXISTS "industry_memberships" (
    "membership_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "association" TEXT,
    "member_since" TEXT,
    "status" TEXT,
    "role" TEXT
);

CREATE TABLE IF NOT EXISTS "trade_networks" (
    "contract_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "network" TEXT,
    "contract_date" TEXT,
    "revenue_share_percent" REAL,
    "status" TEXT,
    "payment_delay_days" INTEGER
);

CREATE TABLE IF NOT EXISTS "biometric_checks" (
    "check_id" TEXT PRIMARY KEY,
    "user_id" TEXT,
    "company_id" TEXT,
    "check_type" TEXT,
    "provider" TEXT,
    "status" TEXT,
    "checked_at" TEXT,
    "liveness_score" REAL
);

CREATE TABLE IF NOT EXISTS "applications" (
    "application_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "user_id" TEXT,
    "product_type" TEXT,
    "requested_amount_rub" INTEGER,
    "term_months" INTEGER,
    "purpose" TEXT,
    "submitted_at" TEXT,
    "status" TEXT,
    "decision" TEXT,
    "decision_at" TEXT,
    "rejection_reason" TEXT
);

CREATE TABLE IF NOT EXISTS "self_assessments" (
    "assessment_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "company_id" TEXT,
    "declared_annual_revenue_rub" INTEGER,
    "declared_monthly_revenue_rub" INTEGER,
    "declared_monthly_expenses_rub" INTEGER,
    "declared_total_debt_rub" INTEGER,
    "declared_monthly_debt_payment_rub" INTEGER,
    "declared_employees" INTEGER,
    "declared_net_profit_rub" INTEGER,
    "obligations_json" TEXT,
    "source" TEXT,
    "created_at" TEXT
);

CREATE TABLE IF NOT EXISTS "collateral_offers" (
    "collateral_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "company_id" TEXT,
    "collateral_type" TEXT,
    "description" TEXT,
    "market_value_rub" INTEGER,
    "ownership_type" TEXT,
    "encumbrance" TEXT,
    "insurance_flag" INTEGER,
    "accepted_flag" INTEGER
);

CREATE TABLE IF NOT EXISTS "application_events" (
    "event_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "stage" TEXT,
    "status" TEXT,
    "actor" TEXT,
    "created_at" TEXT,
    "comment" TEXT
);

CREATE TABLE IF NOT EXISTS "scoring_results" (
    "scoring_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "model_version" TEXT,
    "score" INTEGER,
    "pd" REAL,
    "risk_grade" TEXT,
    "reason_codes_json" TEXT,
    "created_at" TEXT
);

CREATE TABLE IF NOT EXISTS "policy_decisions" (
    "decision_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "decision" TEXT,
    "reason_codes_json" TEXT,
    "conditions_json" TEXT,
    "created_at" TEXT
);

CREATE TABLE IF NOT EXISTS "offers" (
    "offer_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "approved_amount_rub" INTEGER,
    "rate_percent" REAL,
    "term_months" INTEGER,
    "monthly_payment_rub" INTEGER,
    "conditions_json" TEXT,
    "valid_until" TEXT,
    "status" TEXT
);

CREATE TABLE IF NOT EXISTS "loan_contracts" (
    "contract_id" TEXT PRIMARY KEY,
    "application_id" TEXT,
    "company_id" TEXT,
    "amount_rub" INTEGER,
    "rate_percent" REAL,
    "term_months" INTEGER,
    "issued_at" TEXT,
    "status" TEXT,
    "payment_schedule_json" TEXT
);

CREATE TABLE IF NOT EXISTS "documents" (
    "document_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "application_id" TEXT,
    "document_type" TEXT,
    "file_name" TEXT,
    "file_path" TEXT,
    "uploaded_at" TEXT,
    "status" TEXT,
    "extracted_data_json" TEXT
);

CREATE TABLE IF NOT EXISTS "audit_log" (
    "log_id" TEXT PRIMARY KEY,
    "company_id" TEXT,
    "application_id" TEXT,
    "event_type" TEXT,
    "actor" TEXT,
    "payload_json" TEXT,
    "created_at" TEXT
);

CREATE INDEX IF NOT EXISTS "idx_users_company_id" ON "users" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_founders_company_id" ON "founders" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_managers_company_id" ON "managers" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_consents_company_id" ON "consents" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_egrul_records_company_id" ON "egrul_records" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_sme_registry_company_id" ON "sme_registry" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_financial_statements_company_id" ON "financial_statements" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_tax_reports_company_id" ON "tax_reports" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_sfr_reports_company_id" ON "sfr_reports" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_fns_status_company_id" ON "fns_status" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_rosstat_indicators_company_id" ON "rosstat_indicators" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_intellectual_property_company_id" ON "intellectual_property" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_customs_declarations_company_id" ON "customs_declarations" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_gosuslugi_events_company_id" ON "gosuslugi_events" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_rating_agency_ratings_company_id" ON "rating_agency_ratings" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_counterparty_checks_company_id" ON "counterparty_checks" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_business_history_company_id" ON "business_history" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_domain_whois_company_id" ON "domain_whois" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_geo_metrics_company_id" ON "geo_metrics" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_bank_accounts_company_id" ON "bank_accounts" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_bank_transactions_account_id" ON "bank_transactions" ("account_id");

CREATE INDEX IF NOT EXISTS "idx_bank_transactions_company_id" ON "bank_transactions" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_currency_operations_account_id" ON "currency_operations" ("account_id");

CREATE INDEX IF NOT EXISTS "idx_currency_operations_company_id" ON "currency_operations" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_bank_products_company_id" ON "bank_products" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_bank_internal_history_company_id" ON "bank_internal_history" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_credit_bureau_reports_company_id" ON "credit_bureau_reports" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_credit_bureau_loans_report_id" ON "credit_bureau_loans" ("report_id");

CREATE INDEX IF NOT EXISTS "idx_credit_inquiries_company_id" ON "credit_inquiries" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_court_cases_company_id" ON "court_cases" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_enforcement_proceedings_company_id" ON "enforcement_proceedings" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_bankruptcy_events_company_id" ON "bankruptcy_events" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_real_estate_company_id" ON "real_estate" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_vehicles_company_id" ON "vehicles" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_licenses_company_id" ON "licenses" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_tenders_company_id" ON "tenders" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_insurance_policies_company_id" ON "insurance_policies" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_fuel_cards_company_id" ON "fuel_cards" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_telematics_company_id" ON "telematics" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_telematics_vehicle_id" ON "telematics" ("vehicle_id");

CREATE INDEX IF NOT EXISTS "idx_iot_sensors_company_id" ON "iot_sensors" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_accounting_entries_company_id" ON "accounting_entries" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_management_reports_company_id" ON "management_reports" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_accounting_systems_company_id" ON "accounting_systems" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_marketplace_sales_company_id" ON "marketplace_sales" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_payment_services_company_id" ON "payment_services" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_ofd_receipts_company_id" ON "ofd_receipts" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_warehouse_stock_company_id" ON "warehouse_stock" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_website_metrics_company_id" ON "website_metrics" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_reputation_company_id" ON "reputation" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_hr_metrics_company_id" ON "hr_metrics" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_logistics_company_id" ON "logistics" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_utilities_company_id" ON "utilities" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_mobile_operator_company_id" ON "mobile_operator" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_social_media_company_id" ON "social_media" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_news_mentions_company_id" ON "news_mentions" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_franchise_contracts_company_id" ON "franchise_contracts" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_grants_subsidies_company_id" ON "grants_subsidies" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_certifications_company_id" ON "certifications" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_industry_memberships_company_id" ON "industry_memberships" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_trade_networks_company_id" ON "trade_networks" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_biometric_checks_company_id" ON "biometric_checks" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_biometric_checks_user_id" ON "biometric_checks" ("user_id");

CREATE INDEX IF NOT EXISTS "idx_applications_company_id" ON "applications" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_self_assessments_application_id" ON "self_assessments" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_self_assessments_company_id" ON "self_assessments" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_collateral_offers_application_id" ON "collateral_offers" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_collateral_offers_company_id" ON "collateral_offers" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_application_events_application_id" ON "application_events" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_scoring_results_application_id" ON "scoring_results" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_policy_decisions_application_id" ON "policy_decisions" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_offers_application_id" ON "offers" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_loan_contracts_company_id" ON "loan_contracts" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_documents_company_id" ON "documents" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_documents_application_id" ON "documents" ("application_id");

CREATE INDEX IF NOT EXISTS "idx_audit_log_company_id" ON "audit_log" ("company_id");

CREATE INDEX IF NOT EXISTS "idx_audit_log_application_id" ON "audit_log" ("application_id");
