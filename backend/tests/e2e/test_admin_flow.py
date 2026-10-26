import pytest

from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from tests.e2e.conftest import make_proto_response


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


async def _register_and_login(client, email, password="secret123"):
    """Регистрирует, логинит, возвращает token"""
    await client.post(
        "/auth/register",
        json={
            "username": email,
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )
    login = await client.post("/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


async def test_admin_login_and_list(e2e_client):
    """Явно созданный админ видит заявки обычного пользователя"""
    from repositories.auth import UserRepository

    await UserRepository.ensure_admin("admin@example.com", "admin123", "admin")

    client, _ = e2e_client

    user_token = await _register_and_login(client, "user-for-admin@example.com")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    await client.patch("/auth/me", json=make_profile(), headers=user_headers)
    create = await client.post(
        "/applications",
        json={
            "product_type": "term_loan",
            "requested_amount_rub": 1500000,
            "term_months": 24,
            "purpose": "working_capital",
            "segment": "small",
            "consents": {
                "personal_data_processing": True,
                "credit_history_request": True,
                "version": "2026-10-25",
            },
        },
        headers=user_headers,
    )
    assert create.status_code == 201

    admin_login = await client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin123"}
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    listing = await client.get("/admin/applications", headers=admin_headers)
    assert listing.status_code == 200
    assert len(listing.json()["applications"]) == 1

    stats = await client.get("/admin/stats/overview", headers=admin_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total"] == 1
    assert body["by_status"].get("confirmed") == 1


async def test_regular_user_forbidden_on_admin(e2e_client):
    """Обычный пользователь получает 403"""
    client, _ = e2e_client
    token = await _register_and_login(client, "regular@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    r1 = await client.get("/admin/applications", headers=headers)
    assert r1.status_code == 403

    r2 = await client.get("/admin/stats/overview", headers=headers)
    assert r2.status_code == 403


async def test_unauthorized_returns_401(e2e_client):
    """Без токена — 401"""
    client, _ = e2e_client
    r1 = await client.get("/admin/applications")
    assert r1.status_code == 401
    r2 = await client.get("/admin/stats/overview")
    assert r2.status_code == 401


async def test_admin_manual_decision_confirms_application(e2e_client):
    """Ручное одобрение переводит заявку из серой зоны в confirmed"""
    from repositories.auth import UserRepository

    await UserRepository.ensure_admin("admin-review@example.com", "admin123", "admin")

    client, servicer = e2e_client
    servicer.response_factory = lambda r: make_proto_response(
        r.application_id, scoring_pb2.DECISION_MANUAL_REVIEW
    )

    user_token = await _register_and_login(client, "manual-review@example.com")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    await client.patch("/auth/me", json=make_profile(), headers=user_headers)
    create = await client.post(
        "/applications",
        json={
            "product_type": "term_loan",
            "requested_amount_rub": 1500000,
            "term_months": 24,
            "purpose": "equipment",
            "segment": "small",
            "consents": {
                "personal_data_processing": True,
                "credit_history_request": True,
                "version": "2026-10-25",
            },
        },
        headers=user_headers,
    )
    assert create.status_code == 201
    assert create.json()["status"] == "different"
    app_id = create.json()["application_id"]

    admin_login = await client.post(
        "/auth/login", json={"email": "admin-review@example.com", "password": "admin123"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    decision = await client.post(
        f"/admin/applications/{app_id}/decision",
        json={"decision": "approve", "comment": "Проверено вручную"},
        headers=admin_headers,
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"

    events = await client.get(f"/applications/{app_id}/events", headers=admin_headers)
    manual_events = [e for e in events.json() if e["event_type"] == "manual_decision"]
    assert len(manual_events) == 1
    assert manual_events[0]["payload"]["status"] == "confirmed"


async def test_admin_manual_decision_rejects_auto_approved(e2e_client):
    """Ручное решение нельзя применить к заявке с автоматическим решением"""
    from repositories.auth import UserRepository

    await UserRepository.ensure_admin("admin-auto@example.com", "admin123", "admin")

    client, _ = e2e_client
    user_token = await _register_and_login(client, "auto-approved@example.com")
    user_headers = {"Authorization": f"Bearer {user_token}"}
    await client.patch("/auth/me", json=make_profile(), headers=user_headers)
    create = await client.post(
        "/applications",
        json={
            "product_type": "term_loan",
            "requested_amount_rub": 1500000,
            "term_months": 24,
            "purpose": "equipment",
            "segment": "small",
            "consents": {
                "personal_data_processing": True,
                "credit_history_request": True,
                "version": "2026-10-25",
            },
        },
        headers=user_headers,
    )
    assert create.json()["status"] == "confirmed"
    app_id = create.json()["application_id"]

    admin_login = await client.post(
        "/auth/login", json={"email": "admin-auto@example.com", "password": "admin123"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    decision = await client.post(
        f"/admin/applications/{app_id}/decision",
        json={"decision": "decline"},
        headers=admin_headers,
    )
    assert decision.status_code == 409


async def test_regular_user_cannot_apply_manual_decision(e2e_client):
    """Обычный пользователь не может принять решение по заявке"""
    client, _ = e2e_client
    token = await _register_and_login(client, "no-review@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post(
        "/admin/applications/unknown/decision",
        json={"decision": "approve"},
        headers=headers,
    )
    assert response.status_code == 403
