from fastapi import APIRouter, Depends, HTTPException

from models.auth import UserOrm
from repositories.admin import AdminRepository
from schemas.admin import SAdminApplicationListResponse, SAdminStatsResponse
from repositories.applications import ApplicationRepository
from schemas.applications import (
    ApplicationOutcome,
    ApplicationStatus,
    SApplicationDetail,
    SBankDecisionRequest,
)
from services import bank, deal
from services.deal import DealError
from schemas.base import ErrorResponse, ValidationErrorResponse
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
    status: ApplicationStatus | None = None,
    outcome: ApplicationOutcome | None = None,
    current_user: UserOrm = Depends(require_admin),
):
    """Возвращает все заявки (только для админа). Фильтры: status, outcome (например, MANUAL_REVIEW)"""
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
            status=status,
            outcome=outcome,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SAdminApplicationListResponse(
        applications=await deal.details(applications),
        next_cursor=encode_cursor(next_id) if next_id else None,
        previous_cursor=encode_cursor(prev_id) if prev_id else None,
    )


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


@router.post(
    "/applications/{application_id}/decision",
    response_model=SApplicationDetail,
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "Заявка не на ручной проверке или нет подходящего продукта"},
    },
)
async def decide_application(
    application_id: str,
    body: SBankDecisionRequest,
    current_user: UserOrm = Depends(require_admin),
):
    """Решение банка по заявке на ручной проверке: одобрить, предложить другую сумму или отказать"""
    application = await ApplicationRepository.get_by_application_id(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    try:
        updated = await bank.decide_manual_review(application, body, decided_by=current_user.email)
    except DealError as exc:
        raise HTTPException(status_code=409, detail=exc.message)
    return await deal.detail(updated)
