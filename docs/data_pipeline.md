# Data Pipeline: raw SQLite to training table

## Overview

The pipeline converts the synthetic raw data database (`data/raw/simplecredits_raw.db`) into a supervised learning table for credit default prediction.

Key design decisions:

- **As-of slicing.** For every application, all features are computed from data available strictly before `submitted_at`. This prevents label and information leakage.
- **Financial statement availability.** `financial_statements` has no publication timestamp, so a conservative lag is applied: a statement becomes available 90 days after the end of its reporting period (`H1` or `FY`). This prevents using half-year reports before they could be published.
- **Observation horizon.** The label is 1 if a default event occurs within `horizon_days` after submission, 0 if the horizon matures without default, and `censored` otherwise.
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

## Label logic

The label is derived from multiple sources, in priority order:

1. **Future bankruptcy** (label=1): a bankruptcy event occurs after `submitted_at` and within the observation horizon.
2. **Historical defaults** (label=1): the company has `defaults_count > 0` in `bank_internal_history` and `last_activity_at` falls after `submitted_at` and within the observation horizon. This is a prototype-level fallback while the synthetic data does not contain enough future default events; it is not a true prospective default label.
3. **Mature no-default** (label=0): the observation horizon ends before the dataset cutoff and no default event was found.
4. **Censored** (no label): the horizon has not yet matured; the row is excluded from training.

The `label_event` column records which rule produced the label: `future_bankruptcy`, `historical_defaults`, `no_default`, or `censored`.

## Feature sources

| Feature group | Source tables |
|---|---|
| Company profile | `companies` |
| Application | `applications` |
| Self-declared financials | `self_assessments` |
| Financial statements | `financial_statements` |
| Bank products and obligations | `bank_products` |
| Bank transactions | `bank_transactions` |
| Credit bureau data | `credit_bureau_reports`, `credit_inquiries` |
| Tax status | `fns_status` |
| Legal events | `court_cases`, `enforcement_proceedings`, `bankruptcy_events` |
| Internal history | `bank_internal_history` |

Feature categories:

- **Raw numeric**: company age, revenue, debt, payment burden, utilization, days past due.
- **Derived numeric**: transaction inflow/outflow over 90 and 180 days, tax debt, enforcement counts, court claims, BKI score, fraud flag.
- **Categorical**: `product_type`, `purpose`.
- **Risk scores**: `okved_risk`, `region_risk` (mapped from OKVED prefix and region name).

## Output schema

Columns:

- `application_id`, `company_id`, `submitted_at`, `feature_cutoff`, `label_horizon_end`, `label_event`, `label_event_at` — metadata
- 22 raw numeric features + 18 extended numeric features + 2 categorical features
- `default` — binary target

## Manifest

`training_table.manifest.json` contains:

- `pipeline_version` (currently `raw-as-of-v2`)
- `db_path`, `db_sha256`
- `total_applications`, `eligible_applications`, `censored_applications`
- `positive_labels`, `negative_labels`, `default_rate`
- `observation_horizon_days`, `dataset_cutoff`
- `label_event_counts`
- `table_counts`

## Limitations

The current synthetic data has very few future default events. The `historical_defaults` fallback is used to keep the target non-degenerate, but it is not a true prospective label: `defaults_count` is a current snapshot and `last_activity_at` is not a default date. The manifest exposes `label_event_counts` so the share of fallback labels is visible. For production:

- generate future default events after application dates,
- use a longer observation window and a time-based train/test split,
- replace the fallback with actual post-application defaults from `loan_contracts` or collections data.

## Tests

```powershell
cd ml
python -m pytest tests\test_pipeline.py -q
```
