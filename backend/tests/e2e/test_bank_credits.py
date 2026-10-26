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


async def test_not_issued_and_other_clients_credits_do_not_count(e2e_client):
    client, servicer = e2e_client
    seen = _recording(servicer)
    other = await _setup_full_profile(client, "other-client@example.com")
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
