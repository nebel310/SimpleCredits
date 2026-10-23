from unittest.mock import AsyncMock

import grpc
import pytest
from grpc import aio

from ml_grpc.client import ScoringClient
from ml_grpc.exceptions import (
    GrpcDeadlineExceededError,
    GrpcInvalidArgumentError,
    GrpcServiceError,
    GrpcUnavailableError,
)
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2


def make_client():
    """Возвращает клиент без запуска канала"""
    return ScoringClient(host="ml", port=50051, timeout=5.0)


def make_aio_error(code, details="error"):
    """Создаёт AioRpcError с заданным кодом"""
    return aio.AioRpcError(
        code,
        initial_metadata=aio.Metadata(),
        trailing_metadata=aio.Metadata(),
        details=details,
    )


def test_init_stores_fields():
    """Сохраняет параметры подключения"""
    client = make_client()
    assert client.host == "ml"
    assert client.port == 50051
    assert client.timeout == 5.0
    assert client._channel is None
    assert client._stub is None


async def test_start_creates_channel(monkeypatch):
    """Создаёт канал и stub при старте"""
    from unittest.mock import AsyncMock, MagicMock

    client = make_client()

    fake_channel = MagicMock()
    fake_channel.close = AsyncMock()

    monkeypatch.setattr(
        "ml_grpc.client.aio.insecure_channel",
        lambda url: fake_channel,
    )

    await client.start()
    assert client._channel is fake_channel
    assert client._stub is not None

    await client.close()


async def test_close_without_start():
    """Не падает при закрытии без старта"""
    client = make_client()
    await client.close()


async def test_close_calls_channel_close(monkeypatch):
    """Закрывает канал и обнуляет ссылки"""
    from unittest.mock import AsyncMock, MagicMock

    client = make_client()

    fake_channel = MagicMock()
    fake_channel.close = AsyncMock()

    monkeypatch.setattr(
        "ml_grpc.client.aio.insecure_channel",
        lambda url: fake_channel,
    )

    await client.start()
    await client.close()
    fake_channel.close.assert_awaited_once()
    assert client._channel is None
    assert client._stub is None


async def test_score_application_success():
    """Возвращает ответ стаба при успехе"""
    client = make_client()
    expected = scoring_pb2.ScoreApplicationResponse(application_id="abc")
    client._stub = AsyncMock()
    client._stub.ScoreApplication = AsyncMock(return_value=expected)

    result = await client.score_application(scoring_pb2.ScoreApplicationRequest())
    assert result is expected


async def test_score_application_unavailable():
    """Кидает GrpcUnavailableError при UNAVAILABLE"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.ScoreApplication = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.UNAVAILABLE)
    )

    with pytest.raises(GrpcUnavailableError):
        await client.score_application(scoring_pb2.ScoreApplicationRequest())


async def test_score_application_invalid_argument():
    """Кидает GrpcInvalidArgumentError при INVALID_ARGUMENT"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.ScoreApplication = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.INVALID_ARGUMENT)
    )

    with pytest.raises(GrpcInvalidArgumentError):
        await client.score_application(scoring_pb2.ScoreApplicationRequest())


async def test_score_application_deadline():
    """Кидает GrpcDeadlineExceededError при DEADLINE_EXCEEDED"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.ScoreApplication = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.DEADLINE_EXCEEDED)
    )

    with pytest.raises(GrpcDeadlineExceededError):
        await client.score_application(scoring_pb2.ScoreApplicationRequest())


async def test_score_application_other_error():
    """Кидает GrpcServiceError при прочих ошибках"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.ScoreApplication = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.INTERNAL)
    )

    with pytest.raises(GrpcServiceError):
        await client.score_application(scoring_pb2.ScoreApplicationRequest())


async def test_batch_score_success():
    """Возвращает результат пакетного вызова"""
    client = make_client()
    expected = scoring_pb2.BatchScoreApplicationsResponse()
    client._stub = AsyncMock()
    client._stub.BatchScoreApplications = AsyncMock(return_value=expected)

    result = await client.batch_score_applications(
        scoring_pb2.BatchScoreApplicationsRequest()
    )
    assert result is expected


async def test_batch_score_error():
    """Кидает GrpcUnavailableError при ошибке"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.BatchScoreApplications = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.UNAVAILABLE)
    )

    with pytest.raises(GrpcUnavailableError):
        await client.batch_score_applications(
            scoring_pb2.BatchScoreApplicationsRequest()
        )


async def test_get_model_info_success():
    """Возвращает информацию о модели"""
    client = make_client()
    expected = scoring_pb2.GetModelInfoResponse(model_version="v1")
    client._stub = AsyncMock()
    client._stub.GetModelInfo = AsyncMock(return_value=expected)

    result = await client.get_model_info()
    assert result is expected


async def test_get_model_info_error():
    """Кидает GrpcServiceError при ошибке"""
    client = make_client()
    client._stub = AsyncMock()
    client._stub.GetModelInfo = AsyncMock(
        side_effect=make_aio_error(grpc.StatusCode.UNAVAILABLE)
    )

    with pytest.raises(GrpcUnavailableError):
        await client.get_model_info()


def test_map_error_returns_correct_type():
    """Возвращает нужный доменный класс для каждого кода"""
    client = make_client()
    assert isinstance(
        client._map_error(make_aio_error(grpc.StatusCode.UNAVAILABLE)),
        GrpcUnavailableError,
    )
    assert isinstance(
        client._map_error(make_aio_error(grpc.StatusCode.INVALID_ARGUMENT)),
        GrpcInvalidArgumentError,
    )
    assert isinstance(
        client._map_error(make_aio_error(grpc.StatusCode.DEADLINE_EXCEEDED)),
        GrpcDeadlineExceededError,
    )
    assert isinstance(
        client._map_error(make_aio_error(grpc.StatusCode.UNKNOWN)),
        GrpcServiceError,
    )