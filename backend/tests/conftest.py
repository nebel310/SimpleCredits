import bcrypt as _bcrypt
import os


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