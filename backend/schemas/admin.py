from pydantic import BaseModel

from schemas.applications import SApplicationDetail


class SAdminApplicationListResponse(BaseModel):
    """Список всех заявок для админа"""
    applications: list[SApplicationDetail]
    next_cursor: str | None = None
    previous_cursor: str | None = None


class SAdminStatsResponse(BaseModel):
    """Агрегированная статистика по заявкам"""
    total: int
    by_status: dict[str, int]
    by_product_type: dict[str, int]
    by_risk_grade: dict[str, int]
    avg_score: float | None = None