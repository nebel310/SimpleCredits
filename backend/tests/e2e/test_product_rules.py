"""Выбранный клиентом продукт проверяется по каталогу; сегмент считает банк"""
from datetime import datetime, timedelta, timezone

from tests.e2e.test_full_flow import _auth_headers, _setup_full_profile, make_body, make_profile


async def _post(client, headers, **overrides):
    body = make_body("term_loan")
    body.update(overrides)
    return await client.post("/applications", json=body, headers=headers)


async def test_microloan_not_for_small_business(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "small@example.com")  # ООО, 25 сотрудников → малый бизнес
    r = await _post(client, headers, product_type="microloan", requested_amount_rub=1_000_000, term_months=12)
    assert r.status_code == 422 and "микробизнес" in r.json()["detail"]


async def test_purpose_term_amount_checked(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "bounds@example.com")
    assert (await _post(client, headers, purpose="equipment")).status_code == 422
    assert (await _post(client, headers, product_type="overdraft", term_months=60)).status_code == 422
    assert (await _post(client, headers, requested_amount_rub=50_000)).status_code == 422


async def test_legal_form_and_company_age_checked(e2e_client):
    client, _ = e2e_client
    headers = await _auth_headers(client, "ip@example.com")
    profile = make_profile()
    profile["company"].update(inn="771234567890", ogrn="318774600123456", legal_form="individual_entrepreneur")
    await client.patch("/auth/me", json=profile, headers=headers)
    r = await _post(client, headers, product_type="credit_line", requested_amount_rub=5_000_000)
    assert r.status_code == 422 and "доступен только для" in r.json()["detail"]

    profile["company"]["registration_date"] = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    await client.patch("/auth/me", json=profile, headers=headers)
    r = await _post(client, headers)
    assert r.status_code == 422 and "не меньше 12 мес." in r.json()["detail"]


async def test_segment_is_derived_from_company(e2e_client):
    """Клиент прислал «микро», но у компании 25 сотрудников — в заявке будет малый бизнес"""
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "segment@example.com")
    r = await _post(client, headers, segment="micro")
    assert r.status_code == 201
    assert r.json()["application"]["segment"] == "small"
