import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from ml_grpc.client import ScoringClient
from ml_grpc.exceptions import (
    GrpcDeadlineExceededError,
    GrpcInvalidArgumentError,
    GrpcServiceError,
    GrpcUnavailableError,
)
from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from ml_grpc.mappers import (
    proto_to_schema_batch_response,
    proto_to_schema_model_info,
    schema_to_proto_score_request,
)
from models.auth import UserOrm
from schemas.applications import (
    SBatchScoreApplicationsRequest,
    SBatchScoreApplicationsResponse,
    SModelInfoResponse,
)
from schemas.base import ErrorResponse, ValidationErrorResponse
from utils.security import get_current_user


router = APIRouter(
    prefix="/scoring",
    tags=["Скоринг (вспомогательное)"],
)


def get_scoring_client(request: Request) -> ScoringClient:
    """Возвращает gRPC-клиент скоринга из состояния приложения"""
    return request.app.state.scoring_client


def _grpc_http_exception(exc: GrpcServiceError) -> HTTPException:
    """Конвертирует доменную gRPC-ошибку в HTTPException с нужным статусом"""
    if isinstance(exc, GrpcUnavailableError):
        return HTTPException(status_code=502, detail=str(exc))
    if isinstance(exc, GrpcInvalidArgumentError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, GrpcDeadlineExceededError):
        return HTTPException(status_code=504, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


@router.post(
    "/batch",
    response_model=SBatchScoreApplicationsResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def batch_score(
    data: SBatchScoreApplicationsRequest,
    current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    """Пакетный скоринг без сохранения заявок в БД"""
    proto_apps = [
        schema_to_proto_score_request(item, uuid.uuid4().hex)
        for item in data.applications
    ]
    proto_request = scoring_pb2.BatchScoreApplicationsRequest(applications=proto_apps)

    try:
        proto_response = await client.batch_score_applications(proto_request)
    except GrpcServiceError as exc:
        raise _grpc_http_exception(exc) from exc

    return SBatchScoreApplicationsResponse(
        results=proto_to_schema_batch_response(proto_response)
    )


@router.get(
    "/model-info",
    response_model=SModelInfoResponse,
    responses={
        401: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def get_model_info(
    current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    """Информация о загруженной ML-модели"""
    try:
        proto_response = await client.get_model_info()
    except GrpcServiceError as exc:
        raise _grpc_http_exception(exc) from exc

    return proto_to_schema_model_info(proto_response)