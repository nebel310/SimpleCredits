import asyncio
import json

import httpx
import pytest
import websockets

from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2


def make_profile():
    """Полный профиль компании/финансов/КИ"""
    return {
        "company": {
            "inn": "7701234567",
            "ogrn": "1027700132195",
            "legal_name": "ООО Ромашка",
            "legal_form": "llc",
            "okved": "62.01",
            "region": "Москва",
            "registration_date": "2018-04-12T00:00:00Z",
            "employee_count": 25,
        },
        "financials": {
            "annual_revenue_rub": 42000000,
            "annual_net_profit_rub": 6500000,
            "ebitda_rub": 8200000,
            "total_debt_rub": 3000000,
            "monthly_revenue_rub": 3500000,
            "monthly_expenses_rub": 2800000,
            "accounts_receivable_rub": 1200000,
            "cash_balance_rub": 900000,
            "period_end": "2025-12-31T00:00:00Z",
        },
        "credit_history": {
            "active_obligations_count": 2,
            "total_outstanding_rub": 3000000,
            "monthly_debt_payments_rub": 120000,
            "max_days_past_due_12m": 0,
            "has_current_past_due": False,
            "credit_utilization": 0.35,
            "closed_obligations_count": 4,
            "applications_last_6m": 1,
        },
    }


def make_body(product_type="term_loan"):
    """Тело POST /applications"""
    body = {
        "requested_amount_rub": 1500000,
        "term_months": 24,
        "purpose": "working_capital",
        "segment": "small",
    }
    if product_type is not None:
        body["product_type"] = product_type
    return body


async def _setup_user(client: httpx.AsyncClient, email: str) -> str:
    """Регистрирует, логинит, заполняет профиль; возвращает access_token"""
    await client.post(
        "/auth/register",
        json={
            "username": email,
            "email": email,
            "password": "secret123",
            "password_confirm": "secret123",
        },
    )
    login = await client.post("/auth/login", json={"email": email, "password": "secret123"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.patch("/auth/me", json=make_profile(), headers=headers)
    return token


async def _collect_messages(ws, count: int, timeout: float = 10.0) -> list[dict]:
    """Собирает до count сообщений или до таймаута"""
    messages = []
    try:
        for _ in range(count):
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            messages.append(json.loads(raw))
    except asyncio.TimeoutError:
        pass
    return messages


async def test_ws_connect_and_receive_status_confirmed(real_server):
    """Connect → POST /applications → status_changed confirmed"""
    base_url, _ = real_server

    async with httpx.AsyncClient(base_url=base_url) as client:
        token = await _setup_user(client, "ws-happy@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        ws_url = base_url.replace("http://", "ws://") + f"/ws/applications?token={token}"

        async with websockets.connect(ws_url) as ws:
            create = await client.post("/applications", json=make_body(), headers=headers)
            assert create.status_code == 201
            assert create.json()["status"] == "confirmed"
            app_id = create.json()["application_id"]

            messages = await _collect_messages(ws, count=2)
            types = [m["type"] for m in messages]

            assert "event" in types
            enriched = next(m for m in messages if m["type"] == "event")
            assert enriched["event_type"] == "enriched"
            assert enriched["application_id"] == app_id

            assert "status_changed" in types
            status_msg = next(m for m in messages if m["type"] == "status_changed")
            assert status_msg["status"] == "confirmed"
            assert status_msg["application_id"] == app_id
            # клиенту по WebSocket — статус, объяснение и действия, без балла и PD модели
            assert "score" not in status_msg["payload"] and "reason_codes" not in status_msg["payload"]
            assert status_msg["payload"]["actions"] == ["accept", "reject"]
            assert status_msg["payload"]["explanation"].startswith("Одобрено")


async def test_ws_receives_failed_on_ml_down(real_server):
    """ML down → status_changed failed"""
    import grpc

    base_url, servicer = real_server

    async with httpx.AsyncClient(base_url=base_url) as client:
        token = await _setup_user(client, "ws-fail@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "down")

        ws_url = base_url.replace("http://", "ws://") + f"/ws/applications?token={token}"

        async with websockets.connect(ws_url) as ws:
            create = await client.post("/applications", json=make_body(), headers=headers)
            assert create.status_code == 502

            messages = await _collect_messages(ws, count=2)
            types = [m["type"] for m in messages]

            assert "event" in types
            assert "status_changed" in types
            status_msg = next(m for m in messages if m["type"] == "status_changed")
            assert status_msg["status"] == "failed"


async def test_ws_invalid_token_rejected(real_server):
    """Невалидный JWT → закрытие 4401"""
    base_url, _ = real_server
    ws_url = base_url.replace("http://", "ws://") + "/ws/applications?token=invalid"

    with pytest.raises(websockets.ConnectionClosed) as exc:
        async with websockets.connect(ws_url) as ws:
            await ws.recv()

    assert exc.value.code == 4401


async def test_ws_two_connections_both_receive(real_server):
    """Два соединения одного пользователя получают broadcast"""
    base_url, _ = real_server

    async with httpx.AsyncClient(base_url=base_url) as client:
        token = await _setup_user(client, "ws-multi@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        ws_url = base_url.replace("http://", "ws://") + f"/ws/applications?token={token}"

        async with websockets.connect(ws_url) as ws1, websockets.connect(ws_url) as ws2:
            create = await client.post("/applications", json=make_body(), headers=headers)
            assert create.status_code == 201

            msgs1 = await _collect_messages(ws1, count=2)
            msgs2 = await _collect_messages(ws2, count=2)

            assert any(m["type"] == "status_changed" for m in msgs1)
            assert any(m["type"] == "status_changed" for m in msgs2)


async def test_ws_reconnect_restores_events(real_server):
    """После disconnect/reconnect события читаются через GET /events"""
    base_url, _ = real_server

    async with httpx.AsyncClient(base_url=base_url) as client:
        token = await _setup_user(client, "ws-reconnect@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        ws_url = base_url.replace("http://", "ws://") + f"/ws/applications?token={token}"

        async with websockets.connect(ws_url) as ws:
            create = await client.post("/applications", json=make_body(), headers=headers)
            assert create.status_code == 201
            app_id = create.json()["application_id"]
            await _collect_messages(ws, count=2)

        events = await client.get(f"/applications/{app_id}/events", headers=headers)
        assert events.status_code == 200
        types = [e["event_type"] for e in events.json()]
        assert "created" in types
        assert "enriched" in types
        assert "scored" in types
        assert "status_changed" in types

async def test_ws_rejects_token_after_logout(real_server):
    """После выхода из аккаунта канал по старому токену не открывается (4401), как и HTTP"""
    base_url, _ = real_server
    async with httpx.AsyncClient(base_url=base_url) as client:
        token = await _setup_user(client, "ws-logout@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        assert (await client.post("/auth/logout", headers=headers)).status_code == 200
        assert (await client.get("/auth/me", headers=headers)).status_code == 401

    ws_url = base_url.replace("http://", "ws://") + f"/ws/applications?token={token}"
    with pytest.raises(websockets.ConnectionClosed) as exc:
        async with websockets.connect(ws_url) as ws:
            await ws.recv()
    assert exc.value.code == 4401
