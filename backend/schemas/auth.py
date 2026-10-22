from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from typing import Literal




class SUserRegister(BaseModel):
    """Схема для регистрации нового пользователя."""
    username: str
    email: EmailStr
    password: str
    password_confirm: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "john_doe",
                    "email": "john@example.com",
                    "password": "securepassword123",
                    "password_confirm": "securepassword123"
                }
            ]
        }
    )


class SUserLogin(BaseModel):
    """Схема для входа в систему."""
    email: EmailStr
    password: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "john@example.com",
                    "password": "securepassword123"
                }
            ]
        }
    )
    
    
class SUserUpdate(BaseModel):
    """Данные для частичного обновления профиля. Все поля опциональны."""
    username: str | None = Field(None, min_length=1, max_length=50)
    email: EmailStr | None = None
    avatar_id: int | None = None
    bio: str | None = Field(None, max_length=500)
    birth_date: date | None = None
    gender: Literal["male", "female"] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "username": "new_name",
                "bio": "Привет, я новый пользователь",
                "birth_date": "2000-01-01",
                "gender": "male"
            }]
        }
    )

    @model_validator(mode='after')
    def check_at_least_one_field(self):
        if all(v is None for v in self.__dict__.values()):
            raise ValueError('Не передано ни одного поля для обновления')
        return self


class SUser(BaseModel):
    """Схема для отображения информации о пользователе."""
    id: int
    username: str
    email: EmailStr
    avatar_id: int | None=None
    bio: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "username": "john_doe",
                    "email": "john@example.com",
                    "avatar_id": None,
                    "bio": None,
                    "birth_date": None,
                    "gender": None,
                    "created_at": "2024-01-01T12:00:00Z"
                }
            ]
        }
    )
    

class SUserListResponse(BaseModel):
    users: list[SUser]
    next_cursor: str | None = None
    previous_cursor: str | None = None



# ============================================



class RegisterResponse(BaseModel):
    """Схема ответа для успешной регистрации."""
    success: bool = Field(..., example=True)
    user_id: int = Field(..., example=1)
    message: str = Field(..., example="Регистрация прошла успешно")


class LoginResponse(BaseModel):
    """Схема ответа для успешного входа."""
    success: bool = Field(..., example=True)
    message: str = Field(..., example="Вы вошли в аккаунт")
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    refresh_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(..., example="bearer")


class RefreshResponse(BaseModel):
    """Схема ответа для обновления токена."""
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(..., example="bearer")


class LogoutResponse(BaseModel):
    """Схема ответа для выхода из системы."""
    success: bool = Field(..., example=True)