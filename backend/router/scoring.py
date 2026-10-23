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
from datetime import datetime, timezone
from models.auth import UserOrm
from repositories.scoring import ScoringRepository
from schemas.base import ErrorResponse, ValidationErrorResponse
from schemas.scoring import (
    SApplicationDetail,
    SApplicationListResponse,
    SBatchScoreApplicationsRequest,
    SBatchScoreApplicationsResponse,
    SModelInfoResponse,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
    application_orm_to_schema,
)
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
    application = await ScoringRepository.create_application(current_user.id, data)

    try:
        proto_request = schema_to_proto_score_request(data, application.application_id)
        proto_response = await client.score_application(proto_request)
    except GrpcServiceError as exc:
        await ScoringRepository.mark_application_failed(application.application_id)
        raise _grpc_http_exception(exc) from exc

    response = proto_to_schema_response(proto_response)

    await ScoringRepository.save_scoring_result(
        application.application_id,
        {
            "score": response.score,
            "pd": response.pd,
            "risk_grade": response.risk_grade,
            "model_version": response.model_version,
            "scored_at": response.scored_at or datetime.now(timezone.utc),
            "decision": response.decision.decision if response.decision else None,
            "reason_codes": [rc.model_dump() for rc in response.reason_codes],
            "conditions": (
                [c.model_dump() for c in response.decision.conditions]
                if response.decision
                else []
            ),
        },
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
    """
    Пакетный скоринг без сохранения заявок в БД.
    Предназначен для внутренних вызовов и превью.
    """
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
        applications, next_id, prev_id = await ScoringRepository.get_user_applications_paginated(
            user_id=current_user.id,
            cursor_id=cursor_id,
            direction=direction,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    details = []
    for application in applications:
        result = await ScoringRepository.get_scoring_result_by_application_id(
            application.application_id
        )
        details.append(application_orm_to_schema(application, result))

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
    application = await ScoringRepository.get_application_by_application_id(application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    if application.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    result = await ScoringRepository.get_scoring_result_by_application_id(application_id)

    return application_orm_to_schema(application, result)