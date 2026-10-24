import asyncio
import random

from fastapi import APIRouter, HTTPException

from schemas.base import ErrorResponse
from schemas.mock import SBkiResponse, SEgrulResponse, SFnsResponse
from services.mock_data import generate_bki, generate_egrul, generate_fns, is_valid_inn


router = APIRouter(prefix="/mock", tags=["Мок-госуслуги"])


async def _delay() -> None:
    """Искусственная задержка 0.3–1.5 секунды для имитации госуслуг"""
    await asyncio.sleep(random.uniform(0.3, 1.5))


def _ensure_inn(inn: str) -> None:
    """Кидает 404 если формат ИНН невалиден"""
    if not is_valid_inn(inn):
        raise HTTPException(status_code=404, detail="Организация не найдена")


def _ensure_not_fail(fail: bool) -> None:
    """Симулирует сбой при fail=true"""
    if fail:
        raise HTTPException(status_code=500, detail="Имитация сбоя мок-сервиса")


@router.get(
    "/egrul/{inn}",
    response_model=SEgrulResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Организация не найдена"},
        500: {"model": ErrorResponse, "description": "Имитация сбоя"},
    },
)
async def get_egrul(inn: str, fail: bool = False):
    """Возвращает реквизиты компании из ЕГРЮЛ по ИНН"""
    _ensure_inn(inn)
    _ensure_not_fail(fail)
    await _delay()
    return generate_egrul(inn)


@router.get(
    "/fns/{inn}",
    response_model=SFnsResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_fns(inn: str, fail: bool = False):
    """Возвращает налоговые данные из ФНС по ИНН"""
    _ensure_inn(inn)
    _ensure_not_fail(fail)
    await _delay()
    return generate_fns(inn)


@router.get(
    "/bki/{inn}",
    response_model=SBkiResponse,
    responses={
        404: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def get_bki(inn: str, fail: bool = False):
    """Возвращает кредитную историю из БКИ по ИНН"""
    _ensure_inn(inn)
    _ensure_not_fail(fail)
    await _delay()
    return generate_bki(inn)