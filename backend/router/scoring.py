import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
    proto_to_schema_response,
    schema_to_proto_score_request,
)
from models.auth import UserOrm
from repositories.applications import ApplicationRepository
from schemas.applications import (
    SApplicationDetail,
    SApplicationListResponse,
    SBatchScoreApplicationsRequest,
    SBatchScoreApplicationsResponse,
    SModelInfoResponse,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
    application_orm_to_schema,
)
from schemas.base import ErrorResponse, ValidationErrorResponse
from utils.pagination import decode_cursor, encode_cursor
from utils.security import get_current_user


router = APIRouter(
    prefix="/scoring",
    tags=["Скоринг"],
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
    "/applications",
    response_model=SScoreApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ValidationErrorResponse, "description": "ML-сервис отклонил запрос"},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        502: {"model": ErrorResponse, "description": "ML-сервис недоступен"},
        504: {"model": ErrorResponse, "description": "Таймаут ML-сервиса"},
    },
)
async def create_application(
    data: SScoreApplicationRequest,
    current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    """
    Создаёт кредитную заявку, отправляет в ML-сервис и сохраняет результат скоринга.
    Возвращает полный ответ ML-сервиса вместе с application_id.
    """
    application = await ApplicationRepository.create(current_user.id, data)

    try:
        proto_request = schema_to_proto_score_request(data, application.application_id)
        proto_response = await client.score_application(proto_request)
    except GrpcServiceError as exc:
        await ApplicationRepository.mark_failed(application.application_id, str(exc))
        raise _grpc_http_exception(exc) from exc

    response = proto_to_schema_response(proto_response)

    await ApplicationRepository.update_scoring(
        application.application_id,
        scoring_result=response.model_dump(mode="json"),
        status="scored",
    )

    return response


@router.post(
    "/batch",
    response_model=SBatchScoreApplicationsResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        502: {"model": ErrorResponse, "description": "ML-сервис недоступен"},
        504: {"model": ErrorResponse, "description": "Таймаут ML-сервиса"},
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
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        502: {"model": ErrorResponse, "description": "ML-сервис недоступен"},
        504: {"model": ErrorResponse, "description": "Таймаут ML-сервиса"},
    },
)
async def get_model_info(
    current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    """Возвращает информацию о загруженной ML-модели"""
    try:
        proto_response = await client.get_model_info()
    except GrpcServiceError as exc:
        raise _grpc_http_exception(exc) from exc

    return proto_to_schema_model_info(proto_response)


@router.get(
    "/applications",
    response_model=SApplicationListResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
    },
)
async def list_applications(
    cursor: str | None = None,
    direction: str = "forward",
    limit: int = 10,
    current_user: UserOrm = Depends(get_current_user),
):
    """Возвращает список заявок текущего пользователя с курсорной пагинацией"""
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Лимит должен быть от 1 до 50")
    if direction not in ("forward", "backward"):
        raise HTTPException(status_code=400, detail="Недопустимое направление")

    cursor_id = None
    if cursor:
        cursor_id = decode_cursor(cursor)
        if cursor_id is None:
            raise HTTPException(status_code=400, detail="Некорректный курсор")

    try:
        applications, next_id, prev_id = await ApplicationRepository.get_user_applications_paginated(
            user_id=current_user.id,
            cursor_id=cursor_id,
            direction=direction,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    details = [application_orm_to_schema(a) for a in applications]

    return SApplicationListResponse(
        applications=details,
        next_cursor=encode_cursor(next_id) if next_id else None,
        previous_cursor=encode_cursor(prev_id) if prev_id else None,
    )


@router.get(
    "/applications/{application_id}",
    response_model=SApplicationDetail,
    responses={
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        403: {"model": ErrorResponse, "description": "Нет доступа к заявке"},
        404: {"model": ErrorResponse, "description": "Заявка не найдена"},
    },
)
async def get_application(
    application_id: str,
    current_user: UserOrm = Depends(get_current_user),
):
    """Возвращает заявку и результат её скоринга по application_id"""
    application = await ApplicationRepository.get_by_application_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if application.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    return application_orm_to_schema(application)