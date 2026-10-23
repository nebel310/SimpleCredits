from fastapi import APIRouter, Depends, HTTPException, status

from models.auth import UserOrm
from schemas.base import ErrorResponse, ValidationErrorResponse
from schemas.scoring import (
    SModelInfoResponse,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
)
from scoring.client import (
    ScoringClient,
    ScoringError,
    ScoringRequestError,
    ScoringUnavailableError,
    get_scoring_client,
)
from utils.security import get_current_user


router = APIRouter(
    prefix="/scoring",
    tags=["Скоринг"],
)


def _http_error(error: ScoringError) -> HTTPException:
    if isinstance(error, ScoringUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        )
    if isinstance(error, ScoringRequestError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(error),
    )


@router.post(
    "/score",
    response_model=SScoreApplicationResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        422: {"model": ValidationErrorResponse, "description": "Некорректная заявка"},
        502: {"model": ErrorResponse, "description": "Ошибка ML-сервиса"},
        503: {"model": ErrorResponse, "description": "ML-сервис недоступен"},
    },
)
async def score_application(
    request: SScoreApplicationRequest,
    _current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    try:
        return await client.score(request)
    except ScoringError as error:
        raise _http_error(error) from error


@router.get(
    "/model-info",
    response_model=SModelInfoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Не авторизован"},
        502: {"model": ErrorResponse, "description": "Ошибка ML-сервиса"},
        503: {"model": ErrorResponse, "description": "ML-сервис недоступен"},
    },
)
async def get_model_info(
    _current_user: UserOrm = Depends(get_current_user),
    client: ScoringClient = Depends(get_scoring_client),
):
    try:
        return await client.model_info()
    except ScoringError as error:
        raise _http_error(error) from error
