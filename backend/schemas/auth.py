from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from typing import Literal

from schemas.applications import SCompany, SFinancials, SCreditHistory, ensure_consistent_financials, ensure_not_future


class SUserRegister(BaseModel):
    """Схема для регистрации нового пользователя"""
    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    password_confirm: str

    @model_validator(mode="after")
    def check_passwords_match(self):
        """Пароль и подтверждение должны совпадать"""
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "john_doe",
                    "email": "john@example.com",
                    "password": "securepassword123",
                    "password_confirm": "securepassword123",
                }
            ]
        }
    )


class SUserLogin(BaseModel):
    """Схема для входа в систему"""
    email: EmailStr
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"email": "john@example.com", "password": "securepassword123"}]
        }
    )


class SUserUpdate(BaseModel):
    """Данные для частичного обновления профиля. Все поля опциональны"""
    username: str | None = Field(None, min_length=1, max_length=50)
    email: EmailStr | None = None
    avatar_id: int | None = None
    bio: str | None = Field(None, max_length=500)
    birth_date: date | None = None
    gender: Literal["male", "female"] | None = None
    company: SCompany | None = None
    financials: SFinancials | None = None
    credit_history: SCreditHistory | None = None

    @model_validator(mode="after")
    def check_at_least_one_field(self):
        """Запрещает пустой апдейт"""
        if all(v is None for v in self.__dict__.values()):
            raise ValueError("Не передано ни одного поля для обновления")
        return self

    @model_validator(mode="after")
    def check_dates(self):
        """Дата регистрации компании и отчётный период не из будущего"""
        if self.company is not None:
            ensure_not_future(self.company.registration_date, "Дата регистрации компании")
        if self.financials is not None:
            ensure_not_future(self.financials.period_end, "Отчётный период")
            ensure_consistent_financials(self.financials)
        return self


class SUser(BaseModel):
    """Схема для отображения информации о пользователе"""
    id: int
    username: str
    email: EmailStr
    role: Literal["admin", "user"]
    avatar_id: int | None = None
    bio: str | None = None
    birth_date: date | None = None
    gender: str | None = None
    created_at: datetime
    company: SCompany | None = None
    financials: SFinancials | None = None
    credit_history: SCreditHistory | None = None

    model_config = ConfigDict(from_attributes=True)


class SUserListResponse(BaseModel):
    users: list[SUser]
    next_cursor: str | None = None
    previous_cursor: str | None = None


class RegisterResponse(BaseModel):
    """Схема ответа для успешной регистрации"""
    success: bool = Field(..., example=True)
    user_id: int = Field(..., example=1)
    message: str = Field(..., example="Регистрация прошла успешно")


class LoginResponse(BaseModel):
    """Схема ответа для успешного входа"""
    success: bool = Field(..., example=True)
    message: str = Field(..., example="Вы вошли в аккаунт")
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    refresh_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(..., example="bearer")


class SRefreshRequest(BaseModel):
    """Тело запроса на продление сессии"""
    refresh_token: str


class RefreshResponse(BaseModel):
    """Схема ответа для обновления токена"""
    access_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_type: str = Field(..., example="bearer")


class LogoutResponse(BaseModel):
    """Схема ответа для выхода из системы"""
    success: bool = Field(..., example=True)


COMPANY_FIELDS = (
    "inn", "ogrn", "legal_name", "legal_form", "okved",
    "region", "registration_date", "employee_count",
)
FINANCIALS_FIELDS = (
    "annual_revenue_rub", "annual_net_profit_rub", "ebitda_rub", "total_debt_rub",
    "monthly_revenue_rub", "monthly_expenses_rub", "accounts_receivable_rub",
    "cash_balance_rub", "period_end",
)
CREDIT_HISTORY_FIELDS = (
    "active_obligations_count", "total_outstanding_rub", "monthly_debt_payments_rub",
    "max_days_past_due_12m", "has_current_past_due", "credit_utilization",
    "closed_obligations_count", "applications_last_6m",
)


def _build_company(user) -> SCompany | None:
    """Собирает SCompany из ORM если все поля заполнены"""
    if any(getattr(user, f) is None for f in COMPANY_FIELDS):
        return None
    return SCompany(**{f: getattr(user, f) for f in COMPANY_FIELDS})


def _build_financials(user) -> SFinancials | None:
    """Собирает SFinancials из ORM если все поля заполнены"""
    if any(getattr(user, f) is None for f in FINANCIALS_FIELDS):
        return None
    return SFinancials(**{f: getattr(user, f) for f in FINANCIALS_FIELDS})


def _build_credit_history(user) -> SCreditHistory | None:
    """Собирает SCreditHistory из ORM если все поля заполнены"""
    if any(getattr(user, f) is None for f in CREDIT_HISTORY_FIELDS):
        return None
    return SCreditHistory(**{f: getattr(user, f) for f in CREDIT_HISTORY_FIELDS})


def user_orm_to_schema(user) -> SUser:
    """Собирает SUser из ORM-модели с профилем компании, финансов и КИ"""
    return SUser(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        avatar_id=user.avatar_id,
        bio=user.bio,
        birth_date=user.birth_date,
        gender=user.gender,
        created_at=user.created_at,
        company=_build_company(user),
        financials=_build_financials(user),
        credit_history=_build_credit_history(user),
    )