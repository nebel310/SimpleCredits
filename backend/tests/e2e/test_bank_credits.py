"""Кредиты, которые банк уже выдал клиенту, учитываются в следующей заявке"""
from services import enrichment as enrichment_module
from services.application import add_bank_credits
from services.mock_data import generate_bki
from schemas.applications import SCreditHistory
from tests.e2e.conftest import make_proto_response
from tests.e2e.test_full_flow import _setup_full_profile, make_body, make_profile


def _recording(servicer):
    """Фейковая модель одобряет и запоминает кредитную историю из последнего запроса"""
    seen = {}

    def factory(request):
        h = request.credit_history
        seen.update(active=h.active_obligations_count, outstanding=h.total_outstanding_rub, payments=h.monthly_debt_payments_rub)
        return make_proto_response(request.application_id)

    servicer.response_factory = factory
    return seen


async def _issue(client, headers):
    """Подать заявку, принять и оформить — вернуть условия выданного кредита"""
    app_id = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"]
    await client.post(f"/applications/{app_id}/accept", headers=headers)
    issued = (await client.post(f"/applications/{app_id}/issue", headers=headers)).json()
    assert issued["status"] == "issued"
    return issued["offer"]


async def test_issued_credit_counts_in_next_application(e2e_client):
    client, servicer = e2e_client
    seen = _recording(servicer)
    headers = await _setup_full_profile(client, "two-loans@example.com")
    bki = generate_bki(make_profile()["company"]["inn"])

    first = await _issue(client, headers)
    # первая заявка — только история из БКИ
    assert seen == {"active": bki.active_obligations_count, "outstanding": bki.total_outstanding_rub, "payments": bki.monthly_debt_payments_rub}

    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    expected = {
        "active": bki.active_obligations_count + 1,
        "outstanding": bki.total_outstanding_rub + first["amount_rub"],
        "payments": bki.monthly_debt_payments_rub + first["monthly_payment_rub"],
    }
    # модель видит и БКИ, и наш кредит; карточка показывает то же, что видела модель
    assert seen == expected
    assert d["credit_history"]["monthly_debt_payments_rub"] == expected["payments"]
    assert d["credit_history"]["total_outstanding_rub"] == expected["outstanding"]
    assert d["enriched_data"]["bank_credits"] == {
        "count": 1, "outstanding_rub": first["amount_rub"], "monthly_payments_rub": first["monthly_payment_rub"],
    }
    # ответ БКИ в карточке остаётся как есть
    assert d["enriched_data"]["bki"]["monthly_debt_payments_rub"] == bki.monthly_debt_payments_rub


async def test_not_issued_and_other_companies_credits_do_not_count(e2e_client):
    client, servicer = e2e_client
    seen = _recording(servicer)
    other = await _setup_full_profile(client, "other-client@example.com")
    other_company = {**make_profile()["company"], "inn": "7709999990", "legal_name": "ООО Другая компания"}
    assert (await client.patch("/auth/me", json={"company": other_company}, headers=other)).status_code == 200
    await _issue(client, other)

    headers = await _setup_full_profile(client, "own-client@example.com")
    accepted_only = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"]
    await client.post(f"/applications/{accepted_only}/accept", headers=headers)

    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    bki = generate_bki(make_profile()["company"]["inn"])
    assert seen["active"] == bki.active_obligations_count
    assert "bank_credits" not in d["enriched_data"]


async def test_bki_down_uses_profile_plus_own_credits_once(e2e_client, monkeypatch):
    client, servicer = e2e_client
    seen = _recording(servicer)
    headers = await _setup_full_profile(client, "nobki-loans@example.com")
    first = await _issue(client, headers)

    async def bki_down(inn):
        raise RuntimeError("БКИ не отвечает")

    monkeypatch.setattr(enrichment_module, "_call_bki", bki_down)
    profile = make_profile()["credit_history"]
    for _ in range(2):  # повторная обработка не удваивает наш кредит
        await client.post("/applications", json=make_body("term_loan"), headers=headers)
        assert seen["payments"] == profile["monthly_debt_payments_rub"] + first["monthly_payment_rub"]
        assert seen["active"] == profile["active_obligations_count"] + 1


def test_add_bank_credits_without_own_credits_keeps_history():
    history = SCreditHistory(
        active_obligations_count=1, total_outstanding_rub=500_000, monthly_debt_payments_rub=30_000,
        max_days_past_due_12m=0, has_current_past_due=False, credit_utilization=0.2,
        closed_obligations_count=2, applications_last_6m=1,
    )
    same, summary = add_bank_credits(history, [])
    assert same == history and summary is None
    merged, summary = add_bank_credits(history, [{"amount_rub": 1_000_000, "monthly_payment_rub": 91_680}])
    assert merged.active_obligations_count == 2
    assert merged.total_outstanding_rub == 1_500_000
    assert merged.monthly_debt_payments_rub == 121_680
    assert merged.max_days_past_due_12m == 0 and merged.credit_utilization == 0.2
    assert summary == {"count": 1, "outstanding_rub": 1_000_000, "monthly_payments_rub": 91_680}


async def _approved_ids(client, headers, n):
    return [(await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"] for _ in range(n)]


async def test_offers_made_before_another_credit_cannot_be_issued(e2e_client):
    """Несколько одобренных заявок до первой выдачи: после оформления одной остальные устаревают"""
    client, servicer = e2e_client
    _recording(servicer)
    headers = await _setup_full_profile(client, "parallel@example.com")
    first, second, third = await _approved_ids(client, headers, 3)
    # третью успели принять до выдачи первой
    assert (await client.post(f"/applications/{third}/accept", headers=headers)).status_code == 200

    await client.post(f"/applications/{first}/accept", headers=headers)
    assert (await client.post(f"/applications/{first}/issue", headers=headers)).json()["status"] == "issued"

    # вторая: предложение устарело, принять нельзя, кнопок принятия нет
    d = (await client.get(f"/applications/{second}", headers=headers)).json()
    assert d["offer_outdated"] is True and "accept" not in d["actions"] and "reject" in d["actions"]
    r = await client.post(f"/applications/{second}/accept", headers=headers)
    assert r.status_code == 409 and "оформлен другой кредит" in r.json()["detail"]

    # третья уже принята, но оформить её тоже нельзя — только отказаться
    d = (await client.get(f"/applications/{third}", headers=headers)).json()
    assert d["offer_outdated"] is True and d["actions"] == ["reject"]
    r = await client.post(f"/applications/{third}/issue", headers=headers)
    assert r.status_code == 409 and "оформлен другой кредит" in r.json()["detail"]

    # в списке — тот же признак; новая заявка учитывает выданный кредит и может быть оформлена
    listed = {a["application_id"]: a for a in (await client.get("/applications", headers=headers, params={"limit": 50})).json()["applications"]}
    assert listed[second]["offer_outdated"] and not listed[first]["offer_outdated"]
    fresh = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert fresh["offer_outdated"] is False and fresh["enriched_data"]["bank_credits"]["count"] == 1
    assert (await client.post(f"/applications/{fresh['application_id']}/accept", headers=headers)).status_code == 200
    assert (await client.post(f"/applications/{fresh['application_id']}/issue", headers=headers)).status_code == 200


async def test_offer_not_outdated_without_new_credits(e2e_client):
    client, servicer = e2e_client
    _recording(servicer)
    headers = await _setup_full_profile(client, "single@example.com")
    (app_id,) = await _approved_ids(client, headers, 1)
    d = (await client.get(f"/applications/{app_id}", headers=headers)).json()
    assert d["offer_outdated"] is False and d["actions"] == ["accept", "reject"]


async def test_second_account_of_same_company_sees_its_credits(e2e_client):
    """Заёмщик — компания: второй аккаунт с тем же ИНН видит кредиты, выданные первому"""
    client, servicer = e2e_client
    seen = _recording(servicer)
    first_account = await _setup_full_profile(client, "owner@example.com")
    issued = await _issue(client, first_account)
    second_account = await _setup_full_profile(client, "accountant@example.com")
    d = (await client.post("/applications", json=make_body("term_loan"), headers=second_account)).json()
    bki = generate_bki(make_profile()["company"]["inn"])
    assert seen["payments"] == bki.monthly_debt_payments_rub + issued["monthly_payment_rub"]
    assert d["enriched_data"]["bank_credits"]["count"] == 1
