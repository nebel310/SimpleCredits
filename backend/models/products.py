from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Model


class ProductOrm(Model):
    """Модель кредитного продукта из каталога"""
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    product_type: Mapped[str] = mapped_column(nullable=False)
    segment: Mapped[str] = mapped_column(nullable=False)
    min_amount_rub: Mapped[int] = mapped_column(nullable=False)
    max_amount_rub: Mapped[int] = mapped_column(nullable=False)
    min_term_months: Mapped[int] = mapped_column(nullable=False)
    max_term_months: Mapped[int] = mapped_column(nullable=False)
    rate_min_percent: Mapped[float] = mapped_column(nullable=False)
    rate_max_percent: Mapped[float] = mapped_column(nullable=False)
    purposes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    features: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    requirements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extras: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )