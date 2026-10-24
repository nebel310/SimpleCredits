import grpc
import pytest
from sqlalchemy import select, update

import database
from models.auth import UserOrm
from models.applications import ApplicationOrm


def make_body():
    """Возвращает валидное тело POST /scoring/applications"""
    return {
        "application": {
            "product_type": "term_loan",
            "requested_amount_rub": 1500000,
            "term_months": 24,
            "purpose": "equipment",
            "segment": "small",
            "submitted_at": "2026-03-15T10:00:00Z",
        },
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


async def _register(client, email, password="secret123"):
    """Регистрирует пользователя и возвращает ответ"""
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
    """Логинит пользователя и возвращает ответ"""
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _auth_headers(client, email, password="secret123"):
    """Регистрирует, логинит и возвращает заголовки с токеном"""
    await _register(client, email, password)
    login = await _login(client, email, password)
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _make_admin(email):
    """Повышает существующего пользователя до admin"""
    async with database.new_session() as session:
        await session.execute(
            update(UserOrm).where(UserOrm.email == email).values(role="admin")
        )
        await session.commit()


async def test_full_happy_path(e2e_client):
    """Регистрация, логин, создание заявки, чтение и список"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "happy@example.com")

    create = await client.post("/scoring/applications", json=make_body(), headers=headers)
    assert create.status_code == 201
    data = create.json()
    app_id = data["application_id"]
    assert data["score"] == 712
    assert data["risk_grade"] == "B"
    assert data["decision"]["decision"] == "approve"

    detail = await client.get(f"/scoring/applications/{app_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "scored"
    assert detail.json()["scoring_result"]["score"] == 712

    listing = await client.get("/scoring/applications", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()["applications"]) == 1
    assert listing.json()["applications"][0]["application_id"] == app_id

    async with database.new_session() as session:
        result = await session.execute(
            select(ApplicationOrm).where(ApplicationOrm.application_id == app_id)
        )
        record = result.scalars().first()
    assert record is not None
    assert record.status == "scored"
    assert record.user_id is not None


async def test_register_duplicate_email(e2e_client):
    """Повторная регистрация с тем же email возвращает 400"""
    client, _ = e2e_client
    first = await _register(client, "dup@example.com")
    assert first.status_code == 201

    second = await _register(client, "dup@example.com")
    assert second.status_code == 400


async def test_login_wrong_password(e2e_client):
    """Вход с неверным паролем возвращает 400"""
    client, _ = e2e_client
    await _register(client, "wrong@example.com")
    response = await _login(client, "wrong@example.com", "badpassword")
    assert response.status_code == 400


async def test_scoring_unauthorized(e2e_client):
    """Скоринг без токена возвращает 401"""
    client, _ = e2e_client
    response = await client.post("/scoring/applications", json=make_body())
    assert response.status_code == 401


async def test_scoring_invalid_payload(e2e_client):
    """Скоринг с невалидным телом возвращает 422"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "invalid@example.com")
    response = await client.post("/scoring/applications", json={}, headers=headers)
    assert response.status_code == 422


async def test_scoring_declined(e2e_client):
    """Отказ ML-сервиса сохраняется с decision=decline"""
    client, servicer = e2e_client
    from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2

    servicer.response_factory = lambda request: (
        __import__("tests.e2e.conftest", fromlist=["make_proto_response"])
        .make_proto_response(request.application_id, scoring_pb2.DECISION_DECLINE)
    )

    headers = await _auth_headers(client, "declined@example.com")
    create = await client.post("/scoring/applications", json=make_body(), headers=headers)
    assert create.status_code == 201
    assert create.json()["decision"]["decision"] == "decline"

    app_id = create.json()["application_id"]
    detail = await client.get(f"/scoring/applications/{app_id}", headers=headers)
    assert detail.json()["status"] == "scored"
    assert detail.json()["scoring_result"]["decision"]["decision"] == "decline"


async def test_scoring_ml_unavailable_marks_failed(e2e_client):
    """При недоступности ML заявка помечается failed, ответ 502"""
    client, servicer = e2e_client
    headers = await _auth_headers(client, "failed@example.com")
    servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "down")

    response = await client.post("/scoring/applications", json=make_body(), headers=headers)
    assert response.status_code == 502

    async with database.new_session() as session:
        result = await session.execute(select(ApplicationOrm))
        apps = result.scalars().all()

    assert len(apps) == 1
    assert apps[0].status == "failed"


async def test_pagination_flow(e2e_client):
    """Создание пяти заявок и проход по страницам через курсор"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "page@example.com")

    for _ in range(5):
        response = await client.post(
            "/scoring/applications", json=make_body(), headers=headers
        )
        assert response.status_code == 201

    page1 = await client.get("/scoring/applications?limit=2", headers=headers)
    assert page1.status_code == 200
    assert len(page1.json()["applications"]) == 2
    cursor1 = page1.json()["next_cursor"]
    assert cursor1

    page2 = await client.get(
        f"/scoring/applications?limit=2&cursor={cursor1}", headers=headers
    )
    assert len(page2.json()["applications"]) == 2

    page3 = await client.get(
        f"/scoring/applications?limit=2&cursor={page2.json()['next_cursor']}",
        headers=headers,
    )
    assert len(page3.json()["applications"]) == 1
    assert page3.json()["next_cursor"] is None


async def test_user_cannot_see_other_application(e2e_client):
    """Обычный пользователь получает 403 на чужую заявку"""
    client, _ = e2e_client

    owner_headers = await _auth_headers(client, "owner@example.com")
    stranger_headers = await _auth_headers(client, "stranger@example.com")

    create = await client.post(
        "/scoring/applications", json=make_body(), headers=owner_headers
    )
    app_id = create.json()["application_id"]

    response = await client.get(
        f"/scoring/applications/{app_id}", headers=stranger_headers
    )
    assert response.status_code == 403


async def test_admin_can_see_other_application(e2e_client):
    """Админ видит чужую заявку"""
    client, _ = e2e_client

    owner_headers = await _auth_headers(client, "owner2@example.com")
    admin_headers = await _auth_headers(client, "admin2@example.com")
    await _make_admin("admin2@example.com")

    create = await client.post(
        "/scoring/applications", json=make_body(), headers=owner_headers
    )
    app_id = create.json()["application_id"]

    response = await client.get(
        f"/scoring/applications/{app_id}", headers=admin_headers
    )
    assert response.status_code == 200


async def test_model_info_flow(e2e_client):
    """Информация о модели доступна после логина"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "info@example.com")

    response = await client.get("/scoring/model-info", headers=headers)
    assert response.status_code == 200
    assert response.json()["model_version"] == "v1.0.0"


async def test_batch_scoring_flow(e2e_client):
    """Пакетный скоринг возвращает результаты"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "batch@example.com")

    body = {"applications": [make_body(), make_body()]}
    response = await client.post("/scoring/batch", json=body, headers=headers)
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


async def test_get_missing_application(e2e_client):
    """Несуществующая заявка возвращает 404"""
    client, _ = e2e_client
    headers = await _auth_headers(client, "missing@example.com")

    response = await client.get("/scoring/applications/nope", headers=headers)
    assert response.status_code == 404


async def test_products_flow(e2e_client):
    """Сквозной путь по каталогу продуктов после старта приложения"""
    client, _ = e2e_client

    listing = await client.get("/products")
    assert listing.status_code == 200
    data = listing.json()
    assert len(data["products"]) == 5
    codes = [p["code"] for p in data["products"]]
    assert codes == ["microloan", "working_capital", "overdraft", "credit_line", "leasing"]

    detail = await client.get("/products/leasing")
    assert detail.status_code == 200
    body = detail.json()
    assert body["name"] == "Лизинг оборудования"
    assert body["product_type"] == "leasing"
    assert body["extras"]["advance_percent_min"] == 10

    missing = await client.get("/products/does-not-exist")
    assert missing.status_code == 404