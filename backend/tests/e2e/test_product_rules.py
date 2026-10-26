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


async def test_auto_pick_returns_selected_product(e2e_client):
    """Без выбора продукта банк подбирает подходящий: малый бизнес, оборотка 1,5 млн на 24 мес."""
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "auto@example.com")
    r = await client.post("/applications", json=make_body(None), headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["product_selected_by_system"] is True
    assert data["status"] == "different"
    assert data["application"]["product_type"] in ("term_loan", "credit_line", "overdraft")
    assert data["application"]["product_type"] == "credit_line"  # самая низкая ставка из подходящих


async def test_auto_pick_respects_purpose(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "auto-eq@example.com")
    body = make_body(None)
    body.update(purpose="equipment", requested_amount_rub=35_000_000, term_months=60)
    r = await client.post("/applications", json=body, headers=headers)
    assert r.json()["application"]["product_type"] == "leasing"


async def test_no_suitable_product_declined_with_reason(e2e_client):
    """Ни один продукт не подходит — отказ с причиной и пояснением, заявка сохраняется"""
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "none@example.com")
    body = make_body(None)
    body.update(requested_amount_rub=90_000_000)
    r = await client.post("/applications", json=body, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "declined"
    assert data["scoring_result"]["decision"]["reason_codes"] == ["NO_SUITABLE_PRODUCT"]
    assert "нет подходящего продукта" in data["explanation"]


async def test_chosen_product_is_not_marked_as_selected_by_system(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "chosen@example.com")
    r = await client.post("/applications", json=make_body("term_loan"), headers=headers)
    assert r.json()["product_selected_by_system"] is False and r.json()["status"] == "confirmed"
