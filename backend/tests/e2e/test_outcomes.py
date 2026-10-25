"""Тип результата (outcome) и условия предложения (offer) поверх решения модели"""
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from tests.e2e.conftest import make_proto_response
from tests.e2e.test_full_flow import _make_admin, _auth_headers, _setup_full_profile, make_body


def respond(servicer, decision, recommended=None):
    """Фейковая модель: заданное решение, грейд B, при recommended — условие REDUCE_AMOUNT"""
    def factory(request):
        resp = make_proto_response(request.application_id, decision)
        if recommended is not None:
            resp.decision.conditions.append(scoring_pb2.DecisionCondition(
                code="REDUCE_AMOUNT", description="Снизить сумму", recommended_amount_rub=recommended))
            resp.decision.reason_codes.append("LOAN_TO_REVENUE_REDUCTION")
        return resp
    servicer.response_factory = factory


async def test_approve_chosen_product_has_offer(e2e_client):
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE)
    headers = await _setup_full_profile(client, "offer@example.com")
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["status"] == "confirmed" and d["outcome"] is None
    offer = d["offer"]
    assert offer["product_type"] == "term_loan" and offer["amount_rub"] == 1_500_000 and offer["term_months"] == 24
    assert offer["rate_percent"] == 19.8  # грейд B: четверть диапазона 18–25%
    assert offer["monthly_payment_rub"] > 0 and offer["total_payment_rub"] == offer["monthly_payment_rub"] * 24


async def test_approve_auto_pick_is_alternative_product(e2e_client):
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE)
    headers = await _setup_full_profile(client, "alt@example.com")
    d = (await client.post("/applications", json=make_body(None), headers=headers)).json()
    assert d["status"] == "different" and d["outcome"] == "ALTERNATIVE_PRODUCT"
    assert d["offer"]["product_type"] == d["application"]["product_type"]


async def test_reduce_amount_is_counter_offer(e2e_client):
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS, recommended=1_000_000)
    headers = await _setup_full_profile(client, "counter@example.com")
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["status"] == "different" and d["outcome"] == "COUNTER_OFFER"
    assert d["offer"]["amount_rub"] == 1_000_000 and d["offer"]["product_type"] == "term_loan"


async def test_reduce_below_product_min_switches_product(e2e_client):
    """Кредитная линия от 1 млн, модель предлагает 750 тыс — банк предлагает другой продукт на эту сумму"""
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS, recommended=750_000)
    headers = await _setup_full_profile(client, "switch@example.com")
    body = make_body("credit_line")
    body.update(requested_amount_rub=3_500_000)
    d = (await client.post("/applications", json=body, headers=headers)).json()
    assert d["outcome"] == "ALTERNATIVE_PRODUCT"
    cond = d["scoring_result"]["decision"]["conditions"][0]
    assert cond["recommended_amount_rub"] == 750_000 and cond["recommended_product_type"] != "credit_line"
    assert d["offer"]["product_type"] == cond["recommended_product_type"] and d["offer"]["amount_rub"] == 750_000


async def test_reduce_with_no_product_goes_to_manual_review(e2e_client):
    """Рекомендованная сумма меньше минимума всех продуктов — решение принимает человек"""
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS, recommended=10_000)
    headers = await _setup_full_profile(client, "nothing@example.com")
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["outcome"] == "MANUAL_REVIEW" and d["offer"] is None
    assert d["scoring_result"]["decision"]["decision"] == "manual_review"
    assert "RECOMMENDED_AMOUNT_OUTSIDE_PRODUCTS" in d["scoring_result"]["decision"]["reason_codes"]


async def test_manual_review_and_decline(e2e_client):
    client, servicer = e2e_client
    headers = await _setup_full_profile(client, "mr@example.com")
    respond(servicer, scoring_pb2.DECISION_MANUAL_REVIEW)
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["status"] == "different" and d["outcome"] == "MANUAL_REVIEW" and d["offer"] is None
    respond(servicer, scoring_pb2.DECISION_DECLINE)
    d = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()
    assert d["status"] == "declined" and d["outcome"] is None and d["offer"] is None


async def test_admin_stats_and_filter_by_outcome(e2e_client):
    client, servicer = e2e_client
    headers = await _setup_full_profile(client, "client@example.com")
    respond(servicer, scoring_pb2.DECISION_MANUAL_REVIEW)
    await client.post("/applications", json=make_body("term_loan"), headers=headers)
    respond(servicer, scoring_pb2.DECISION_APPROVE)
    await client.post("/applications", json=make_body("term_loan"), headers=headers)
    await _auth_headers(client, "bank@example.com")
    await _make_admin("bank@example.com")
    admin = await _auth_headers(client, "bank@example.com")
    stats = (await client.get("/admin/stats/overview", headers=admin)).json()
    assert stats["by_outcome"] == {"MANUAL_REVIEW": 1}
    assert stats["by_decision"] == {"manual_review": 1, "approve": 1}
    only = (await client.get("/admin/applications?outcome=MANUAL_REVIEW", headers=admin)).json()["applications"]
    assert len(only) == 1 and only[0]["outcome"] == "MANUAL_REVIEW"
    confirmed = (await client.get("/admin/applications?status=confirmed", headers=admin)).json()["applications"]
    assert len(confirmed) == 1
