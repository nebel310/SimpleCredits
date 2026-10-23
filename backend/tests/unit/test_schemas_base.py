import pytest
from pydantic import ValidationError

from schemas.base import ErrorResponse, SuccessResponse, ValidationErrorResponse


def test_success_response_valid():
    """Создаёт валидный SuccessResponse"""
    assert SuccessResponse(detail="ok").detail == "ok"


def test_success_response_missing_detail():
    """Отклоняет SuccessResponse без detail"""
    with pytest.raises(ValidationError):
        SuccessResponse()


def test_error_response_valid():
    """Создаёт валидный ErrorResponse"""
    assert ErrorResponse(detail="err").detail == "err"


def test_validation_error_response_valid():
    """Создаёт валидный ValidationErrorResponse"""
    assert ValidationErrorResponse(detail="bad").detail == "bad"