# Data Pipeline: raw SQLite to training table

## Overview

The pipeline converts the synthetic raw data database (`data/raw/simplecredits_raw.db`) into a supervised learning table for credit default prediction.

Key design decisions:

- **As-of slicing.** For every application, all features are computed from data available strictly before `submitted_at`. This prevents label and information leakage.
- **Financial statement availability.** `financial_statements` has no publication timestamp, so a conservative lag is applied: a statement becomes available 90 days after the end of its reporting period (`H1` or `FY`). This prevents using half-year reports before they could be published.
- **Observation horizon.** The label is 1 if a default event occurs within `horizon_days` after submission, 0 if the horizon matures without default, and `censored` otherwise.
- **Approved applications only.** Applications that never reached an approved/issued status are excluded: their labels would incorrectly treat a rejected application as a non-default.
- **One row per application.** The training table has one row per application, with company-level features aggregated at the application timestamp.
- **Reproducibility.** The pipeline writes a manifest with the database SHA-256, table counts, and label statistics.

## Quick start

From the repository root:

```powershell
cd ml
python -m simplecredits.ml.data.pipeline --db ..\data\raw\simplecredits_raw.db --out data\training_table.csv --horizon-days 30
```

Defaults:

- `--db`: `data/raw/simplecredits_raw.db` (resolved relative to repository root)
- `--out`: `ml/data/training_table.csv`
- `--horizon-days`: `30` (matches the synthetic application window so the horizon matures)

The pipeline writes:

- `ml/data/training_table.csv` — training table
- `ml/data/training_table.manifest.json` — dataset manifest

To regenerate the larger development dataset (2000 companies, 24 months, no bulky CSV/JSON/documents):

```powershell
python tools\generate_raw_data.py --out data\raw\large --companies 2000 --months 24 --seed 42 --no-csv --no-json --no-documents
cd ml
python -m simplecredits.ml.data.pipeline --db ..\data\raw\large\simplecredits_raw.db --out data\training_table_large.csv --horizon-days 30
```

## Label logic

The label is derived from multiple sources, in priority order:

1. **Future default** (label=1): a `loan_default_events` row for the same application occurs after `submitted_at` and within the observation horizon.
2. **Future bankruptcy** (label=1): a bankruptcy event occurs after `submitted_at` and within the observation horizon.
3. **Historical defaults** (label=1): the company has `defaults_count > 0` in `bank_internal_history` and `last_activity_at` falls after `submitted_at` and within the observation horizon. This is a fallback for datasets that predate `loan_default_events`.
4. **Mature no-default** (label=0): the observation horizon ends before the dataset cutoff and no default event was found.
5. **Censored** (no label): the horizon has not yet matured; the row is excluded from training.

The `label_event` column records which rule produced the label: `future_default`, `future_bankruptcy`, `historical_defaults`, or `no_default`.

## Feature sources

The pipeline reads every raw table that exists in the database and computes features as of each application:

| Feature group | Source tables |
|---|---|
| Company and people | `companies`, `users`, `founders`, `managers`, `consents` |
| Application | `applications`, `self_assessments`, `collateral_offers`, `application_events` |
| Registries and status | `egrul_records`, `sme_registry`, `fns_status`, `rosstat_indicators`, `sfr_reports` |
| Financials and accounting | `financial_statements`, `tax_reports`, `accounting_entries`, `management_reports`, `accounting_systems`, `warehouse_stock` |
| Banking | `bank_accounts`, `bank_transactions`, `currency_operations`, `bank_products`, `bank_internal_history` |
| Credit bureau | `credit_bureau_reports`, `credit_bureau_loans`, `credit_inquiries` |
| Legal and risk | `court_cases`, `enforcement_proceedings`, `bankruptcy_events`, `counterparty_checks`, `business_history`, `news_mentions`, `reputation` |
| Assets and operations | `real_estate`, `vehicles`, `licenses`, `tenders`, `insurance_policies`, `fuel_cards`, `telematics`, `iot_sensors`, `logistics`, `utilities`, `marketplace_sales`, `ofd_receipts`, `payment_services` |
| External signals | `domain_whois`, `geo_metrics`, `mobile_operator`, `social_media`, `website_metrics`, `hr_metrics`, `biometric_checks` |
| Public support and networks | `grants_subsidies`, `certifications`, `industry_memberships`, `trade_networks`, `franchise_contracts`, `intellectual_property`, `customs_declarations`, `gosuslugi_events`, `rating_agency_ratings` |
| Prior interactions | `scoring_results`, `policy_decisions`, `offers`, `loan_contracts`, `documents`, `audit_log`, `loan_default_events` |

Feature categories:

- **Raw numeric**: 201 features covering company profile, financials, banking, credit history, legal events, operations, digital activity, and prior interactions.
- **Model numeric**: derived ratios and logs plus the raw numeric set.
- **Categorical**: `product_type`, `purpose`, `company_segment`, `legal_form`, `tax_regime`, `client_rating`.
- **Risk scores**: `okved_risk`, `region_risk` (mapped from OKVED prefix and region name).

## Output schema

Columns:

- `application_id`, `company_id`, `submitted_at`, `feature_cutoff`, `label_horizon_end`, `label_event`, `label_event_at` — metadata
- 201 numeric features + 6 categorical features
- `default` — binary target

## Manifest

`training_table.manifest.json` contains:

- `pipeline_version` (currently `raw-as-of-v3`)
- `db_path`, `db_sha256`
- `total_applications`, `eligible_applications`, `censored_applications`
- `positive_labels`, `negative_labels`, `default_rate`
- `observation_horizon_days`, `dataset_cutoff`
- `label_event_counts`
- `table_counts`

## Limitations

The large synthetic database contains real post-application `loan_default_events`, so most labels are now `future_default`. The `historical_defaults` fallback remains only for older databases without that table. Remaining limitations:

- the synthetic feature-to-default relationship is intentionally simple and produces modest ROC-AUC;
- train/test splits are random and stratified rather than time-based;
- static registry tables in the synthetic generator are snapshots, so early applications see fewer of those features;
- production model serving still supplies only the legacy feature subset and must be extended before using the full model.

## Tests

```powershell
cd ml
python -m pytest tests\test_pipeline.py -q
```
