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