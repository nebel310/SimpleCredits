import os

import bcrypt as _bcrypt
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


_bcrypt_hashpw_orig = _bcrypt.hashpw


def _bcrypt_hashpw_truncated(password, salt):
    """Обрезает пароль до 72 байт как bcrypt 4.x"""
    if isinstance(password, (bytes, bytearray)) and len(password) > 72:
        password = bytes(password[:72])
    return _bcrypt_hashpw_orig(password, salt)


_bcrypt.hashpw = _bcrypt_hashpw_truncated

os.environ["SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_EXPIRE_DAYS"] = "7"

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ROOT_USER", "minioadmin")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "minioadmin")
os.environ.setdefault("MINIO_BUCKET_NAME", "test-bucket")

import database  # noqa: E402


_test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)

_test_session = async_sessionmaker(_test_engine, expire_on_commit=False)

database.engine = _test_engine
database.new_session = _test_session


@event.listens_for(_test_engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_conn, connection_record):
    """Включает PRAGMA foreign_keys для каждого нового соединения"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()