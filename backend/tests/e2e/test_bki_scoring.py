"""Кредитная история для модели берётся из БКИ, снимок заявки совпадает с тем, что видела модель"""
from services import enrichment as enrichment_module
from services.mock_data import generate_bki
from tests.e2e.conftest import make_proto_response
from tests.e2e.test_full_flow import _setup_full_profile, make_body, make_profile


async def test_model_gets_bki_history_and_card_matches(e2e_client):
    client, servicer = e2e_client
    seen = {}

    def factory(request):
        seen["active"] = request.credit_history.active_obligations_count
        seen["payments"] = request.credit_history.monthly_debt_payments_rub
        seen["past_due"] = request.credit_history.has_current_past_due
        return make_proto_response(request.application_id)

    servicer.response_factory = factory
    headers = await _setup_full_profile(client, "bki@example.com")
    bki = generate_bki(make_profile()["company"]["inn"])
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()

    assert seen == {"active": bki.active_obligations_count, "payments": bki.monthly_debt_payments_rub, "past_due": bki.has_current_past_due}
    assert d["credit_history"]["active_obligations_count"] == bki.active_obligations_count
    assert d["credit_history"]["monthly_debt_payments_rub"] == d["enriched_data"]["bki"]["monthly_debt_payments_rub"]


async def test_profile_history_used_when_bki_is_down(e2e_client, monkeypatch):
    client, servicer = e2e_client
    seen = {}

    def factory(request):
        seen["active"] = request.credit_history.active_obligations_count
        return make_proto_response(request.application_id)

    async def bki_down(inn):
        raise RuntimeError("БКИ не отвечает")

    monkeypatch.setattr(enrichment_module, "_call_bki", bki_down)
    servicer.response_factory = factory
    headers = await _setup_full_profile(client, "nobki@example.com")
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["enriched_data"]["bki"] is None
    assert seen["active"] == make_profile()["credit_history"]["active_obligations_count"]
