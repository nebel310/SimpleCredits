import pytest
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

import database
from database import Model, add_missing_columns


async def test_add_missing_columns_adds_new_nullable_columns(monkeypatch):
    """Старая таблица без новой колонки получает её при старте, данные сохраняются"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    old = MetaData()
    Table("demo_items", old, Column("id", Integer, primary_key=True), Column("name", String))
    new = MetaData()
    Table(
        "demo_items", new,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("note", String, nullable=True),
        Column("flag", Boolean, nullable=True),
    )
    async with engine.begin() as conn:
        await conn.run_sync(old.create_all)
        await conn.exec_driver_sql("INSERT INTO demo_items (id, name) VALUES (1, 'старая строка')")
    monkeypatch.setattr(Model, "metadata", new)
    async with engine.begin() as conn:
        added = await conn.run_sync(add_missing_columns)
        columns = await conn.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("demo_items")})
        row = (await conn.exec_driver_sql("SELECT name, note FROM demo_items")).first()
    assert added == ["demo_items.note", "demo_items.flag"]
    assert {"note", "flag"} <= columns
    assert row == ("старая строка", None)
    await engine.dispose()


async def test_add_missing_columns_noop_when_schema_matches():
    """Если схема уже актуальна, ничего не меняется"""
    async with database.engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
        added = await conn.run_sync(add_missing_columns)
        await conn.run_sync(Model.metadata.drop_all)
    assert added == []


async def test_add_missing_columns_refuses_not_null(monkeypatch):
    """NOT NULL колонку без значения добавить нельзя — понятная ошибка вместо битой базы"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    old = MetaData()
    Table("demo_items", old, Column("id", Integer, primary_key=True))
    new = MetaData()
    Table("demo_items", new, Column("id", Integer, primary_key=True), Column("must", String, nullable=False))
    async with engine.begin() as conn:
        await conn.run_sync(old.create_all)
    monkeypatch.setattr(Model, "metadata", new)
    with pytest.raises(RuntimeError, match="nullable"):
        async with engine.begin() as conn:
            await conn.run_sync(add_missing_columns)
    await engine.dispose()


async def test_add_missing_columns_creates_missing_indexes(monkeypatch):
    """Индекс из модели появляется и в старой таблице"""
    from sqlalchemy import Index
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    old = MetaData()
    Table("demo_items", old, Column("id", Integer, primary_key=True), Column("owner", Integer))
    new = MetaData()
    t = Table("demo_items", new, Column("id", Integer, primary_key=True), Column("owner", Integer), Column("key", String, nullable=True))
    Index("ux_demo_owner_key", t.c.owner, t.c.key, unique=True)
    async with engine.begin() as conn:
        await conn.run_sync(old.create_all)
    monkeypatch.setattr(Model, "metadata", new)
    async with engine.begin() as conn:
        added = await conn.run_sync(add_missing_columns)
        indexes = await conn.run_sync(lambda c: {i["name"] for i in inspect(c).get_indexes("demo_items")})
    assert "demo_items.ux_demo_owner_key" in added and "ux_demo_owner_key" in indexes
    await engine.dispose()
