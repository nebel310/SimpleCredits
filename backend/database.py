import os

from dotenv import load_dotenv
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


load_dotenv()

engine = create_async_engine(os.getenv('DATABASE_URL'))

new_session = async_sessionmaker(engine, expire_on_commit=False)


class Model(DeclarativeBase):
    """Базовый класс для всех моделей базы данных"""
    pass


def add_missing_columns(sync_conn) -> list[str]:
    """
    Добавляет в уже существующие таблицы колонки, которые появились в моделях позже.

    create_all создаёт только новые таблицы и не трогает старые. Без этого база,
    созданная прошлой версией бэкенда (volume в docker compose), падала бы на новых полях.
    Добавляем только nullable-колонки без значения по умолчанию — это безопасно для
    любых данных. Возвращает список добавленных колонок вида "таблица.колонка".
    """
    insp = inspect(sync_conn)
    existing_tables = set(insp.get_table_names())
    quote = sync_conn.dialect.identifier_preparer.quote
    added: list[str] = []
    for table in Model.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for column in table.columns:
            if column.name in have:
                continue
            if not column.nullable:
                raise RuntimeError(
                    f"Колонку {table.name}.{column.name} нельзя добавить автоматически: "
                    "новые колонки в существующих таблицах должны быть nullable"
                )
            column_type = column.type.compile(dialect=sync_conn.dialect)
            sync_conn.exec_driver_sql(
                f"ALTER TABLE {quote(table.name)} ADD COLUMN {quote(column.name)} {column_type}"
            )
            added.append(f"{table.name}.{column.name}")
    return added


async def create_tables():
    """Создает таблицы и добавляет недостающие колонки в существующие"""
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.create_all)
        added = await conn.run_sync(add_missing_columns)
    if added:
        print(f"Добавлены колонки: {', '.join(added)}")


async def delete_tables():
    """Удаляет все таблицы из базы данных (только для тестов)"""
    async with engine.begin() as conn:
        await conn.run_sync(Model.metadata.drop_all)


import models.auth  # noqa: E402, F401
import models.files  # noqa: E402, F401
import models.products  # noqa: E402, F401
import models.applications  # noqa: E402, F401