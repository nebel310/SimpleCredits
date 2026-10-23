from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.auth import (
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    RegisterResponse,
    SUser,
    SUserLogin,
    SUserRegister,
    SUserUpdate,
)


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
            password="secret123",
            password_confirm="secret123",
        )


def test_s_user_login_valid():
    """Создаёт валидную схему входа"""
    data = SUserLogin(email="john@example.com", password="secret123")
    assert data.email == "john@example.com"


def test_s_user_login_invalid_email():
    """Отклоняет некорректный email при входе"""
    with pytest.raises(ValidationError):
        SUserLogin(email="bad", password="secret123")


def test_s_user_update_all_none_raises():
    """Запрещает пустой апдейт без полей"""
    with pytest.raises(ValidationError, match="Не передано ни одного поля"):
        SUserUpdate()


def test_s_user_update_one_field_passes():
    """Пропускает апдейт с одним полем"""
    assert SUserUpdate(bio="new bio").bio == "new bio"


def test_s_user_update_invalid_gender():
    """Отклоняет невалидный gender"""
    with pytest.raises(ValidationError):
        SUserUpdate(gender="other")


def test_s_user_update_valid_genders():
    """Пропускает male и female"""
    assert SUserUpdate(gender="male").gender == "male"
    assert SUserUpdate(gender="female").gender == "female"


def test_s_user_update_bio_too_long():
    """Отклоняет bio длиннее 500 символов"""
    with pytest.raises(ValidationError):
        SUserUpdate(bio="x" * 501)


def test_s_user_from_attributes():
    """Собирает SUser из ORM-подобного объекта"""
    obj = SimpleNamespace(
        id=1,
        username="john",
        email="john@example.com",
        role="user",
        avatar_id=None,
        bio=None,
        birth_date=None,
        gender=None,
        created_at=datetime.now(timezone.utc),
    )
    user = SUser.model_validate(obj)
    assert user.id == 1
    assert user.role == "user"


def test_s_user_invalid_role():
    """Отклоняет невалидную роль"""
    obj = SimpleNamespace(
        id=1,
        username="john",
        email="john@example.com",
        role="superadmin",
        avatar_id=None,
        bio=None,
        birth_date=None,
        gender=None,
        created_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        SUser.model_validate(obj)


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