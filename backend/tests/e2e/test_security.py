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


async def _login_tokens(client, email):
    await client.post("/auth/register", json={"username": email, "email": email, "password": "secret123", "password_confirm": "secret123"})
    return (await client.post("/auth/login", json={"email": email, "password": "secret123"})).json()


async def test_refresh_token_has_expiry_and_works_both_ways(e2e_client):
    """Refresh-токен с exp; продление работает через тело и (для совместимости) через query"""
    import base64, json as _json
    client, _ = e2e_client
    tokens = await _login_tokens(client, "refresh@example.com")
    rt = tokens["refresh_token"]
    payload = _json.loads(base64.urlsafe_b64decode(rt.split(".")[1] + "=="))
    assert "exp" in payload and payload["type"] == "refresh"
    by_body = await client.post("/auth/refresh", json={"refresh_token": rt})
    by_query = await client.post(f"/auth/refresh?refresh_token={rt}")
    assert by_body.status_code == 200 and by_query.status_code == 200
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {by_body.json()['access_token']}"})
    assert me.status_code == 200


async def test_refresh_rejects_garbage_missing_and_after_logout(e2e_client):
    client, _ = e2e_client
    tokens = await _login_tokens(client, "refresh2@example.com")
    assert (await client.post("/auth/refresh", json={"refresh_token": "garbage"})).status_code == 400
    assert (await client.post("/auth/refresh")).status_code == 400
    await client.post("/auth/logout", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert (await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})).status_code == 400


async def test_refresh_token_is_not_an_access_token(e2e_client):
    client, _ = e2e_client
    tokens = await _login_tokens(client, "refresh3@example.com")
    r = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert r.status_code == 401
