from __future__ import annotations

from collections import defaultdict

import pandas as pd

from simplecredits.ml.data.schema import CATEGORICAL_FEATURES

FEATURE_META: dict[str, tuple[str, str, str]] = {
    "company_age_months": (
        "BUSINESS_AGE",
        "Молодой бизнес без длительной истории",
        "Зрелый бизнес с устойчивой историей",
    ),
    "employee_count": (
        "BUSINESS_SCALE",
        "Небольшой масштаб бизнеса",
        "Достаточный масштаб бизнеса",
    ),
    "okved_risk": (
        "INDUSTRY_RISK",
        "Повышенный риск отрасли",
        "Отрасль с умеренным риском",
    ),
    "region_risk": (
        "REGION_RISK",
        "Повышенный региональный риск",
        "Умеренный региональный риск",
    ),
    "log_annual_revenue": (
        "REVENUE_SCALE",
        "Небольшая выручка",
        "Значительная выручка",
    ),
    "log_requested_amount": (
        "REQUESTED_AMOUNT",
        "Высокая запрашиваемая сумма",
        "Умеренная запрашиваемая сумма",
    ),
    "term_months": (
        "LOAN_TERM",
        "Длительный срок кредита",
        "Умеренный срок кредита",
    ),
    "debt_to_revenue": (
        "DEBT_BURDEN",
        "Высокая долговая нагрузка",
        "Низкая долговая нагрузка",
    ),
    "debt_service_ratio": (
        "DEBT_SERVICE",
        "Высокая нагрузка на обслуживание долга",
        "Умеренная нагрузка на обслуживание долга",
    ),
    "requested_to_annual_revenue": (
        "LOAN_TO_REVENUE",
        "Запрос велик относительно выручки",
        "Запрос соразмерен выручке",
    ),
    "profitability": (
        "PROFITABILITY",
        "Низкая рентабельность",
        "Хорошая рентабельность",
    ),
    "ebitda_margin": (
        "EBITDA_MARGIN",
        "Низкая маржинальность",
        "Здоровая маржинальность",
    ),
    "cash_coverage": (
        "LIQUIDITY",
        "Недостаток ликвидности",
        "Достаточная ликвидность",
    ),
    "expense_ratio": (
        "EXPENSE_RATIO",
        "Высокая доля расходов",
        "Умеренная доля расходов",
    ),
    "log_revenue_per_employee": (
        "LABOR_PRODUCTIVITY",
        "Низкая выручка на сотрудника",
        "Высокая выручка на сотрудника",
    ),
    "max_days_past_due_12m": (
        "PAST_DUE_HISTORY",
        "Просрочки за последний год",
        "Хорошая платёжная дисциплина",
    ),
    "has_current_past_due": (
        "CURRENT_PAST_DUE",
        "Есть текущая просрочка",
        "Нет текущих просрочек",
    ),
    "credit_utilization": (
        "CREDIT_UTILIZATION",
        "Высокая загрузка лимитов",
        "Умеренная загрузка лимитов",
    ),
    "active_obligations_count": (
        "ACTIVE_OBLIGATIONS",
        "Много действующих обязательств",
        "Умеренное число обязательств",
    ),
    "applications_last_6m": (
        "APPLICATION_INTENSITY",
        "Частые обращения за кредитом",
        "Умеренная кредитная активность",
    ),
    "closed_obligations_ratio": (
        "CREDIT_HISTORY_DEPTH",
        "Ограниченная кредитная история",
        "Положительная кредитная история",
    ),
    "product_type": (
        "PRODUCT_RISK",
        "Повышенный риск продукта",
        "Продукт с умеренным риском",
    ),
    "purpose": (
        "PURPOSE_RISK",
        "Повышенный риск цели финансирования",
        "Цель с умеренным риском",
    ),
}


def _base_feature(encoded_name: str) -> str:
    name = encoded_name.split("__", 1)[-1]
    for category in CATEGORICAL_FEATURES:
        if name == category or name.startswith(f"{category}_"):
            return category
    return name


def compute_reasons(
    preprocessor,
    estimator,
    features_row: pd.DataFrame,
    top_k: int = 5,
) -> list[dict]:
    transformed = preprocessor.transform(features_row)
    if hasattr(transformed, "toarray"):
        transformed = transformed.toarray()
    values = transformed[0]
    names = preprocessor.get_feature_names_out()
    coefficients = estimator.coef_[0]

    aggregated: dict[str, float] = defaultdict(float)
    for name, value, coefficient in zip(names, values, coefficients, strict=True):
        aggregated[_base_feature(str(name))] += float(value) * float(coefficient)

    ranked = sorted(aggregated.items(), key=lambda item: abs(item[1]), reverse=True)
    reasons: list[dict] = []
    for feature, contribution in ranked:
        if abs(contribution) < 1e-9:
            continue
        code, risky_text, safe_text = FEATURE_META.get(
            feature, (feature.upper(), "Фактор повышает риск", "Фактор снижает риск")
        )
        if contribution > 0:
            description, impact = risky_text, "negative"
        else:
            description, impact = safe_text, "positive"
        reasons.append(
            {
                "code": code,
                "description": description,
                "feature": feature,
                "impact": impact,
                "contribution": round(contribution, 6),
            }
        )
        if len(reasons) >= top_k:
            break
    return reasons


def compute_catboost_reasons(
    model,
    features_row: pd.DataFrame,
    top_k: int = 5,
) -> list[dict]:
    from catboost import Pool

    pool = Pool(features_row, cat_features=CATEGORICAL_FEATURES)
    shap_values = model.get_feature_importance(data=pool, type="ShapValues")
    contributions = shap_values[0][:-1]
    ranked = sorted(
        zip(features_row.columns, contributions, strict=True),
        key=lambda item: abs(float(item[1])),
        reverse=True,
    )

    reasons: list[dict] = []
    for feature, contribution in ranked:
        value = float(contribution)
        if abs(value) < 1e-9:
            continue
        code, risky_text, safe_text = FEATURE_META.get(
            feature, (feature.upper(), "Фактор повышенного риска", "Фактор снижения риска")
        )
        if value > 0:
            description, impact = risky_text, "negative"
        else:
            description, impact = safe_text, "positive"
        reasons.append(
            {
                "code": code,
                "description": description,
                "feature": feature,
                "impact": impact,
                "contribution": round(value, 6),
            }
        )
        if len(reasons) >= top_k:
            break
    return reasons
