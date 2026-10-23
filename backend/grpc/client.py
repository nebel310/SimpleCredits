import grpc
from grpc import aio

from grpc.exceptions import (
    GrpcDeadlineExceededError,
    GrpcInvalidArgumentError,
    GrpcServiceError,
    GrpcUnavailableError,
)
from grpc.generated.simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc


class ScoringClient:
    """Асинхронный клиент ML-сервиса скоринга"""

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._channel = None
        self._stub = None

    async def start(self):
        """Открывает gRPC-канал и создаёт stub"""
        self._channel = aio.insecure_channel(f"{self.host}:{self.port}")
        self._stub = scoring_pb2_grpc.ScoringServiceStub(self._channel)

    async def close(self):
        """Закрывает gRPC-канал"""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def score_application(self, request):
        """Вызывает ScoreApplication на ML-сервисе"""
        try:
            return await self._stub.ScoreApplication(request, timeout=self.timeout)
        except aio.AioRpcError as exc:
            raise self._map_error(exc) from exc

    async def batch_score_applications(self, request):
        """Вызывает BatchScoreApplications на ML-сервисе"""
        try:
            return await self._stub.BatchScoreApplications(request, timeout=self.timeout)
        except aio.AioRpcError as exc:
            raise self._map_error(exc) from exc

    async def get_model_info(self):
        """Вызывает GetModelInfo на ML-сервисе"""
        try:
            return await self._stub.GetModelInfo(
                scoring_pb2.GetModelInfoRequest(), timeout=self.timeout
            )
        except aio.AioRpcError as exc:
            raise self._map_error(exc) from exc

    def _map_error(self, exc):
        """Конвертирует AioRpcError в доменное исключение"""
        code = exc.code()
        details = exc.details() or ""

        if code == grpc.StatusCode.UNAVAILABLE:
            return GrpcUnavailableError(f"ML-сервис недоступен: {details}")
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            return GrpcInvalidArgumentError(f"Некорректный запрос к ML-сервису: {details}")
        if code == grpc.StatusCode.DEADLINE_EXCEEDED:
            return GrpcDeadlineExceededError(f"Таймаут ML-сервиса: {details}")
        return GrpcServiceError(f"Ошибка ML-сервиса ({code}): {details}")