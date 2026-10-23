import pytest_asyncio

import database
from database import Model
from models.auth import UserOrm


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_schema():
    """Пересоздаёт схему БД перед каждым тестом"""
    async with database.engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    yield
    async with database.engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)


@pytest_asyncio.fixture
async def test_user():
    """Создаёт обычного пользователя в БД"""
    async with database.new_session() as session:
        user = UserOrm(
            username="tester",
            email="tester@test.local",
            hashed_password="fakehash",
            role="user",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def admin_user():
    """Создаёт администратора в БД"""
    async with database.new_session() as session:
        user = UserOrm(
            username="admin",
            email="admin@test.local",
            hashed_password="fakehash",
            role="admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user