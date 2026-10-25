import asyncio

from schemas.applications import (
    SApplication,
    SCompany,
    SCreditHistory,
    SFinancials,
    SScoreApplicationRequest,
)
from schemas.mock import SBkiResponse, SEgrulResponse, SFnsResponse
from services.exceptions import EnrichmentError
from services.mock_data import generate_bki, generate_egrul, generate_fns


async def _call_egrul(inn: str) -> SEgrulResponse:
    """Асинхронно получает данные ЕГРЮЛ"""
    return generate_egrul(inn)


async def _call_fns(inn: str) -> SFnsResponse:
    """Асинхронно получает данные ФНС"""
    return generate_fns(inn)


async def _call_bki(inn: str) -> SBkiResponse:
    """Асинхронно получает данные БКИ"""
    return generate_bki(inn)


async def enrich(inn: str) -> dict:
    """
    Обогащает данные через три мок-источника параллельно.
    При падении источника его ключ = None, остальные сохраняются.
    """
    results = await asyncio.gather(
        _call_egrul(inn),
        _call_fns(inn),
        _call_bki(inn),
        return_exceptions=True,
    )

    keys = ("egrul", "fns", "bki")
    enriched: dict = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            enriched[key] = None
        else:
            enriched[key] = result.model_dump(mode="json")
    return enriched


def _company_from_egrul(enriched: dict) -> SCompany | None:
    """Собирает SCompany из egrul-ответа"""
    egrul = enriched.get("egrul")
    if not egrul:
        return None
    return SCompany(
        inn=egrul["inn"],
        ogrn=egrul["ogrn"],
        legal_name=egrul["legal_name"],
        legal_form=egrul["legal_form"],
        okved=egrul["okved"],
        region=egrul["region"],
        registration_date=egrul["registration_date"],
        employee_count=egrul["employee_count"],
    )


def _credit_history_from_bki(enriched: dict) -> SCreditHistory | None:
    """Собирает SCreditHistory из bki-ответа"""
    bki = enriched.get("bki")
    if not bki:
        return None
    return SCreditHistory(
        active_obligations_count=bki["active_obligations_count"],
        total_outstanding_rub=bki["total_outstanding_rub"],
        monthly_debt_payments_rub=bki["monthly_debt_payments_rub"],
        max_days_past_due_12m=bki["max_days_past_due_12m"],
        has_current_past_due=bki["has_current_past_due"],
        credit_utilization=bki["credit_utilization"],
        closed_obligations_count=bki["closed_obligations_count"],
        applications_last_6m=bki["applications_last_6m"],
    )


def merge_profile_with_enriched(
    application: SApplication,
    profile_company: SCompany | None,
    profile_financials: SFinancials | None,
    profile_credit_history: SCreditHistory | None,
    enriched: dict,
) -> SScoreApplicationRequest:
    """
    Собирает полный SScoreApplicationRequest, добивая пропуски профиля из enriched_data.
    Кидает EnrichmentError если обязательного блока нет ни в профиле, ни в обогащении.
    """
    company = profile_company or _company_from_egrul(enriched)
    if company is None:
        raise EnrichmentError("Не удалось получить данные компании из ЕГРЮЛ", source="egrul")

    if profile_financials is None:
        raise EnrichmentError(
            "Профиль финансов не заполнен, а моки госуслуг не возвращают финансовые показатели",
            source="financials",
        )

    credit_history = profile_credit_history or _credit_history_from_bki(enriched)
    if credit_history is None:
        raise EnrichmentError("Не удалось получить кредитную историю из БКИ", source="bki")

    return SScoreApplicationRequest(
        application=application,
        company=company,
        financials=profile_financials,
        credit_history=credit_history,
    )


# Словарь налоговых режимов: мок ФНС отдаёт кириллицу, а ML обучен на слагах
# из обучающей таблицы пайплайна (usn / osn / patent / eshn). Без приведения
# CatBoost увидел бы неизвестную категорию.
TAX_REGIME_TO_ML = {
    "УСН": "usn",
    "ОСН": "osn",
    "ПАТЕНТ": "patent",
    "ЕСХН": "eshn",
}


def extract_ml_extra_features(
    enriched: dict,
) -> tuple[dict[str, float], dict[str, str]]:
    """Собирает extra_*_features для ML из ответов мок-госуслуг.

    Отдаём только те признаки, которые действительно есть в обучающей таблице
    пайплайна и по которым источник даёт сопоставимые значения:

    - bki.credit_score -> bki_credit_score. Главный признак модели (49% важности);
      без него ML подставляет дефолт схемы и качество падает с AUC 0.76 до 0.55.
    - fns.tax_debt_rub -> tax_debt_rub.
    - fns.tax_regime -> tax_regime (со приведением словаря).

    Намеренно НЕ отдаём:
    - mass_address_flag / mass_manager_flag: в обучающей таблице они константны
      (всегда 0), поэтому признак не несёт информации, а значения из мока
      оказались бы вне распределения обучения;
    - disqualified_manager_flag: мок всегда возвращает False, то есть значение
      совпадает с дефолтом;
    - reputation_rating: в обучении это шкала 0-5, а fns.reliability_score —
      шкала 40-100; подмена исказила бы признак.
    """
    numeric: dict[str, float] = {}
    categorical: dict[str, str] = {}

    bki = enriched.get("bki")
    if bki:
        score = bki.get("credit_score")
        if score is not None:
            numeric["bki_credit_score"] = float(score)

    fns = enriched.get("fns")
    if fns:
        debt = fns.get("tax_debt_rub")
        if debt is not None:
            numeric["tax_debt_rub"] = float(debt)

        regime = fns.get("tax_regime")
        if regime:
            mapped = TAX_REGIME_TO_ML.get(str(regime).strip().upper())
            if mapped:
                categorical["tax_regime"] = mapped

    return numeric, categorical