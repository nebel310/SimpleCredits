from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.applications import SCompany, SCreditHistory, SFinancials
from schemas.auth import (
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    RegisterResponse,
    SUser,
    SUserLogin,
    SUserRegister,
    SUserUpdate,
    user_orm_to_schema,
)


def make_company_dict():
    """Возвращает валидный словарь компании"""
    return dict(
        inn="7701234567",
        ogrn="1027700132195",
        legal_name="ООО Ромашка",
        legal_form="llc",
        okved="62.01",
        region="Москва",
        registration_date=datetime.now(timezone.utc),
        employee_count=25,
    )


def make_financials_dict():
    """Возвращает валидный словарь финансов"""
    return dict(
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


def make_credit_history_dict():
    """Возвращает валидный словарь КИ"""
    return dict(
        active_obligations_count=2,
        total_outstanding_rub=3000000,
        monthly_debt_payments_rub=120000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
    )


def make_user_orm(**overrides):
    """Возвращает ORM-подобный объект пользователя"""
    base = dict(
        id=1,
        username="john",
        email="john@example.com",
        role="user",
        avatar_id=None,
        bio=None,
        birth_date=None,
        gender=None,
        created_at=datetime.now(timezone.utc),
        inn=None,
        ogrn=None,
        legal_name=None,
        legal_form=None,
        okved=None,
        region=None,
        registration_date=None,
        employee_count=None,
        annual_revenue_rub=None,
        annual_net_profit_rub=None,
        ebitda_rub=None,
        total_debt_rub=None,
        monthly_revenue_rub=None,
        monthly_expenses_rub=None,
        accounts_receivable_rub=None,
        cash_balance_rub=None,
        period_end=None,
        active_obligations_count=None,
        total_outstanding_rub=None,
        monthly_debt_payments_rub=None,
        max_days_past_due_12m=None,
        has_current_past_due=None,
        credit_utilization=None,
        closed_obligations_count=None,
        applications_last_6m=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_s_user_register_valid():
    """Создаёт валидную схему регистрации"""
    data = SUserRegister(
        username="john",
        email="john@example.com",
        password="secret123",
        password_confirm="secret123",
    )
    assert data.email == "john@example.com"


def test_s_user_register_invalid_email():
    """Отклоняет некорректный email"""
    with pytest.raises(ValidationError):
        SUserRegister(
            username="john",
            email="not-an-email",
            password="x",
            password_confirm="x",
        )


def test_s_user_login_valid():
    """Создаёт валидную схему входа"""
    data = SUserLogin(email="john@example.com", password="secret123")
    assert data.email == "john@example.com"


def test_s_user_update_all_none_raises():
    """Запрещает пустой апдейт"""
    with pytest.raises(ValidationError, match="Не передано ни одного поля"):
        SUserUpdate()


def test_s_user_update_one_field_passes():
    """Пропускает апдейт с одним полем"""
    assert SUserUpdate(bio="new bio").bio == "new bio"


def test_s_user_update_with_company():
    """SUserUpdate принимает блок company"""
    u = SUserUpdate(company=SCompany(**make_company_dict()))
    assert u.company.inn == "7701234567"


def test_s_user_update_with_financials():
    """SUserUpdate принимает блок financials"""
    u = SUserUpdate(financials=SFinancials(**make_financials_dict()))
    assert u.financials.annual_revenue_rub == 42000000


def test_s_user_update_with_credit_history():
    """SUserUpdate принимает блок credit_history"""
    u = SUserUpdate(credit_history=SCreditHistory(**make_credit_history_dict()))
    assert u.credit_history.credit_utilization == 0.35


def test_s_user_update_invalid_gender():
    """Отклоняет невалидный gender"""
    with pytest.raises(ValidationError):
        SUserUpdate(gender="other")


def test_s_user_update_bio_too_long():
    """Отклоняет bio длиннее 500 символов"""
    with pytest.raises(ValidationError):
        SUserUpdate(bio="x" * 501)


def test_user_orm_to_schema_empty_profile():
    """Профиль не заполнен → все блоки None"""
    u = user_orm_to_schema(make_user_orm())
    assert u.company is None
    assert u.financials is None
    assert u.credit_history is None


def test_user_orm_to_schema_full_profile():
    """Все блоки собраны если поля заполнены"""
    ns = make_user_orm(
        **make_company_dict(),
        **make_financials_dict(),
        **make_credit_history_dict(),
    )
    u = user_orm_to_schema(ns)
    assert u.company is not None
    assert u.financials is not None
    assert u.credit_history is not None


def test_user_orm_to_schema_partial_company():
    """Частично заполненная компания → company=None"""
    ns = make_user_orm(inn="7701234567")
    u = user_orm_to_schema(ns)
    assert u.company is None


def test_user_orm_to_schema_partial_financials():
    """Частично заполненные финансы → financials=None"""
    ns = make_user_orm(annual_revenue_rub=100)
    u = user_orm_to_schema(ns)
    assert u.financials is None


def test_user_orm_to_schema_partial_credit_history():
    """Частично заполненная КИ → credit_history=None"""
    ns = make_user_orm(active_obligations_count=2)
    u = user_orm_to_schema(ns)
    assert u.credit_history is None


def test_user_orm_to_schema_false_is_not_none():
    """has_current_past_due=False считается заполненным"""
    ns = make_user_orm(
        **make_company_dict(),
        **make_financials_dict(),
        **make_credit_history_dict(),
    )
    ns.has_current_past_due = False
    u = user_orm_to_schema(ns)
    assert u.credit_history is not None
    assert u.credit_history.has_current_past_due is False


def test_register_response_fields():
    """Проверяет поля RegisterResponse"""
    assert RegisterResponse(success=True, user_id=1, message="ok").success is True


def test_login_response_fields():
    """Проверяет поля LoginResponse"""
    r = LoginResponse(
        success=True,
        message="ok",
        access_token="a",
        refresh_token="r",
        token_type="bearer",
    )
    assert r.token_type == "bearer"


def test_refresh_response_fields():
    """Проверяет поля RefreshResponse"""
    assert RefreshResponse(access_token="a", token_type="bearer").access_token == "a"


def test_logout_response_fields():
    """Проверяет поля LogoutResponse"""
    assert LogoutResponse(success=True).success is True