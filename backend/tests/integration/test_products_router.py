import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

import database
from models.products import ProductOrm
from repositories.products import ProductRepository
from router.products import router as products_router


@pytest_asyncio.fixture
async def client():
    """HTTP-клиент с роутером продуктов"""
    app = FastAPI()
    app.include_router(products_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_list_products_empty(client):
    """Пустой каталог → пустой список"""
    response = await client.get("/products")
    assert response.status_code == 200
    assert response.json()["products"] == []


async def test_list_products_returns_active(client):
    """Каталог возвращает активные продукты в порядке display_order"""
    await ProductRepository.ensure_products()
    response = await client.get("/products")
    assert response.status_code == 200
    data = response.json()["products"]
    assert len(data) == 5
    assert data[0]["code"] == "microloan"
    assert all(p["display_order"] for p in data)


async def test_list_products_skips_inactive(client):
    """Каталог не показывает неактивные продукты"""
    await ProductRepository.ensure_products()
    async with database.new_session() as session:
        await session.execute(
            update(ProductOrm).where(ProductOrm.code == "microloan").values(is_active=False)
        )
        await session.commit()
    response = await client.get("/products")
    assert response.status_code == 200
    codes = [p["code"] for p in response.json()["products"]]
    assert "microloan" not in codes


async def test_get_product_by_code(client):
    """GET /products/{code} возвращает детали"""
    await ProductRepository.ensure_products()
    response = await client.get("/products/overdraft")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == "overdraft"
    assert data["product_type"] == "overdraft"


async def test_get_product_missing(client):
    """GET /products/{missing} → 404"""
    response = await client.get("/products/nope")
    assert response.status_code == 404