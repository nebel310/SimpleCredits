import os
from typing import NoReturn

import grpc

from schemas.scoring import (
    SModelInfoResponse,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
)
from scoring.mapping import from_proto_model_info, from_proto_response, to_proto_request
from simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc


class ScoringError(Exception):
    pass


class ScoringUnavailableError(ScoringError):
    pass


class ScoringRequestError(ScoringError):
    pass


class ScoringResponseError(ScoringError):
    pass


class ScoringClient:
    def __init__(self, target: str | None = None, timeout: float | None = None):
        self.target = target or os.getenv("SCORING_GRPC_ADDR", "localhost:50051")
        self.timeout = timeout if timeout is not None else float(
            os.getenv("SCORING_TIMEOUT_SECONDS", "10")
        )

    @staticmethod
    def _raise_rpc_error(error: grpc.aio.AioRpcError) -> NoReturn:
        code = error.code()
        details = error.details() or "unknown error"
        if code in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
            raise ScoringUnavailableError(
                f"ML scoring service is unavailable: {details}"
            ) from error
        if code == grpc.StatusCode.INVALID_ARGUMENT:
            raise ScoringRequestError(details) from error
        raise ScoringResponseError(
            f"ML scoring service returned {code.name}: {details}"
        ) from error

    async def score(self, request: SScoreApplicationRequest) -> SScoreApplicationResponse:
        proto_request = to_proto_request(request)
        try:
            async with grpc.aio.insecure_channel(self.target) as channel:
                stub = scoring_pb2_grpc.ScoringServiceStub(channel)
                response = await stub.ScoreApplication(
                    proto_request,
                    timeout=self.timeout,
                )
        except grpc.aio.AioRpcError as error:
            self._raise_rpc_error(error)
        return from_proto_response(response)

    async def model_info(self) -> SModelInfoResponse:
        try:
            async with grpc.aio.insecure_channel(self.target) as channel:
                stub = scoring_pb2_grpc.ScoringServiceStub(channel)
                response = await stub.GetModelInfo(
                    scoring_pb2.GetModelInfoRequest(),
                    timeout=self.timeout,
                )
        except grpc.aio.AioRpcError as error:
            self._raise_rpc_error(error)
        return from_proto_model_info(response)


def get_scoring_client() -> ScoringClient:
    return ScoringClient()
