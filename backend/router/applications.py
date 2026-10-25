from fastapi import APIRouter, Depends, HTTPException, Request, status

from ml_grpc.client import ScoringClient
from ml_grpc.exceptions import (
    GrpcDeadlineExceededError,
    GrpcInvalidArgumentError,
    GrpcServiceError,
    GrpcUnavailableError,
)
from models.auth import UserOrm
from repositories.applications import ApplicationRepository
from schemas.applications import (
    SApplicationCreateRequest,
    SApplicationDetail,
    SApplicationEventResponse,
    SApplicationListResponse,
    application_orm_to_schema,
)
from schemas.base import ErrorResponse, ValidationErrorResponse
from services.application import ApplicationService
from services.exceptions import ProductMismatchError, ProfileIncompleteError
from utils.pagination import decode_cursor, encode_cursor
from utils.security import get_current_user


router = APIRouter(prefix="/applications", tags=["Заявки"])


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
    "",
    response_model=SApplicationDetail,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ValidationErrorResponse, "description": "Профиль не заполнен / ML отклонил"},
        422: {"description": "Тело не прошло валидацию или выбранный продукт не подходит под заявку"},
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        502: {"model": ErrorResponse, "description": "ML недоступен"},
        504: {"model": ErrorResponse, "description": "Таймаут ML"},
    },
)
async def create_application(
    data: SApplicationCreateRequest,
    current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    """Создаёт кредитную заявку, обогащает, скорит и возвращает детали"""
    try:
        application = await ApplicationService.create_and_process(
            current_user, data, client
        )
    except ProfileIncompleteError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProductMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except GrpcServiceError as exc:
        raise _grpc_http_exception(exc) from exc

    return application_orm_to_schema(application)


@router.get(
    "",
    response_model=SApplicationListResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse},
    },
)
async def list_applications(
    cursor: str | None = None,
    direction: str = "forward",
    limit: int = 10,
    current_user: UserOrm = Depends(get_current_user),
):
    """Список заявок текущего пользователя с курсорной пагинацией"""
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

    return SApplicationListResponse(
        applications=[application_orm_to_schema(a) for a in applications],
        next_cursor=encode_cursor(next_id) if next_id else None,
        previous_cursor=encode_cursor(prev_id) if prev_id else None,
    )


@router.get(
    "/{application_id}",
    response_model=SApplicationDetail,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_application(
    application_id: str,
    current_user: UserOrm = Depends(get_current_user),
):
    """Детали заявки с результатом скоринга"""
    application = await ApplicationRepository.get_by_application_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    return application_orm_to_schema(application)


@router.get(
    "/{application_id}/events",
    response_model=list[SApplicationEventResponse],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_application_events(
    application_id: str,
    current_user: UserOrm = Depends(get_current_user),
):
    """История событий по заявке для восстановления таймлайна"""
    application = await ApplicationRepository.get_by_application_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    if application.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    events = await ApplicationRepository.list_events(application_id)
    return [SApplicationEventResponse.model_validate(e) for e in events]