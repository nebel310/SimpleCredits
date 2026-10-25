from fastapi import APIRouter, Depends, HTTPException

from models.auth import UserOrm
from repositories.admin import AdminRepository
from schemas.admin import (
    SAdminApplicationDecisionRequest,
    SAdminApplicationListResponse,
    SAdminStatsResponse,
)
from schemas.applications import SApplicationDetail, application_orm_to_schema
from schemas.base import ErrorResponse, ValidationErrorResponse
from services.application import ApplicationService
from services.exceptions import ManualDecisionNotAllowedError
from utils.pagination import decode_cursor, encode_cursor
from utils.security import require_admin


router = APIRouter(
    prefix="/admin",
    tags=["Администрирование"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/applications",
    response_model=SAdminApplicationListResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def list_all_applications(
    cursor: str | None = None,
    direction: str = "forward",
    limit: int = 10,
    current_user: UserOrm = Depends(require_admin),
):
    """Возвращает все заявки (только для админа)"""
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
        applications, next_id, prev_id = await AdminRepository.list_all_paginated(
            cursor_id=cursor_id,
            direction=direction,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SAdminApplicationListResponse(
        applications=[application_orm_to_schema(a) for a in applications],
        next_cursor=encode_cursor(next_id) if next_id else None,
        previous_cursor=encode_cursor(prev_id) if prev_id else None,
    )


@router.post(
    "/applications/{application_id}/decision",
    response_model=SApplicationDetail,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def decide_application(
    application_id: str,
    data: SAdminApplicationDecisionRequest,
    current_user: UserOrm = Depends(require_admin),
):
    """Применяет ручное решение банка к заявке из серой зоны"""
    try:
        application = await ApplicationService.decide_manually(
            application_id=application_id,
            decision=data.decision,
            admin_id=current_user.id,
            comment=data.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ManualDecisionNotAllowedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return application_orm_to_schema(application)


@router.get(
    "/stats/overview",
    response_model=SAdminStatsResponse,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def stats_overview(current_user: UserOrm = Depends(require_admin)):
    """Возвращает агрегированную статистику по заявкам"""
    data = await AdminRepository.stats_overview()
    return SAdminStatsResponse(**data)