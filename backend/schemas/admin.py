from typing import Literal

from pydantic import BaseModel, Field

from schemas.applications import SApplicationDetail


class SAdminApplicationListResponse(BaseModel):
    """Список всех заявок для админа"""
    applications: list[SApplicationDetail]
    next_cursor: str | None = None
    previous_cursor: str | None = None


class SAdminApplicationDecisionRequest(BaseModel):
    """Ручное решение банка по заявке из серой зоны"""
    decision: Literal["approve", "decline"]
    comment: str | None = Field(default=None, max_length=1000)


class SAdminStatsResponse(BaseModel):
    """Агрегированная статистика по заявкам"""
    total: int
    by_status: dict[str, int]
    by_product_type: dict[str, int]
    by_risk_grade: dict[str, int]
    avg_score: float | None = None