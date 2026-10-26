"""Принятие предложения и синтетическая выдача"""
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from tests.e2e.test_full_flow import _auth_headers, _make_admin, _setup_full_profile, make_body
from tests.e2e.test_outcomes import respond


async def _approved(client, servicer, email, decision=scoring_pb2.DECISION_APPROVE, product="term_loan", recommended=None):
    respond(servicer, decision, recommended)
    headers = await _setup_full_profile(client, email)
    d = (await client.post("/applications", json=make_body(product), headers=headers)).json()
    return headers, d["application_id"]


async def test_full_path_accept_then_issue(e2e_client):
    client, servicer = e2e_client
    headers, app_id = await _approved(client, servicer, "deal@example.com")
    accepted = await client.post(f"/applications/{app_id}/accept", headers=headers)
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    issued = await client.post(f"/applications/{app_id}/issue", headers=headers)
    data = issued.json()
    assert issued.status_code == 200 and data["status"] == "issued"
    assert data["contract_number"].startswith("SC-") and data["issued_at"]
    events = [e["event_type"] for e in (await client.get(f"/applications/{app_id}/events", headers=headers)).json()]
    assert events[-2:] == ["offer_accepted", "issued"]


async def test_counter_offer_can_be_accepted(e2e_client):
    client, servicer = e2e_client
    headers, app_id = await _approved(client, servicer, "counter-deal@example.com", scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS, recommended=1_000_000)
    r = await client.post(f"/applications/{app_id}/accept", headers=headers)
    assert r.status_code == 200 and r.json()["offer"]["amount_rub"] == 1_000_000


async def test_cannot_issue_before_accept_or_twice(e2e_client):
    client, servicer = e2e_client
    headers, app_id = await _approved(client, servicer, "order@example.com")
    r = await client.post(f"/applications/{app_id}/issue", headers=headers)
    assert r.status_code == 409 and "Сначала примите" in r.json()["detail"]
    await client.post(f"/applications/{app_id}/accept", headers=headers)
    assert (await client.post(f"/applications/{app_id}/accept", headers=headers)).status_code == 409
    await client.post(f"/applications/{app_id}/issue", headers=headers)
    assert (await client.post(f"/applications/{app_id}/issue", headers=headers)).status_code == 409


async def test_manual_review_and_decline_cannot_be_accepted(e2e_client):
    client, servicer = e2e_client
    headers, review_id = await _approved(client, servicer, "nomr@example.com", scoring_pb2.DECISION_MANUAL_REVIEW)
    r = await client.post(f"/applications/{review_id}/accept", headers=headers)
    assert r.status_code == 409 and "ручной проверке" in r.json()["detail"]
    respond(servicer, scoring_pb2.DECISION_DECLINE)
    declined = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"]
    assert (await client.post(f"/applications/{declined}/accept", headers=headers)).status_code == 409


async def test_reject_offer(e2e_client):
    client, servicer = e2e_client
    headers, app_id = await _approved(client, servicer, "reject@example.com")
    r = await client.post(f"/applications/{app_id}/reject", headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "rejected_by_client"
    assert (await client.post(f"/applications/{app_id}/accept", headers=headers)).status_code == 409


async def test_only_owner_can_accept(e2e_client):
    client, servicer = e2e_client
    _, app_id = await _approved(client, servicer, "owner@example.com")
    stranger = await _auth_headers(client, "stranger@example.com")
    assert (await client.post(f"/applications/{app_id}/accept", headers=stranger)).status_code == 403
    await _make_admin("stranger@example.com")
    admin = await _auth_headers(client, "stranger@example.com")
    assert (await client.post(f"/applications/{app_id}/accept", headers=admin)).status_code == 403
    assert (await client.post("/applications/nope/accept", headers=admin)).status_code == 404
