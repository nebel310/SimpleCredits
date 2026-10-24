import grpc
import pytest
from sqlalchemy import update

import database
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from models.auth import UserOrm
from models.applications import ApplicationOrm


def make_profile():
    """Возвращает полный PATCH /auth/me с компанией/финансами/КИ"""
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


def make_body(product_type: str | None = "term_loan"):
    """Возвращает тело POST /applications"""
    body = {
        "requested_amount_rub": 1500000,
        "term_months": 24,
        "purpose": "equipment",
        "segment": "small",
    }
    if product_type is not None:
        body["product_type"] = product_type
    return body


async def _register(client, email, password="secret123"):
    return await client.post(
        "/auth/register",
        json={
            "username": "user",
            "email": email,
            "password": password,
            "password_confirm": password,
        },
    )


async def _login(client, email, password="secret123"):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _auth_headers(client, email, password="secret123"):
    await _register(client, email, password)
    login = await _login(client, email, password)
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _setup_full_profile(client, email):
    """Регистрирует, логинит, заполняет профиль и возвращает headers"""
    headers = await _auth_headers(client, email)
    await client.patch("/auth/me", json=make_profile(), headers=headers)
    return headers


async def _make_admin(email):
    async with database.new_session() as session:
        await session.execute(
            update(UserOrm).where(UserOrm.email == email).values(role="admin")
        )
        await session.commit()


async def test_full_happy_path_confirmed(e2e_client):
    """Полный путь: approve + product_type задан → confirmed"""
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "happy@example.com")

    create = await client.post("/applications", json=make_body("term_loan"), headers=headers)
    assert create.status_code == 201
    data = create.json()
    app_id = data["application_id"]
    assert data["status"] == "confirmed"
    assert data["scoring_result"]["score"] == 712
    assert data["scoring_result"]["decision"]["decision"] == "approve"
    assert data["enriched_data"]["egrul"] is not None
    assert data["enriched_data"]["fns"] is not None
    assert data["enriched_data"]["bki"] is not None

    detail = await client.get(f"/applications/{app_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "confirmed"

    listing = await client.get("/applications", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["applications"]) == 1

    events = await client.get(f"/applications/{app_id}/events", headers=headers)
    assert events.status_code == 200
    event_types = [e["event_type"] for e in events.json()]
    assert "created" in event_types
    assert "enriched" in event_types
    assert "scored" in event_types
    assert "status_changed" in event_types

    async with database.new_session() as session:
        apps = (await session.execute(
            __import__("sqlalchemy").select(ApplicationOrm)
        )).scalars().all()
    assert len(apps) == 1
    assert apps[0].status == "confirmed"


async def test_approve_no_product_type_different(e2e_client):
    """approve + product_type не задан → different"""
    client, _ = e2e_client
    headers = await _setup_full_profile(client, "noprod@example.com")

    create = await client.post("/applications", json=make_body(None), headers=headers)
    assert create.status_code == 201
    assert create.json()["status"] == "different"


async def test_approve_with_conditions_different(e2e_client):
    """approve_with_conditions → different"""
    client, servicer = e2e_client
    servicer.response_factory = lambda r: __import__(
        "tests.e2e.conftest", fromlist=["make_proto_response"]
    ).make_proto_response(r.application_id, scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS)

    headers = await _setup_full_profile(client, "cond@example.com")
    create = await client.post("/applications", json=make_body(), headers=headers)
    assert create.status_code == 201
    assert create.json()["status"] == "different"


async def test_manual_review_different(e2e_client):
    """manual_review → different"""
    client, servicer = e2e_client
    servicer.response_factory = lambda r: __import__(
        "tests.e2e.conftest", fromlist=["make_proto_response"]
    ).make_proto_response(r.application_id, scoring_pb2.DECISION_MANUAL_REVIEW)

    headers = await _setup_full_profile(client, "review@example.com")
    create = await client.post("/applications", json=make_body(), headers=headers)
    assert create.status_code == 201
    assert create.json()["status"] == "different"


async def test_decline_declined(e2e_client):
    """decline → declined"""
    client, servicer = e2e_client
    servicer.response_factory = lambda r: __import__(
        "tests.e2e.conftest", fromlist=["make_proto_response"]
    ).make_proto_response(r.application_id, scoring_pb2.DECISION_DECLINE)

    headers = await _setup_full_profile(client, "decline@example.com")
    create = await client.post("/applications", json=make_body(), headers=headers)
    assert create.status_code == 201
    assert create.json()["status"] == "declined"


async def test_ml_unavailable_failed(e2e_client):
    """ML down → failed + 502"""
    client, servicer = e2e_client
    servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "down")

    headers = await _setup_full_profile(client, "mldown@example.com")
    response = await client.post("/applications", json=make_body(), headers=headers)
    assert response.status_code == 502

    async with database.new_session() as session:
        from sqlalchemy import select
        apps = (await session.execute(select(ApplicationOrm))).scalars().all()
    assert len(apps) == 1
    assert apps[0].status == "failed"


async def test_profile_incomplete_returns_400(e2e_client):
    """Профиль пуст и в теле нет company/financials/credit_history → 400"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "empty@example.com")
    response = await client.post("/applications", json=make_body(), headers=headers)
    assert response.status_code == 400
    assert "Профиль" in response.json()["detail"]


async def test_profile_via_create_body(e2e_client):
    """Профиль заполняется из тела POST /applications"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "inline@example.com")

    body = {**make_body("term_loan"), **make_profile()}
    create = await client.post("/applications", json=body, headers=headers)
    assert create.status_code == 201
    assert create.json()["status"] == "confirmed"

    me = await client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["company"]["legal_name"] == "ООО Ромашка"


async def test_user_cannot_see_other_application(e2e_client):
    """Обычный пользователь → 403 на чужую заявку"""
    client, _ = e2e_client
    owner = await _setup_full_profile(client, "owner@example.com")
    stranger = await _setup_full_profile(client, "stranger@example.com")

    create = await client.post("/applications", json=make_body(), headers=owner)
    app_id = create.json()["application_id"]

    response = await client.get(f"/applications/{app_id}", headers=stranger)
    assert response.status_code == 403


async def test_admin_sees_other_application(e2e_client):
    """Админ видит чужую заявку"""
    client, _ = e2e_client
    owner = await _setup_full_profile(client, "owner2@example.com")
    admin = await _setup_full_profile(client, "admin2@example.com")
    await _make_admin("admin2@example.com")

    create = await client.post("/applications", json=make_body(), headers=owner)
    app_id = create.json()["application_id"]

    response = await client.get(f"/applications/{app_id}", headers=admin)
    assert response.status_code == 200


async def test_get_missing_application(e2e_client):
    """Несуществующая заявка → 404"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "missing@example.com")
    response = await client.get("/applications/nope", headers=headers)
    assert response.status_code == 404


async def test_products_available(e2e_client):
    """Каталог продуктов доступен без авторизации"""
    client, _ = e2e_client
    response = await client.get("/products")
    assert response.status_code == 200
    assert len(response.json()["products"]) == 5