import pytest
from sqlalchemy import select, update

import database
from models.products import ProductOrm
from repositories.products import ProductRepository, SEED_PRODUCTS


async def test_ensure_products_seeds_all():
    """Первый вызов создаёт все продукты из сида"""
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        result = await session.execute(select(ProductOrm))
        products = result.scalars().all()
    assert len(products) == len(SEED_PRODUCTS)


async def test_ensure_products_idempotent():
    """Повторный вызов не дублирует продукты"""
    await ProductRepository.ensure_products()
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        result = await session.execute(select(ProductOrm))
        products = result.scalars().all()
    assert len(products) == len(SEED_PRODUCTS)


async def test_ensure_products_preserves_custom_fields():
    """Ручные изменения не перезатираются повторным сидом"""
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        await session.execute(
            update(ProductOrm)
            .where(ProductOrm.code == "microloan")
            .values(name="Custom Name")
        )
        await session.commit()

    await ProductRepository.ensure_products()

    async with database.new_session() as session:
        result = await session.execute(
            select(ProductOrm).where(ProductOrm.code == "microloan")
        )
        product = result.scalars().first()
    assert product.name == "Custom Name"


async def test_list_active_returns_only_active():
    """list_active фильтрует по is_active"""
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        await session.execute(
            update(ProductOrm)
            .where(ProductOrm.code == "microloan")
            .values(is_active=False)
        )
        await session.commit()

    products = await ProductRepository.list_active()
    codes = [p.code for p in products]
    assert "microloan" not in codes
    assert len(codes) == len(SEED_PRODUCTS) - 1


async def test_list_active_sorted_by_display_order():
    """list_active возвращает в порядке display_order"""
    await ProductRepository.ensure_products()
    products = await ProductRepository.list_active()
    assert [p.display_order for p in products] == sorted(p.display_order for p in products)


async def test_get_by_code_found():
    """get_by_code возвращает продукт по коду"""
    await ProductRepository.ensure_products()
    product = await ProductRepository.get_by_code("microloan")
    assert product is not None
    assert product.name == "Микрозайм"


async def test_get_by_code_missing():
    """get_by_code возвращает None для несуществующего кода"""
    assert await ProductRepository.get_by_code("nope") is None

async def test_ensure_products_upgrades_old_seed_conditions_keeps_custom_name():
    """База из прошлой версии получает новые ставки и требования, ручное название остаётся"""
    from repositories.products import SEED_VERSION
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        await session.execute(
            update(ProductOrm).where(ProductOrm.code == "leasing").values(
                name="Мой лизинг", rate_min_percent=12.0, extras={"advance_percent_min": 10}
            )
        )
        await session.commit()

    await ProductRepository.ensure_products()

    async with database.new_session() as session:
        product = (await session.execute(select(ProductOrm).where(ProductOrm.code == "leasing"))).scalars().first()
    assert product.name == "Мой лизинг"
    assert product.rate_min_percent == 17.0
    assert product.extras["seed_version"] == SEED_VERSION
    assert product.extras["min_company_age_months"] == 12


async def test_seed_rates_above_key_rate_and_every_purpose_covered():
    """Ставки всех продуктов выше ключевой (14%), у каждой цели есть хотя бы один продукт"""
    from schemas.applications import FinancingPurpose
    from typing import get_args
    assert all(p["rate_min_percent"] > 14.0 for p in SEED_PRODUCTS)
    covered = {purpose for p in SEED_PRODUCTS for purpose in p["purposes"]}
    assert set(get_args(FinancingPurpose)) <= covered


async def test_seed_requirements_are_structured():
    """Требования к форме и возрасту компании заданы полями, а не только текстом"""
    for p in SEED_PRODUCTS:
        assert p["extras"]["legal_forms"]
        assert p["extras"]["min_company_age_months"] >= 0
        assert p["segment"] in ("micro", "small", "both")


async def test_every_purpose_has_product_for_each_segment():
    """И микро-, и малый бизнес могут получить продукт под любую цель"""
    from schemas.applications import FinancingPurpose
    from typing import get_args
    for segment in ("micro", "small"):
        covered = {pu for p in SEED_PRODUCTS if p["segment"] in (segment, "both") for pu in p["purposes"]}
        assert set(get_args(FinancingPurpose)) <= covered, segment
