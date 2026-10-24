from datetime import datetime, timezone

import pytest

from schemas.applications import SApplication, SCompany, SCreditHistory, SFinancials
from services.enrichment import merge_profile_with_enriched
from services.exceptions import EnrichmentError


def make_application():
    """Возвращает валидную SApplication"""
    return SApplication(
        product_type="term_loan",
        requested_amount_rub=1_500_000,
        term_months=24,
        purpose="equipment",
        segment="small",
        submitted_at=datetime.now(timezone.utc),
    )


def make_company():
    """Возвращает валидную SCompany"""
    return SCompany(
        inn="7701234567",
        ogrn="1027700132195",
        legal_name="ООО Ромашка",
        legal_form="llc",
        okved="62.01",
        region="Москва",
        registration_date=datetime.now(timezone.utc),
        employee_count=25,
    )


def make_financials():
    """Возвращает валидную SFinancials"""
    return SFinancials(
        annual_revenue_rub=42_000_000,
        annual_net_profit_rub=6_500_000,
        ebitda_rub=8_200_000,
        total_debt_rub=3_000_000,
        monthly_revenue_rub=3_500_000,
        monthly_expenses_rub=2_800_000,
        accounts_receivable_rub=1_200_000,
        cash_balance_rub=900_000,
        period_end=datetime.now(timezone.utc),
    )


def make_credit_history():
    """Возвращает валидную SCreditHistory"""
    return SCreditHistory(
        active_obligations_count=2,
        total_outstanding_rub=3_000_000,
        monthly_debt_payments_rub=120_000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
    )


def make_enriched_egrul():
    """Возвращает enriched с заполненным egrul"""
    return {
        "egrul": {
            "inn": "7701234567",
            "ogrn": "1027700132195",
            "legal_name": "ООО Из-ЕГРЮЛ",
            "legal_form": "llc",
            "status": "active",
            "okved": "62.01",
            "okved_description": "Разработка ПО",
            "region": "Москва",
            "registration_date": datetime.now(timezone.utc).isoformat(),
            "employee_count": 30,
            "director": "Иванов И.И.",
            "address": "Москва",
        },
        "fns": None,
        "bki": None,
    }


def make_enriched_bki():
    """Возвращает enriched с заполненным bki"""
    return {
        "egrul": None,
        "fns": None,
        "bki": {
            "inn": "7701234567",
            "credit_score": 700,
            "active_obligations_count": 1,
            "total_outstanding_rub": 1_000_000,
            "monthly_debt_payments_rub": 50_000,
            "max_days_past_due_12m": 0,
            "has_current_past_due": False,
            "credit_utilization": 0.3,
            "closed_obligations_count": 2,
            "applications_last_6m": 1,
            "last_update": datetime.now(timezone.utc).isoformat(),
        },
    }


def test_merge_full_profile():
    """Полный профиль → берём из профиля"""
    result = merge_profile_with_enriched(
        make_application(),
        make_company(),
        make_financials(),
        make_credit_history(),
        enriched={},
    )
    assert result.company.legal_name == "ООО Ромашка"
    assert result.credit_history.credit_utilization == pytest.approx(0.35)


def test_merge_company_from_egrul():
    """company=None + enriched.egrul → компания из ЕГРЮЛ"""
    result = merge_profile_with_enriched(
        make_application(),
        profile_company=None,
        profile_financials=make_financials(),
        profile_credit_history=make_credit_history(),
        enriched=make_enriched_egrul(),
    )
    assert result.company.legal_name == "ООО Из-ЕГРЮЛ"
    assert result.company.employee_count == 30


def test_merge_credit_history_from_bki():
    """КИ=None + enriched.bki → из БКИ"""
    result = merge_profile_with_enriched(
        make_application(),
        profile_company=make_company(),
        profile_financials=make_financials(),
        profile_credit_history=None,
        enriched=make_enriched_bki(),
    )
    assert result.credit_history.active_obligations_count == 1


def test_merge_financials_none_raises():
    """financials=None → EnrichmentError"""
    with pytest.raises(EnrichmentError, match="финанс"):
        merge_profile_with_enriched(
            make_application(),
            profile_company=make_company(),
            profile_financials=None,
            profile_credit_history=make_credit_history(),
            enriched={},
        )


def test_merge_company_none_and_egrul_none_raises():
    """company=None и enriched.egrul=None → EnrichmentError"""
    with pytest.raises(EnrichmentError, match="ЕГРЮЛ"):
        merge_profile_with_enriched(
            make_application(),
            profile_company=None,
            profile_financials=make_financials(),
            profile_credit_history=make_credit_history(),
            enriched={"egrul": None, "fns": None, "bki": None},
        )


def test_merge_credit_history_none_and_bki_none_raises():
    """КИ=None и enriched.bki=None → EnrichmentError"""
    with pytest.raises(EnrichmentError, match="БКИ"):
        merge_profile_with_enriched(
            make_application(),
            profile_company=make_company(),
            profile_financials=make_financials(),
            profile_credit_history=None,
            enriched={"egrul": None, "fns": None, "bki": None},
        )


def test_merge_empty_enriched_uses_profile():
    """Пустой enriched — все данные из профиля"""
    result = merge_profile_with_enriched(
        make_application(),
        make_company(),
        make_financials(),
        make_credit_history(),
        enriched={},
    )
    assert result.application.requested_amount_rub == 1_500_000