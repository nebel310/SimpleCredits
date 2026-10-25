"""Банк закрывает ручную проверку своим решением"""
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from tests.e2e.test_full_flow import _auth_headers, _make_admin, _setup_full_profile, make_body
from tests.e2e.test_outcomes import respond


async def _review_and_admin(client, servicer, email, product="term_loan"):
    respond(servicer, scoring_pb2.DECISION_MANUAL_REVIEW)
    headers = await _setup_full_profile(client, email)
    app_id = (await client.post("/applications", json=make_body(product), headers=headers)).json()["application_id"]
    await _auth_headers(client, f"bank-{email}")
    await _make_admin(f"bank-{email}")
    admin = await _auth_headers(client, f"bank-{email}")
    return headers, admin, app_id


async def test_bank_approves_manual_review_then_client_accepts(e2e_client):
    client, servicer = e2e_client
    headers, admin, app_id = await _review_and_admin(client, servicer, "mr1@example.com")
    r = await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "approve", "comment": "Обороты подтверждены"}, headers=admin)
    d = r.json()
    assert r.status_code == 200 and d["status"] == "confirmed" and d["outcome"] is None
    assert d["offer"]["amount_rub"] == 1_500_000
    assert d["bank_decision"]["decision"] == "approve" and d["bank_decision"]["decided_by"] == "bank-mr1@example.com"
    assert d["explanation"] == "Обороты подтверждены"
    assert d["scoring_result"]["decision"]["decision"] == "manual_review"  # решение модели сохраняется
    assert (await client.post(f"/applications/{app_id}/accept", headers=headers)).status_code == 200


async def test_bank_counter_offer_and_decline(e2e_client):
    client, servicer = e2e_client
    _, admin, app_id = await _review_and_admin(client, servicer, "mr2@example.com")
    r = await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "approve_with_conditions", "recommended_amount_rub": 900_000}, headers=admin)
    assert r.json()["status"] == "different" and r.json()["outcome"] == "COUNTER_OFFER" and r.json()["offer"]["amount_rub"] == 900_000
    # повторное решение по уже закрытой проверке — 409
    again = await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "decline"}, headers=admin)
    assert again.status_code == 409

    _, admin, app2 = await _review_and_admin(client, servicer, "mr3@example.com")
    r = await client.post(f"/admin/applications/{app2}/decision", json={"decision": "decline", "comment": "Нагрузка выше нормы"}, headers=admin)
    assert r.json()["status"] == "declined" and r.json()["offer"] is None


async def test_conditions_need_amount_and_client_cannot_decide(e2e_client):
    client, servicer = e2e_client
    headers, admin, app_id = await _review_and_admin(client, servicer, "mr4@example.com")
    assert (await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "approve_with_conditions"}, headers=admin)).status_code == 422
    assert (await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "approve"}, headers=headers)).status_code == 403


async def test_decision_only_for_manual_review(e2e_client):
    client, servicer = e2e_client
    respond(servicer, scoring_pb2.DECISION_APPROVE)
    headers = await _setup_full_profile(client, "approved@example.com")
    app_id = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"]
    await _auth_headers(client, "bank@example.com")
    await _make_admin("bank@example.com")
    admin = await _auth_headers(client, "bank@example.com")
    r = await client.post(f"/admin/applications/{app_id}/decision", json={"decision": "decline"}, headers=admin)
    assert r.status_code == 409
