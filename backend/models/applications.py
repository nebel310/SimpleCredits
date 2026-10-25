from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Model


class ApplicationOrm(Model):
    """Модель кредитной заявки со снимком профиля и результатом скоринга"""
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(nullable=False, default="pending", server_default="pending")

    product_type: Mapped[str | None] = mapped_column(nullable=True)
    # True — продукт подобрал банк (клиент его не выбирал). Новые колонки только nullable:
    # в существующую базу они добавляются при старте (database.add_missing_columns)
    product_selected_by_system: Mapped[bool | None] = mapped_column(nullable=True)
    # Тип результата внутри статуса different: ALTERNATIVE_PRODUCT / COUNTER_OFFER / MANUAL_REVIEW
    outcome: Mapped[str | None] = mapped_column(nullable=True)
    # Условия предложения: продукт, сумма, срок, ставка, платёж (services.products.build_offer)
    offer: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Оформление: номер модельного договора и момент синтетической выдачи
    contract_number: Mapped[str | None] = mapped_column(nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_amount_rub: Mapped[int] = mapped_column(nullable=False)
    term_months: Mapped[int] = mapped_column(nullable=False)
    purpose: Mapped[str] = mapped_column(nullable=False)
    segment: Mapped[str] = mapped_column(nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    inn: Mapped[str] = mapped_column(nullable=False)
    ogrn: Mapped[str] = mapped_column(nullable=False)
    legal_name: Mapped[str] = mapped_column(nullable=False)
    legal_form: Mapped[str] = mapped_column(nullable=False)
    okved: Mapped[str] = mapped_column(nullable=False)
    region: Mapped[str] = mapped_column(nullable=False)
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    employee_count: Mapped[int] = mapped_column(nullable=False)

    annual_revenue_rub: Mapped[int] = mapped_column(nullable=False)
    annual_net_profit_rub: Mapped[int] = mapped_column(nullable=False)
    ebitda_rub: Mapped[int] = mapped_column(nullable=False)
    total_debt_rub: Mapped[int] = mapped_column(nullable=False)
    monthly_revenue_rub: Mapped[int] = mapped_column(nullable=False)
    monthly_expenses_rub: Mapped[int] = mapped_column(nullable=False)
    accounts_receivable_rub: Mapped[int] = mapped_column(nullable=False)
    cash_balance_rub: Mapped[int] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    active_obligations_count: Mapped[int] = mapped_column(nullable=False)
    total_outstanding_rub: Mapped[int] = mapped_column(nullable=False)
    monthly_debt_payments_rub: Mapped[int] = mapped_column(nullable=False)
    max_days_past_due_12m: Mapped[int] = mapped_column(nullable=False)
    has_current_past_due: Mapped[bool] = mapped_column(nullable=False)
    credit_utilization: Mapped[float] = mapped_column(nullable=False)
    closed_obligations_count: Mapped[int] = mapped_column(nullable=False)
    applications_last_6m: Mapped[int] = mapped_column(nullable=False)

    enriched_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scoring_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ApplicationEventOrm(Model):
    """Модель события по заявке для восстановления таймлайна"""
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.application_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )