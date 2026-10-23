from datetime import datetime, timezone

import grpc
import pytest
import pytest_asyncio
from fastapi import FastAPI
from google.protobuf.timestamp_pb2 import Timestamp
from grpc import aio
from httpx import ASGITransport, AsyncClient

from ml_grpc.client import ScoringClient
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc
from router.scoring import router as scoring_router
from utils.security import get_current_user


def make_response(
    application_id,
    decision=scoring_pb2.DECISION_APPROVE,
    risk_grade=scoring_pb2.RISK_GRADE_B,
):
    """Собирает proto ScoreApplicationResponse"""
    ts = Timestamp()
    ts.FromDatetime(datetime(2026, 3, 15, 10, 0, 1, tzinfo=timezone.utc))
    return scoring_pb2.ScoreApplicationResponse(
        application_id=application_id,
        score=712,
        pd=0.0421,
        risk_grade=risk_grade,
        reason_codes=[
            scoring_pb2.ReasonCode(
                code="RC001",
                description="Хорошая история",
                feature="max_days_past_due_12m",
                impact=scoring_pb2.REASON_IMPACT_POSITIVE,
                contribution=-0.12,
            )
        ],
        model_version="v1.0.0",
        scored_at=ts,
        decision=scoring_pb2.DecisionResult(decision=decision),
    )


class FakeScoringServicer(scoring_pb2_grpc.ScoringServiceServicer):
    """Фейковый ML-сервис для интеграционных тестов"""

    def __init__(self):
        self.response_factory = lambda request: make_response(request.application_id)
        self.score_error = None
        self.batch_error = None
        self.info_error = None

    async def ScoreApplication(self, request, context):
        """Возвращает настроенный ответ или ошибку"""
        if self.score_error:
            await context.abort(*self.score_error)
        return self.response_factory(request)

    async def BatchScoreApplications(self, request, context):
        """Возвращает пакет ответов или ошибку"""
        if self.batch_error:
            await context.abort(*self.batch_error)
        results = [self.response_factory(app) for app in request.applications]
        return scoring_pb2.BatchScoreApplicationsResponse(results=results)

    async def GetModelInfo(self, request, context):
        """Возвращает фиксированную информацию о модели"""
        if self.info_error:
            await context.abort(*self.info_error)
        return scoring_pb2.GetModelInfoResponse(
            model_version="v1.0.0",
            model_type="logistic_regression",
            features=["a", "b"],
            metrics={"auc": 0.82},
        )


@pytest_asyncio.fixture
async def fake_grpc_server():
    """Поднимает in-process gRPC-сервер с фейковым ML-сервисом"""
    server = aio.server()
    servicer = FakeScoringServicer()
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    yield server, port, servicer
    await server.stop(0)


@pytest_asyncio.fixture
async def scoring_client(fake_grpc_server):
    """Реальный ScoringClient поверх in-process сервера"""
    _, port, _ = fake_grpc_server
    client = ScoringClient(host="127.0.0.1", port=port, timeout=5.0)
    await client.start()
    yield client
    await client.close()


def _build_app(scoring_client, current_user=None):
    """Собирает FastAPI-приложение с роутером скоринга"""
    app = FastAPI()
    app.include_router(scoring_router)
    app.state.scoring_client = scoring_client
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest_asyncio.fixture
async def client(scoring_client, test_user):
    """Авторизованный клиент от лица test_user"""
    app = _build_app(scoring_client, test_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_client(scoring_client, admin_user):
    """Авторизованный клиент от лица admin_user"""
    app = _build_app(scoring_client, admin_user)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def unauth_client(scoring_client):
    """Клиент без переопределения авторизации"""
    app = _build_app(scoring_client)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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


async def test_create_application_success(client):
    """Возвращает 201 с application_id и результатом скоринга"""
    response = await client.post("/scoring/applications", json=make_body())
    assert response.status_code == 201
    data = response.json()
    assert data["application_id"]
    assert data["score"] == 712
    assert data["risk_grade"] == "B"
    assert data["decision"]["decision"] == "approve"


async def test_create_application_ml_unavailable(client, fake_grpc_server):
    """При UNAVAILABLE возвращает 502"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "down")

    response = await client.post("/scoring/applications", json=make_body())
    assert response.status_code == 502


async def test_create_application_ml_invalid(client, fake_grpc_server):
    """При INVALID_ARGUMENT возвращает 400"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.INVALID_ARGUMENT, "bad")

    response = await client.post("/scoring/applications", json=make_body())
    assert response.status_code == 400


async def test_create_application_ml_deadline(client, fake_grpc_server):
    """При DEADLINE_EXCEEDED возвращает 504"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.DEADLINE_EXCEEDED, "slow")

    response = await client.post("/scoring/applications", json=make_body())
    assert response.status_code == 504


async def test_create_application_invalid_body(client):
    """Возвращает 422 при невалидном теле"""
    response = await client.post("/scoring/applications", json={})
    assert response.status_code == 422


async def test_create_application_unauthorized(unauth_client):
    """Возвращает 401 без токена"""
    response = await unauth_client.post("/scoring/applications", json=make_body())
    assert response.status_code == 401


async def test_batch_success(client):
    """Batch возвращает результаты"""
    body = {"applications": [make_body(), make_body()]}
    response = await client.post("/scoring/batch", json=body)
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


async def test_batch_ml_error(client, fake_grpc_server):
    """Batch при ошибке ML возвращает 502"""
    _, _, servicer = fake_grpc_server
    servicer.batch_error = (grpc.StatusCode.UNAVAILABLE, "down")

    response = await client.post("/scoring/batch", json={"applications": [make_body()]})
    assert response.status_code == 502


async def test_model_info_success(client):
    """Возвращает информацию о модели"""
    response = await client.get("/scoring/model-info")
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == "v1.0.0"
    assert data["metrics"]["auc"] == pytest.approx(0.82)


async def test_model_info_ml_error(client, fake_grpc_server):
    """При ошибке ML возвращает 502"""
    _, _, servicer = fake_grpc_server
    servicer.info_error = (grpc.StatusCode.UNAVAILABLE, "down")

    response = await client.get("/scoring/model-info")
    assert response.status_code == 502


async def test_list_applications_empty(client):
    """Пустой список заявок"""
    response = await client.get("/scoring/applications")
    assert response.status_code == 200
    assert response.json()["applications"] == []


async def test_list_applications_with_items(client):
    """Список содержит созданные заявки"""
    await client.post("/scoring/applications", json=make_body())
    await client.post("/scoring/applications", json=make_body())

    response = await client.get("/scoring/applications")
    assert response.status_code == 200
    assert len(response.json()["applications"]) == 2


async def test_list_applications_invalid_limit(client):
    """Возвращает 400 при невалидном лимите"""
    response = await client.get("/scoring/applications?limit=0")
    assert response.status_code == 400


async def test_list_applications_invalid_direction(client):
    """Возвращает 400 при невалидном направлении"""
    response = await client.get("/scoring/applications?direction=unknown")
    assert response.status_code == 400


async def test_list_applications_invalid_cursor(client):
    """Возвращает 400 при невалидном курсоре"""
    response = await client.get("/scoring/applications?cursor=!!!")
    assert response.status_code == 400


async def test_get_application_own(client):
    """Своя заявка с результатом доступна"""
    create = await client.post("/scoring/applications", json=make_body())
    app_id = create.json()["application_id"]

    response = await client.get(f"/scoring/applications/{app_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["application_id"] == app_id
    assert data["scoring_result"]["score"] == 712


async def test_get_application_missing(client):
    """Несуществующая заявка → 404"""
    response = await client.get("/scoring/applications/nope")
    assert response.status_code == 404


async def test_get_application_other_user_forbidden(client, admin_client):
    """Обычный пользователь не видит чужую заявку"""
    await admin_client.post("/scoring/applications", json=make_body())
    admin_apps = await admin_client.get("/scoring/applications")
    admin_app_id = admin_apps.json()["applications"][0]["application_id"]

    response = await client.get(f"/scoring/applications/{admin_app_id}")
    assert response.status_code == 403


async def test_get_application_admin_sees_others(client, admin_client):
    """Админ видит чужую заявку"""
    await client.post("/scoring/applications", json=make_body())
    apps = await client.get("/scoring/applications")
    app_id = apps.json()["applications"][0]["application_id"]

    response = await admin_client.get(f"/scoring/applications/{app_id}")
    assert response.status_code == 200