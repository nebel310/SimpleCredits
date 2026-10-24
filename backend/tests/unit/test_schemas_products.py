from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas.products import SProductListResponse, SProductResponse


def make_product_ns(**overrides):
    """Возвращает ORM-подобный объект продукта"""
    base = dict(
        id=1,
        code="microloan",
        name="Микрозайм",
        description="Быстрый займ",
        product_type="microloan",
        segment="micro",
        min_amount_rub=50000,
        max_amount_rub=3000000,
        min_term_months=1,
        max_term_months=24,
        rate_min_percent=18.0,
        rate_max_percent=28.0,
        purposes=["working_capital"],
        features=["Без залога"],
        requirements=["ИП от 6 месяцев"],
        extras={"express_decision": True},
        display_order=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_product_response_from_attributes():
    """Собирает SProductResponse из ORM-подобного объекта"""
    p = SProductResponse.model_validate(make_product_ns())
    assert p.code == "microloan"
    assert p.purposes == ["working_capital"]


def test_product_response_missing_field():
    """Отклоняет объект без обязательных полей"""
    with pytest.raises(ValidationError):
        SProductResponse.model_validate(SimpleNamespace(id=1))


def test_product_list_response_empty():
    """Пустой список продуктов"""
    r = SProductListResponse(products=[])
    assert r.products == []


def test_product_list_response_with_items():
    """Список из одного продукта"""
    r = SProductListResponse(products=[SProductResponse.model_validate(make_product_ns())])
    assert len(r.products) == 1