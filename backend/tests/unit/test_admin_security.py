from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from utils.security import require_admin, require_role


def _user(role: str):
    """Возвращает объект пользователя с ролью"""
    return SimpleNamespace(id=1, email="u@example.com", role=role)


async def test_require_admin_allows_admin():
    """require_admin пропускает admin"""
    checker = require_admin
    user = _user("admin")
    result = await checker(user)
    assert result is user


async def test_require_admin_rejects_user():
    """require_admin отклоняет user с 403"""
    checker = require_admin
    user = _user("user")
    with pytest.raises(HTTPException) as exc:
        await checker(user)
    assert exc.value.status_code == 403


async def test_require_role_allows_listed():
    """require_role пропускает любую из перечисленных ролей"""
    checker = require_role("admin", "user")
    user = _user("user")
    result = await checker(user)
    assert result is user


async def test_require_role_rejects_others():
    """require_role отклоняет роль не из списка"""
    checker = require_role("admin")
    user = _user("user")
    with pytest.raises(HTTPException):
        await checker(user)