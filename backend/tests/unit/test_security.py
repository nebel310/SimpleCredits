from datetime import datetime, timezone

import pytest
from jose import jwt
from passlib.context import CryptContext

from utils.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash


def test_create_access_token_returns_valid_jwt():
    """Создаёт валидный JWT с полем sub и exp"""
    token = create_access_token({"sub": "user@example.com"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "user@example.com"
    assert "exp" in payload


def test_create_access_token_expires_in_configured_time():
    """Время жизни токена около 15 минут"""
    token = create_access_token({"sub": "user@example.com"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    delta = (exp - datetime.now(timezone.utc)).total_seconds()
    assert 14 * 60 <= delta <= 15 * 60


def test_create_access_token_preserves_custom_data():
    """Сохраняет дополнительные поля в payload"""
    token = create_access_token({"sub": "user@example.com", "role": "admin"})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["role"] == "admin"


def test_create_access_token_overwrites_exp():
    """Перезаписывает exp, переданный в data"""
    token = create_access_token({"sub": "user@example.com", "exp": 0})
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["exp"] > 0


def test_get_password_hash_is_salted():
    """Два хэша одного пароля различаются из-за соли"""
    assert get_password_hash("password123") != get_password_hash("password123")


def test_get_password_hash_verifies_correct_password():
    """Хэш подтверждает правильный пароль"""
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    assert ctx.verify("password123", get_password_hash("password123"))


def test_get_password_hash_rejects_wrong_password():
    """Хэш не подтверждает неправильный пароль"""
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    assert not ctx.verify("wrong", get_password_hash("password123"))