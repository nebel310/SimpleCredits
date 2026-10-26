"""Признаки, доступные в проде.

Модель обучается на таблице пайплайна, где заполнены все признаки. В проде же
gRPC-сервер получает только то, что backend кладёт в ScoreApplicationRequest:
26 полей из proto и 3 признака из обогащения мок-госуслугами. Всё остальное
подставляется из дефолтов схемы.

Если обучать модель на признаках, которых в проде нет, она подбирает веса под
значения, которые никогда не придут. На catboost-v3 это дало коллапс: 29 из 30
отобранных признаков backend не отдаёт, PD схлопнулся в диапазон 0.23-0.32,
все заявки получили грейд E и manual_review (прод-симуляция: AUC 0.7519 против
0.7625 у модели на доступных признаках).

Доступность выводится эмпирически, а не хранится списком: признак считается
доступным, если он меняется при изменении доступных сырых колонок. Это защищает
от расхождения при правках build_features или схемы.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    CATEGORICAL_VOCABULARIES,
    DEFAULT_RAW_ROW,
)
from simplecredits.ml.features.features import FEATURE_COLUMNS, build_features

# Колонки, которые request_to_raw_row() заполняет из полей proto.
SERVING_PROTO_COLUMNS: frozenset[str] = frozenset(
    {
        "accounts_receivable_rub",
        "active_obligations_count",
        "annual_net_profit_rub",
        "annual_revenue_rub",
        "applications_last_6m",
        "cash_balance_rub",
        "closed_obligations_count",
        "company_age_months",
        "company_segment",
        "credit_utilization",
        "ebitda_rub",
        "employee_count",
        "has_current_past_due",
        "legal_form",
        "max_days_past_due_12m",
        "monthly_debt_payments_rub",
        "monthly_expenses_rub",
        "monthly_revenue_rub",
        "okved_risk",
        "product_type",
        "purpose",
        "region_risk",
        "requested_amount_rub",
        "term_months",
        "total_debt_rub",
        "total_outstanding_rub",
    }
)

# Колонки, которые backend кладёт в extra_*_features из ответов мок-госуслуг
# (services/enrichment.py: extract_ml_extra_features).
SERVING_ENRICHED_COLUMNS: frozenset[str] = frozenset(
    {
        "bki_credit_score",  # bki.credit_score
        "tax_debt_rub",  # fns.tax_debt_rub
        "tax_regime",  # fns.tax_regime, с приведением словаря
    }
)

SERVING_AVAILABLE_COLUMNS: frozenset[str] = (
    SERVING_PROTO_COLUMNS | SERVING_ENRICHED_COLUMNS
)

# Число проб, на которых проверяется чувствительность признаков.
_PROBE_ROWS = 24


def _probe_frame(seed: int = 1234) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Два набора строк: с дефолтами и с возмущёнными доступными колонками.

    Возмущаются только колонки из SERVING_AVAILABLE_COLUMNS — ровно те, что
    могут прийти в проде. Признак, который на возмущение не отреагировал,
    прод-запросом изменён быть не может.
    """
    rng = np.random.default_rng(seed)
    baseline = pd.DataFrame([dict(DEFAULT_RAW_ROW) for _ in range(_PROBE_ROWS)])
    perturbed = baseline.copy()

    for column in sorted(SERVING_AVAILABLE_COLUMNS & set(perturbed.columns)):
        if column in CATEGORICAL_FEATURES:
            perturbed[column] = [
                value for value in _cycle_categorical(column, _PROBE_ROWS)
            ]
            continue
        default = float(DEFAULT_RAW_ROW.get(column, 0.0) or 0.0)
        spread = max(abs(default), 1.0)
        perturbed[column] = default + rng.uniform(-spread, spread, size=_PROBE_ROWS)

    return baseline, perturbed


def _cycle_categorical(column: str, count: int) -> list[str]:
    """Перебирает возможные значения категориального признака."""
    values = list(CATEGORICAL_VOCABULARIES.get(column, ["other"]))
    return [values[index % len(values)] for index in range(count)]


def serving_available_features() -> list[str]:
    """Признаки модели, которые в проде действительно зависят от входных данных.

    Порядок совпадает с FEATURE_COLUMNS. Результат детерминирован: возмущения
    строятся на фиксированном сиде.
    """
    baseline, perturbed = _probe_frame()
    base_features = build_features(baseline)
    pert_features = build_features(perturbed)

    available: list[str] = []
    for column in FEATURE_COLUMNS:
        left = base_features[column].to_numpy(dtype=object)
        right = pert_features[column].to_numpy(dtype=object)
        if np.issubdtype(np.asarray(right).dtype, np.number):
            differs = bool(
                np.any(~np.isclose(left.astype(float), right.astype(float), equal_nan=True))
            )
        else:
            differs = bool(np.any(left != right))
        if differs:
            available.append(column)
    return available


def unavailable_features() -> list[str]:
    """Признаки модели, недоступные в проде (всегда принимают дефолт схемы)."""
    available = set(serving_available_features())
    return [column for column in FEATURE_COLUMNS if column not in available]
