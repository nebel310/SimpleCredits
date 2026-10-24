from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.applications import (
    DEFAULT_PRODUCT_TYPE,
    SApplication,
    SApplicationCreateRequest,
    SApplicationDetail,
    SApplicationEventResponse,
    SCompany,
    SCreditHistory,
    SDecisionCondition,
    SDecisionResult,
    SFinancials,
    SReasonCode,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
    application_orm_to_schema,
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


def make_application_orm():
    """Возвращает ORM-подобный объект заявки"""
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        application_id="abc123",
        status="scored",
        created_at=now,
        updated_at=now,
        product_type="term_loan",
        requested_amount_rub=1500000,
        term_months=24,
        purpose="equipment",
        segment="small",
        submitted_at=now,
        inn="7701234567",
        ogrn="1027700132195",
        legal_name="ООО Ромашка",
        legal_form="llc",
        okved="62.01",
        region="Москва",
        registration_date=now,
        employee_count=25,
        annual_revenue_rub=42000000,
        annual_net_profit_rub=6500000,
        ebitda_rub=8200000,
        total_debt_rub=3000000,
        monthly_revenue_rub=3500000,
        monthly_expenses_rub=2800000,
        accounts_receivable_rub=1200000,
        cash_balance_rub=900000,
        period_end=now,
        active_obligations_count=2,
        total_outstanding_rub=3000000,
        monthly_debt_payments_rub=120000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
        scoring_result=None,
        enriched_data=None,
        explanation=None,
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


def test_full_request_valid():
    """Собирает полный валидный SScoreApplicationRequest"""
    request = SScoreApplicationRequest(
        application=make_valid_application(),
        company=make_valid_company(),
        financials=make_valid_financials(),
        credit_history=make_valid_credit_history(),
    )
    assert request.company.inn == "7701234567"


def test_create_request_without_profile():
    """SApplicationCreateRequest допускает отсутствие профиля"""
    r = SApplicationCreateRequest(
        requested_amount_rub=100000,
        term_months=12,
        purpose="other",
        segment="micro",
    )
    assert r.company is None
    assert r.product_type is None


def test_create_request_with_profile():
    """SApplicationCreateRequest принимает профиль"""
    r = SApplicationCreateRequest(
        product_type="term_loan",
        requested_amount_rub=100000,
        term_months=12,
        purpose="other",
        segment="micro",
        company=make_valid_company(),
        financials=make_valid_financials(),
        credit_history=make_valid_credit_history(),
    )
    assert r.company.inn == "7701234567"


def test_create_request_requires_purpose_and_segment():
    """Пропуск purpose/segment → ошибка"""
    with pytest.raises(ValidationError):
        SApplicationCreateRequest(
            requested_amount_rub=100000,
            term_months=12,
        )


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


def test_event_response_from_attributes():
    """Собирает SApplicationEventResponse из ORM-подобного объекта"""
    ns = SimpleNamespace(
        id=1,
        event_type="created",
        payload={"user_id": 1},
        created_at=datetime.now(timezone.utc),
    )
    r = SApplicationEventResponse.model_validate(ns)
    assert r.event_type == "created"


def test_orm_to_schema_without_result():
    """Собирает заявку без результата скоринга"""
    detail = application_orm_to_schema(make_application_orm())
    assert detail.application_id == "abc123"
    assert detail.status == "scored"
    assert detail.scoring_result is None
    assert detail.enriched_data is None
    assert detail.explanation is None


def test_orm_to_schema_with_result():
    """Собирает заявку с результатом из JSONB"""
    ns = make_application_orm()
    ns.scoring_result = SScoreApplicationResponse(
        application_id="abc123",
        score=712,
        pd=0.0421,
        risk_grade="B",
        reason_codes=[],
        model_version="v1.0.0",
        scored_at=datetime.now(timezone.utc),
        decision=SDecisionResult(decision="approve"),
    ).model_dump(mode="json")

    detail = application_orm_to_schema(ns)
    assert detail.scoring_result is not None
    assert detail.scoring_result.score == 712
    assert detail.scoring_result.risk_grade == "B"


def test_orm_to_schema_null_product_type_uses_default():
    """При null product_type подставляет значение по умолчанию"""
    ns = make_application_orm()
    ns.product_type = None
    detail = application_orm_to_schema(ns)
    assert detail.application.product_type == DEFAULT_PRODUCT_TYPE


def test_orm_to_schema_passes_enriched_data():
    """Пробрасывает enriched_data и explanation"""
    ns = make_application_orm()
    ns.enriched_data = {"egrul": {"okved": "62.01"}}
    ns.explanation = "Заявка одобрена"
    detail = application_orm_to_schema(ns)
    assert detail.enriched_data == {"egrul": {"okved": "62.01"}}
    assert detail.explanation == "Заявка одобрена"