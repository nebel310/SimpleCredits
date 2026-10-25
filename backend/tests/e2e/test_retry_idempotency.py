"""Повтор проверки после сбоя ML и защита от дублей заявок"""
import asyncio

import grpc
from sqlalchemy import select

import database
from models.applications import ApplicationOrm
from tests.e2e.test_full_flow import _auth_headers, _setup_full_profile, make_body


async def _count():
    async with database.new_session() as session:
        return len((await session.execute(select(ApplicationOrm))).scalars().all())


async def test_failed_response_contains_application_id_and_retry_works(e2e_client):
    client, servicer = e2e_client
    headers = await _setup_full_profile(client, "retry@example.com")
    servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "ML лежит")
    r = await client.post("/applications", json=make_body("term_loan"), headers=headers)
    assert r.status_code == 502
    app_id = r.json()["application_id"]
    assert app_id and (await client.get(f"/applications/{app_id}", headers=headers)).json()["status"] == "failed"

    # ML всё ещё лежит — повтор снова failed, заявка та же
    again = await client.post(f"/applications/{app_id}/retry", headers=headers)
    assert again.status_code == 502 and again.json()["application_id"] == app_id

    servicer.score_error = None
    ok = await client.post(f"/applications/{app_id}/retry", headers=headers)
    assert ok.status_code == 200 and ok.json()["status"] == "confirmed"
    assert await _count() == 1
    events = [e["event_type"] for e in (await client.get(f"/applications/{app_id}/events", headers=headers)).json()]
    assert events.count("retry_started") == 2 and events.count("failed") == 2 and events[-1] == "status_changed"


async def test_retry_only_for_failed_and_only_owner(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "noretry@example.com")
    app_id = (await client.post("/applications", json=make_body("term_loan"), headers=headers)).json()["application_id"]
    r = await client.post(f"/applications/{app_id}/retry", headers=headers)
    assert r.status_code == 409
    stranger = await _auth_headers(client, "other@example.com")
    assert (await client.post(f"/applications/{app_id}/retry", headers=stranger)).status_code == 403


async def test_same_idempotency_key_returns_same_application(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "idem@example.com")
    h = {**headers, "Idempotency-Key": "attempt-1"}
    first = await client.post("/applications", json=make_body("term_loan"), headers=h)
    second = await client.post("/applications", json=make_body("term_loan"), headers=h)
    assert first.status_code == second.status_code == 201
    assert first.json()["application_id"] == second.json()["application_id"]
    third = await client.post("/applications", json=make_body("term_loan"), headers={**headers, "Idempotency-Key": "attempt-2"})
    assert third.json()["application_id"] != first.json()["application_id"]
    assert await _count() == 2


async def test_parallel_requests_with_same_key_create_one_application(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "parallel@example.com")
    h = {**headers, "Idempotency-Key": "double-click"}
    results = await asyncio.gather(*[client.post("/applications", json=make_body("term_loan"), headers=h) for _ in range(3)])
    ids = {r.json()["application_id"] for r in results}
    assert len(ids) == 1 and await _count() == 1


async def test_without_key_each_request_is_new(e2e_client):
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "nokey@example.com")
    await client.post("/applications", json=make_body("term_loan"), headers=headers)
    await client.post("/applications", json=make_body("term_loan"), headers=headers)
    assert await _count() == 2
