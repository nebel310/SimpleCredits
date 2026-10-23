from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.scoring import (
    SApplication,
    SCompany,
    SCreditHistory,
    SDecisionCondition,
    SDecisionResult,
    SFinancials,
    SReasonCode,
    SScoreApplicationRequest,
)


def make_valid_application():
    """Возвращает валидную SApplication"""
    return SApplication(
        product_type="term_loan",
        requested_amount_rub=1500000,
        term_months=24,
        purpose="equipment",
        segment="small",
        submitted_at=datetime.now(timezone.utc),
    )


def make_valid_company():
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


def make_valid_financials():
    """Возвращает валидную SFinancials"""
    return SFinancials(
        annual_revenue_rub=42000000,
        annual_net_profit_rub=6500000,
        ebitda_rub=8200000,
        total_debt_rub=3000000,
        monthly_revenue_rub=3500000,
        monthly_expenses_rub=2800000,
        accounts_receivable_rub=1200000,
        cash_balance_rub=900000,
        period_end=datetime.now(timezone.utc),
    )


def make_valid_credit_history():
    """Возвращает валидную SCreditHistory"""
    return SCreditHistory(
        active_obligations_count=2,
        total_outstanding_rub=3000000,
        monthly_debt_payments_rub=120000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
    )


def test_application_all_product_types():
    """Пропускает все допустимые product_type"""
    for value in ("microloan", "term_loan", "overdraft", "credit_line", "leasing"):
        data = make_valid_application().model_copy(update={"product_type": value})
        assert data.product_type == value


def test_application_invalid_product_type():
    """Отклоняет неизвестный product_type"""
    with pytest.raises(ValidationError):
        SApplication(
            product_type="unknown",
            requested_amount_rub=100,
            term_months=12,
            purpose="other",
            segment="micro",
            submitted_at=datetime.now(timezone.utc),
        )


def test_application_negative_amount():
    """Отклоняет отрицательную сумму"""
    with pytest.raises(ValidationError):
        SApplication(
            product_type="term_loan",
            requested_amount_rub=-1,
            term_months=12,
            purpose="other",
            segment="micro",
            submitted_at=datetime.now(timezone.utc),
        )


def test_application_zero_term():
    """Отклоняет term_months=0"""
    with pytest.raises(ValidationError):
        SApplication(
            product_type="term_loan",
            requested_amount_rub=100,
            term_months=0,
            purpose="other",
            segment="micro",
            submitted_at=datetime.now(timezone.utc),
        )


def test_company_short_inn():
    """Отклоняет ИНН короче 10 символов"""
    with pytest.raises(ValidationError):
        SCompany(
            inn="123",
            ogrn="1027700132195",
            legal_name="X",
            legal_form="llc",
            okved="62",
            region="М",
            registration_date=datetime.now(timezone.utc),
            employee_count=1,
        )


def test_company_long_ogrn():
    """Отклоняет ОГРН длиннее 15 символов"""
    with pytest.raises(ValidationError):
        SCompany(
            inn="7701234567",
            ogrn="1" * 16,
            legal_name="X",
            legal_form="llc",
            okved="62",
            region="М",
            registration_date=datetime.now(timezone.utc),
            employee_count=1,
        )


def test_company_invalid_legal_form():
    """Отклоняет неизвестный legal_form"""
    with pytest.raises(ValidationError):
        SCompany(
            inn="7701234567",
            ogrn="1027700132195",
            legal_name="X",
            legal_form="unknown",
            okved="62",
            region="М",
            registration_date=datetime.now(timezone.utc),
            employee_count=1,
        )


def test_financials_negative_revenue():
    """Отклоняет отрицательную выручку"""
    with pytest.raises(ValidationError):
        SFinancials(
            annual_revenue_rub=-1,
            annual_net_profit_rub=0,
            ebitda_rub=0,
            total_debt_rub=0,
            monthly_revenue_rub=0,
            monthly_expenses_rub=0,
            accounts_receivable_rub=0,
            cash_balance_rub=0,
            period_end=datetime.now(timezone.utc),
        )


def test_financials_negative_profit_allowed():
    """Пропускает отрицательный annual_net_profit_rub"""
    data = make_valid_financials().model_copy(update={"annual_net_profit_rub": -100})
    assert data.annual_net_profit_rub == -100


def test_credit_history_utilization_above_one():
    """Отклоняет credit_utilization > 1"""
    with pytest.raises(ValidationError):
        SCreditHistory(
            active_obligations_count=0,
            total_outstanding_rub=0,
            monthly_debt_payments_rub=0,
            max_days_past_due_12m=0,
            has_current_past_due=False,
            credit_utilization=1.5,
            closed_obligations_count=0,
            applications_last_6m=0,
        )


def test_credit_history_utilization_negative():
    """Отклоняет отрицательный credit_utilization"""
    with pytest.raises(ValidationError):
        SCreditHistory(
            active_obligations_count=0,
            total_outstanding_rub=0,
            monthly_debt_payments_rub=0,
            max_days_past_due_12m=0,
            has_current_past_due=False,
            credit_utilization=-0.1,
            closed_obligations_count=0,
            applications_last_6m=0,
        )


def test_full_request_valid():
    """Собирает полный валидный SScoreApplicationRequest"""
    request = SScoreApplicationRequest(
        application=make_valid_application(),
        company=make_valid_company(),
        financials=make_valid_financials(),
        credit_history=make_valid_credit_history(),
    )
    assert request.company.inn == "7701234567"


def test_reason_code_valid():
    """Создаёт валидный SReasonCode"""
    rc = SReasonCode(
        code="RC001",
        description="Стабильная история",
        feature="max_days_past_due_12m",
        impact="positive",
        contribution=-0.12,
    )
    assert rc.impact == "positive"


def test_reason_code_invalid_impact():
    """Отклоняет неизвестный impact"""
    with pytest.raises(ValidationError):
        SReasonCode(
            code="RC001",
            description="X",
            feature="y",
            impact="unknown",
            contribution=0.0,
        )


def test_decision_condition_valid():
    """Создаёт валидный SDecisionCondition"""
    c = SDecisionCondition(code="C1", description="X", recommended_amount_rub=100)
    assert c.recommended_amount_rub == 100


def test_decision_result_defaults():
    """Пустые списки по умолчанию"""
    d = SDecisionResult(decision="approve")
    assert d.reason_codes == []
    assert d.conditions == []


def test_decision_result_invalid_decision():
    """Отклоняет неизвестный decision"""
    with pytest.raises(ValidationError):
        SDecisionResult(decision="unknown")