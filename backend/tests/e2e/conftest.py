import asyncio
import socket

import uvicorn

from datetime import datetime, timezone

import pytest_asyncio
from google.protobuf.timestamp_pb2 import Timestamp
from grpc import aio
from httpx import ASGITransport, AsyncClient

import database
from database import Model
from ml_grpc.client import ScoringClient
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_schema():
    """Пересоздаёт схему БД перед каждым e2e-тестом"""
    async with database.engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    yield
    async with database.engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)


def make_proto_response(application_id, decision=scoring_pb2.DECISION_APPROVE):
    """Собирает proto ScoreApplicationResponse для фейкового ML-сервиса"""
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
    """Фейковый ML-сервис для e2e-тестов"""

    def __init__(self):
        self.response_factory = lambda request: make_proto_response(request.application_id)
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
        )


@pytest_asyncio.fixture
async def e2e_client(db_schema):
    """HTTP-клиент поверх настоящего FastAPI-приложения с фейковым ML"""
    from repositories.products import ProductRepository

    server = aio.server()
    servicer = FakeScoringServicer()
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()

    scoring_client = ScoringClient(host="127.0.0.1", port=port, timeout=5.0)
    await scoring_client.start()

    from main import app
    app.state.scoring_client = scoring_client

    await ProductRepository.ensure_products()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, servicer

    await scoring_client.close()
    await server.stop(0)


def _free_port() -> int:
    """Возвращает свободный TCP-порт"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def real_server(e2e_client, monkeypatch):
    """Поднимает реальный uvicorn с main.app для WebSocket-тестов"""
    from main import app
    from minio.client import s3_client

    async def noop_ensure_bucket():
        return None

    monkeypatch.setattr(s3_client, "ensure_bucket", noop_ensure_bucket)

    _, servicer = e2e_client
    fake_client = app.state.scoring_client

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.05)

    app.state.scoring_client = fake_client

    try:
        yield f"http://127.0.0.1:{port}", servicer
    finally:
        server.should_exit = True
        await serve_task