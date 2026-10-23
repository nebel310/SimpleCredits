from pydantic import BaseModel, Field




class SuccessResponse(BaseModel):
    """Схема ответа для полоэительных неинформативных ответов"""
    detail: str = Field(..., example="Сообщение об успешном ответе")


class ErrorResponse(BaseModel):
    """Схема ответа для ошибок"""
    detail: str = Field(..., example="Сообщение об ошибке")


class ValidationErrorResponse(BaseModel):
    """Схема ответа для ошибок валидации"""
    detail: str = Field(..., example="Пользователь с таким email уже существует")