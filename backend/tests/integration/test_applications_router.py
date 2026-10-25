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
from router.applications import router as applications_router
from utils.security import get_current_user


def make_proto_response(application_id, decision=scoring_pb2.DECISION_APPROVE):
    """Собирает proto ScoreApplicationResponse"""
    ts = Timestamp()
    ts.FromDatetime(datetime(2026, 3, 15, 10, 0, 1, tzinfo=timezone.utc))
    return scoring_pb2.ScoreApplicationResponse(
        application_id=application_id,
        score=712,
        pd=0.0421,
        risk_grade=scoring_pb2.RISK_GRADE_B,
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
    """Фейковый ML-сервис"""

    def __init__(self):
        self.response_factory = lambda r: make_proto_response(r.application_id)
        self.score_error = None

    async def ScoreApplication(self, request, context):
        if self.score_error:
            await context.abort(*self.score_error)
        return self.response_factory(request)


@pytest_asyncio.fixture
async def fake_grpc_server():
    """In-process gRPC-сервер"""
    server = aio.server()
    servicer = FakeScoringServicer()
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    yield server, port, servicer
    await server.stop(0)


@pytest_asyncio.fixture
async def scoring_client(fake_grpc_server):
    _, port, _ = fake_grpc_server
    client = ScoringClient(host="127.0.0.1", port=port, timeout=5.0)
    await client.start()
    yield client
    await client.close()


def _build_app(scoring_client, current_user=None):
    app = FastAPI()
    app.include_router(applications_router)
    app.state.scoring_client = scoring_client
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return app


@pytest_asyncio.fixture
async def client(scoring_client, test_user):
    app = _build_app(scoring_client, test_user)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def unauth_client(scoring_client):
    app = _build_app(scoring_client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def user_with_profile(test_user):
    """Пользователь с полным профилем"""
    import database
    async with database.new_session() as session:
        user = await session.get(type(test_user), test_user.id)
        user.inn = "7701234567"
        user.ogrn = "1027700132195"
        user.legal_name = "ООО Ромашка"
        user.legal_form = "llc"
        user.okved = "62.01"
        user.region = "Москва"
        user.registration_date = datetime(2018, 4, 12)
        user.employee_count = 25
        user.annual_revenue_rub = 42000000
        user.annual_net_profit_rub = 6500000
        user.ebitda_rub = 8200000
        user.total_debt_rub = 3000000
        user.monthly_revenue_rub = 3500000
        user.monthly_expenses_rub = 2800000
        user.accounts_receivable_rub = 1200000
        user.cash_balance_rub = 900000
        user.period_end = datetime(2025, 12, 31)
        user.active_obligations_count = 2
        user.total_outstanding_rub = 3000000
        user.monthly_debt_payments_rub = 120000
        user.max_days_past_due_12m = 0
        user.has_current_past_due = False
        user.credit_utilization = 0.35
        user.closed_obligations_count = 4
        user.applications_last_6m = 1
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def auth_client(scoring_client, user_with_profile):
    """Клиент от лица пользователя с профилем"""
    app = _build_app(scoring_client, user_with_profile)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def make_body(product_type: str | None = "term_loan"):
    body = {
        "requested_amount_rub": 1500000,
        "term_months": 24,
        "purpose": "equipment",
        "segment": "small",
        "consents": {
            "personal_data_processing": True,
            "credit_history_request": True,
            "version": "2026-10-25",
        },
    }
    if product_type is not None:
        body["product_type"] = product_type
    return body


async def test_create_confirmed(auth_client):
    """approve + product_type → confirmed"""
    r = await auth_client.post("/applications", json=make_body("term_loan"))
    assert r.status_code == 201
    assert r.json()["status"] == "confirmed"
    assert r.json()["scoring_result"]["score"] == 712
    assert r.json()["enriched_data"]["egrul"] is not None


async def test_create_different_no_product_type(auth_client):
    """approve без product_type → different"""
    r = await auth_client.post("/applications", json=make_body(None))
    assert r.status_code == 201
    assert r.json()["status"] == "different"


async def test_create_different_conditions(auth_client, fake_grpc_server):
    """approve_with_conditions → different"""
    _, _, servicer = fake_grpc_server
    servicer.response_factory = lambda req: make_proto_response(
        req.application_id, scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS
    )
    r = await auth_client.post("/applications", json=make_body())
    assert r.json()["status"] == "different"


async def test_create_different_manual_review(auth_client, fake_grpc_server):
    """manual_review → different"""
    _, _, servicer = fake_grpc_server
    servicer.response_factory = lambda req: make_proto_response(
        req.application_id, scoring_pb2.DECISION_MANUAL_REVIEW
    )
    r = await auth_client.post("/applications", json=make_body())
    assert r.json()["status"] == "different"


async def test_create_declined(auth_client, fake_grpc_server):
    """decline → declined"""
    _, _, servicer = fake_grpc_server
    servicer.response_factory = lambda req: make_proto_response(
        req.application_id, scoring_pb2.DECISION_DECLINE
    )
    r = await auth_client.post("/applications", json=make_body())
    assert r.json()["status"] == "declined"


async def test_create_ml_down_returns_502(auth_client, fake_grpc_server):
    """ML UNAVAILABLE → 502, статус failed"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.UNAVAILABLE, "down")
    r = await auth_client.post("/applications", json=make_body())
    assert r.status_code == 502

    async with __import__("database").new_session() as session:
        from sqlalchemy import select
        from models.applications import ApplicationOrm
        apps = (await session.execute(select(ApplicationOrm))).scalars().all()
    assert apps[0].status == "failed"


async def test_create_ml_invalid_returns_400(auth_client, fake_grpc_server):
    """ML INVALID_ARGUMENT → 400"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.INVALID_ARGUMENT, "bad")
    r = await auth_client.post("/applications", json=make_body())
    assert r.status_code == 400


async def test_create_ml_deadline_returns_504(auth_client, fake_grpc_server):
    """ML DEADLINE → 504"""
    _, _, servicer = fake_grpc_server
    servicer.score_error = (grpc.StatusCode.DEADLINE_EXCEEDED, "slow")
    r = await auth_client.post("/applications", json=make_body())
    assert r.status_code == 504


async def test_create_invalid_body(auth_client):
    """Невалидное тело → 422"""
    r = await auth_client.post("/applications", json={})
    assert r.status_code == 422


async def test_create_requires_consents(auth_client):
    """Без согласий → 422"""
    body = make_body()
    body.pop("consents")
    r = await auth_client.post("/applications", json=body)
    assert r.status_code == 422


async def test_create_rejects_partial_consents(auth_client):
    """Если одно из согласий не предоставлено → 422"""
    body = make_body()
    body["consents"]["credit_history_request"] = False
    r = await auth_client.post("/applications", json=body)
    assert r.status_code == 422


async def test_create_persists_consents_with_timestamp(auth_client):
    """Сохраняет согласия и серверное время принятия"""
    r = await auth_client.post("/applications", json=make_body())
    assert r.status_code == 201
    consents = r.json()["consents"]
    assert consents["personal_data_processing"] is True
    assert consents["credit_history_request"] is True
    assert consents["version"] == "2026-10-25"
    assert consents["accepted_at"]


async def test_create_unauthorized(unauth_client):
    """Без токена → 401"""
    r = await unauth_client.post("/applications", json=make_body())
    assert r.status_code == 401


async def test_create_profile_incomplete(client, test_user):
    """Профиль неполный и в теле нет полей → 400"""
    r = await client.post("/applications", json=make_body())
    assert r.status_code == 400
    assert "Профиль" in r.json()["detail"]


async def test_create_profile_via_body(client, test_user):
    """Профиль передаётся в теле → 201 и сохраняется в профиль"""
    body = {
        **make_body(),
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
    r = await client.post("/applications", json=body)
    assert r.status_code == 201
    assert r.json()["status"] == "confirmed"


async def test_list_empty(auth_client):
    """Пустой список"""
    r = await auth_client.get("/applications")
    assert r.status_code == 200
    assert r.json()["applications"] == []


async def test_list_with_items(auth_client):
    """Список с двумя заявками"""
    await auth_client.post("/applications", json=make_body())
    await auth_client.post("/applications", json=make_body())
    r = await auth_client.get("/applications")
    assert len(r.json()["applications"]) == 2


async def test_list_invalid_limit(auth_client):
    r = await auth_client.get("/applications?limit=0")
    assert r.status_code == 400


async def test_list_invalid_direction(auth_client):
    r = await auth_client.get("/applications?direction=unknown")
    assert r.status_code == 400


async def test_list_invalid_cursor(auth_client):
    r = await auth_client.get("/applications?cursor=!!!")
    assert r.status_code == 400


async def test_get_own(auth_client):
    """Своя заявка доступна"""
    create = await auth_client.post("/applications", json=make_body())
    app_id = create.json()["application_id"]
    r = await auth_client.get(f"/applications/{app_id}")
    assert r.status_code == 200
    assert r.json()["scoring_result"]["score"] == 712


async def test_get_missing(auth_client):
    r = await auth_client.get("/applications/nope")
    assert r.status_code == 404


async def test_events_populated(auth_client):
    """После создания заявки есть события created, enriched, scored, status_changed"""
    create = await auth_client.post("/applications", json=make_body())
    app_id = create.json()["application_id"]
    r = await auth_client.get(f"/applications/{app_id}/events")
    assert r.status_code == 200
    types = [e["event_type"] for e in r.json()]
    assert "created" in types
    assert "enriched" in types
    assert "scored" in types
    assert "status_changed" in types


async def test_events_missing(auth_client):
    r = await auth_client.get("/applications/nope/events")
    assert r.status_code == 404