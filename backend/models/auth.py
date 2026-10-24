from datetime import datetime, date, timezone

from sqlalchemy import ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Model


class UserOrm(Model):
    """Модель пользователя с профилем компании, финансов и кредитной истории"""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str]
    role: Mapped[str] = mapped_column(nullable=False, default="user", server_default="user")
    avatar_id: Mapped[int | None] = mapped_column(nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    inn: Mapped[str | None] = mapped_column(nullable=True)
    ogrn: Mapped[str | None] = mapped_column(nullable=True)
    legal_name: Mapped[str | None] = mapped_column(nullable=True)
    legal_form: Mapped[str | None] = mapped_column(nullable=True)
    okved: Mapped[str | None] = mapped_column(nullable=True)
    region: Mapped[str | None] = mapped_column(nullable=True)
    registration_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(nullable=True)

    annual_revenue_rub: Mapped[int | None] = mapped_column(nullable=True)
    annual_net_profit_rub: Mapped[int | None] = mapped_column(nullable=True)
    ebitda_rub: Mapped[int | None] = mapped_column(nullable=True)
    total_debt_rub: Mapped[int | None] = mapped_column(nullable=True)
    monthly_revenue_rub: Mapped[int | None] = mapped_column(nullable=True)
    monthly_expenses_rub: Mapped[int | None] = mapped_column(nullable=True)
    accounts_receivable_rub: Mapped[int | None] = mapped_column(nullable=True)
    cash_balance_rub: Mapped[int | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    active_obligations_count: Mapped[int | None] = mapped_column(nullable=True)
    total_outstanding_rub: Mapped[int | None] = mapped_column(nullable=True)
    monthly_debt_payments_rub: Mapped[int | None] = mapped_column(nullable=True)
    max_days_past_due_12m: Mapped[int | None] = mapped_column(nullable=True)
    has_current_past_due: Mapped[bool | None] = mapped_column(nullable=True)
    credit_utilization: Mapped[float | None] = mapped_column(nullable=True)
    closed_obligations_count: Mapped[int | None] = mapped_column(nullable=True)
    applications_last_6m: Mapped[int | None] = mapped_column(nullable=True)


class RefreshTokenOrm(Model):
    """Модель refresh токена для аутентификации"""
    __tablename__ = 'refresh_tokens'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'))
    token: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class BlacklistedTokenOrm(Model):
    """Модель черного списка токенов"""
    __tablename__ = 'blacklisted_tokens'

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )