"""Проверки входных данных: регистрация, профиль, заявка"""
from datetime import datetime, timedelta, timezone

from tests.e2e.test_full_flow import _auth_headers, _setup_full_profile, make_body, make_profile


def _reg(email, password="secret123", confirm=None, username=None):
    return {"username": username or email, "email": email, "password": password, "password_confirm": confirm or password}


async def test_register_short_password_rejected(e2e_client):
    client, _ = e2e_client
    r = await client.post("/auth/register", json=_reg("short@example.com", "12345"))
    assert r.status_code == 422


async def test_register_passwords_must_match(e2e_client):
    client, _ = e2e_client
    r = await client.post("/auth/register", json=_reg("mismatch@example.com", "secret123", "secret124"))
    assert r.status_code == 422
    assert "Пароли не совпадают" in r.text


async def test_register_duplicate_username_rejected(e2e_client):
    client, _ = e2e_client
    assert (await client.post("/auth/register", json=_reg("a@example.com", username="ivan"))).status_code == 201
    r = await client.post("/auth/register", json=_reg("b@example.com", username="ivan"))
    assert r.status_code == 400
    assert "именем уже существует" in r.json()["detail"]


async def test_profile_future_dates_rejected(e2e_client):
    client, _ = e2e_client
    headers = await _auth_headers(client, "future@example.com")
    profile = make_profile()
    profile["company"]["registration_date"] = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = await client.patch("/auth/me", json=profile, headers=headers)
    assert r.status_code == 422 and "в будущем" in r.text
    profile = make_profile()
    profile["financials"]["period_end"] = "2099-01-01T00:00:00Z"
    r = await client.patch("/auth/me", json=profile, headers=headers)
    assert r.status_code == 422


async def test_profile_today_is_allowed(e2e_client):
    """Сегодняшняя дата (и «завтра» по UTC из-за часовых поясов) — допустима"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "today@example.com")
    profile = make_profile()
    profile["financials"]["period_end"] = (datetime.now(timezone.utc) + timedelta(hours=20)).isoformat()
    r = await client.patch("/auth/me", json=profile, headers=headers)
    assert r.status_code == 200


async def test_application_zero_amount_rejected(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "zero@example.com")
    body = make_body()
    body["requested_amount_rub"] = 0
    r = await client.post("/applications", json=body, headers=headers)
    assert r.status_code == 422


async def test_financials_must_be_consistent(e2e_client):
    """Месячная выручка, прибыль и EBITDA не больше годовой выручки — иначе правила нагрузки обходятся"""
    from tests.e2e.test_full_flow import _setup_full_profile, make_profile
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "consistent@example.com")
    fin = make_profile()["financials"]
    for field, text in [("monthly_revenue_rub", "Выручка в месяц"), ("annual_net_profit_rub", "Чистая прибыль"), ("ebitda_rub", "EBITDA")]:
        bad = {**fin, field: fin["annual_revenue_rub"] + 1}
        r = await client.patch("/auth/me", json={"financials": bad}, headers=headers)
        assert r.status_code == 422 and text in str(r.json()["detail"])
