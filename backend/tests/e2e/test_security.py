"""Проверки доступа: кто что может видеть и менять"""
from tests.e2e.test_full_flow import _auth_headers, _make_admin, _setup_full_profile


async def test_users_list_forbidden_for_client(e2e_client):
    """Клиент не может выгрузить список пользователей с их финансами"""
    client, _ = e2e_client
    await _setup_full_profile(client, "victim@example.com")
    headers = await _auth_headers(client, "curious@example.com")
    r = await client.get("/auth/users", headers=headers)
    assert r.status_code == 403


async def test_users_list_allowed_for_admin(e2e_client):
    """Администратор видит список пользователей"""
    client, _ = e2e_client
    await _setup_full_profile(client, "someone@example.com")
    await _auth_headers(client, "boss@example.com")
    await _make_admin("boss@example.com")
    headers = await _auth_headers(client, "boss@example.com")
    r = await client.get("/auth/users", headers=headers)
    assert r.status_code == 200
    emails = {u["email"] for u in r.json()["users"]}
    assert {"someone@example.com", "boss@example.com"} <= emails


async def test_users_list_requires_token(e2e_client):
    """Без токена — 401"""
    client, _ = e2e_client
    r = await client.get("/auth/users")
    assert r.status_code == 401
