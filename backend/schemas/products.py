from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SProductResponse(BaseModel):
    """Информация о кредитном продукте"""
    id: int
    code: str
    name: str
    description: str
    product_type: str
    segment: str
    min_amount_rub: int
    max_amount_rub: int
    min_term_months: int
    max_term_months: int
    rate_min_percent: float
    rate_max_percent: float
    purposes: list[str]
    features: list[str]
    requirements: list[str]
    extras: dict
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SProductListResponse(BaseModel):
    """Список продуктов каталога"""
    products: list[SProductResponse]