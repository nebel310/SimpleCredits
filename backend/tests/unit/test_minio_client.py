from contextlib import asynccontextmanager

import pytest
from botocore.exceptions import ClientError

from minio.client import S3Client
from minio.exceptions import ObjectNotFoundError, StorageError


@pytest.fixture
def s3():
    """Возвращает настроенный S3Client"""
    return S3Client(
        endpoint="http://test:9000",
        access_key="key",
        secret_key="secret",
        bucket_name="test-bucket",
    )


@pytest.fixture
def patch_s3(monkeypatch):
    """Возвращает функцию подмены get_client на заданный мок"""

    def _patch(s3_client, mock_client):
        @asynccontextmanager
        async def ctx():
            yield mock_client

        monkeypatch.setattr(s3_client, "get_client", ctx)

    return _patch


def test_s3_client_init():
    """Инициализирует поля и регион по умолчанию"""
    s3 = S3Client("http://e:9000", "k", "s", "b")
    assert s3.endpoint == "http://e:9000"
    assert s3.bucket_name == "b"
    assert s3.region == "us-east-1"


def test_s3_client_get_client_returns_context():
    """Возвращает то, что создал session.create_client"""
    s3 = S3Client("http://e:9000", "k", "s", "b")
    mock_session = type("S", (), {})()
    mock_session.create_client = lambda *a, **kw: "ctx"
    s3.session = mock_session
    assert s3.get_client() == "ctx"


async def test_ensure_bucket_exists(s3, patch_s3):
    """Не создаёт бакет если head_bucket успешен"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.head_bucket = AsyncMock(return_value={})
    client.create_bucket = AsyncMock()
    patch_s3(s3, client)

    await s3.ensure_bucket()
    client.head_bucket.assert_called_once_with(Bucket="test-bucket")
    client.create_bucket.assert_not_called()


async def test_ensure_bucket_creates_on_404(s3, patch_s3):
    """Создаёт бакет при 404"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.head_bucket = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "404"}}, "HeadBucket")
    )
    client.create_bucket = AsyncMock(return_value={})
    patch_s3(s3, client)

    await s3.ensure_bucket()
    client.create_bucket.assert_called_once_with(Bucket="test-bucket")


async def test_ensure_bucket_creation_failure(s3, patch_s3):
    """Кидает StorageError если create_bucket упал"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.head_bucket = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "404"}}, "HeadBucket")
    )
    client.create_bucket = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "CreateBucket")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.ensure_bucket()


async def test_ensure_bucket_head_denied(s3, patch_s3):
    """Кидает StorageError при ошибке отличной от 404"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.head_bucket = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "HeadBucket")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.ensure_bucket()


async def test_ensure_bucket_unexpected_error(s3, patch_s3):
    """Кидает StorageError при неожиданном исключении"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.head_bucket = AsyncMock(side_effect=RuntimeError("boom"))
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.ensure_bucket()


async def test_upload_with_extension(s3, patch_s3):
    """Возвращает ключ uuid + расширение"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.put_object = AsyncMock(return_value={})
    patch_s3(s3, client)

    key = await s3.upload(b"data", "png")
    assert len(key) == 32 + 1 + 3
    assert key.endswith(".png")


async def test_upload_without_extension(s3, patch_s3):
    """Возвращает ключ без расширения"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.put_object = AsyncMock(return_value={})
    patch_s3(s3, client)

    assert len(await s3.upload(b"data")) == 32


async def test_upload_failure(s3, patch_s3):
    """Кидает StorageError при ошибке put_object"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.put_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.upload(b"data")


async def test_download_success(s3, patch_s3):
    """Возвращает байты файла"""
    from unittest.mock import AsyncMock

    body = AsyncMock()
    body.read = AsyncMock(return_value=b"file content")

    client = AsyncMock()
    client.get_object = AsyncMock(return_value={"Body": body})
    patch_s3(s3, client)

    assert await s3.download("key") == b"file content"


async def test_download_not_found(s3, patch_s3):
    """Кидает ObjectNotFoundError при NoSuchKey"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.get_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    )
    patch_s3(s3, client)

    with pytest.raises(ObjectNotFoundError):
        await s3.download("key")


async def test_download_other_error(s3, patch_s3):
    """Кидает StorageError при прочих ошибках"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.get_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.download("key")


async def test_stream_full(s3, patch_s3):
    """Отдаёт все чанки файла"""
    from unittest.mock import AsyncMock

    body = AsyncMock()
    body.read = AsyncMock(side_effect=[b"chunk1", b"chunk2", b""])

    client = AsyncMock()
    client.get_object = AsyncMock(return_value={"Body": body})
    patch_s3(s3, client)

    chunks = []
    async for chunk in s3.download_range_stream("key"):
        chunks.append(chunk)
    assert chunks == [b"chunk1", b"chunk2"]


async def test_stream_with_start(s3, patch_s3):
    """Передаёт Range bytes=start- при одном start"""
    from unittest.mock import AsyncMock

    body = AsyncMock()
    body.read = AsyncMock(side_effect=[b""])

    client = AsyncMock()
    client.get_object = AsyncMock(return_value={"Body": body})
    patch_s3(s3, client)

    async for _ in s3.download_range_stream("key", start=10):
        pass
    client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="key", Range="bytes=10-"
    )


async def test_stream_with_start_and_end(s3, patch_s3):
    """Передаёт Range bytes=start-end"""
    from unittest.mock import AsyncMock

    body = AsyncMock()
    body.read = AsyncMock(side_effect=[b""])

    client = AsyncMock()
    client.get_object = AsyncMock(return_value={"Body": body})
    patch_s3(s3, client)

    async for _ in s3.download_range_stream("key", start=0, end=100):
        pass
    client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="key", Range="bytes=0-100"
    )


async def test_stream_no_range(s3, patch_s3):
    """Не передаёт Range если start не задан"""
    from unittest.mock import AsyncMock

    body = AsyncMock()
    body.read = AsyncMock(side_effect=[b""])

    client = AsyncMock()
    client.get_object = AsyncMock(return_value={"Body": body})
    patch_s3(s3, client)

    async for _ in s3.download_range_stream("key"):
        pass
    client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="key", Range=None
    )


async def test_stream_not_found(s3, patch_s3):
    """Кидает ObjectNotFoundError при NoSuchKey"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.get_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    )
    patch_s3(s3, client)

    with pytest.raises(ObjectNotFoundError):
        async for _ in s3.download_range_stream("key"):
            pass


async def test_stream_invalid_range(s3, patch_s3):
    """Кидает StorageError при InvalidRange"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.get_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "InvalidRange"}}, "GetObject")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        async for _ in s3.download_range_stream("key"):
            pass


async def test_delete_success(s3, patch_s3):
    """Удаляет объект успешно"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.delete_object = AsyncMock(return_value={})
    patch_s3(s3, client)

    await s3.delete("key")
    client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="key")


async def test_delete_not_found(s3, patch_s3):
    """Кидает ObjectNotFoundError при NoSuchKey"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.delete_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "NoSuchKey"}}, "DeleteObject")
    )
    patch_s3(s3, client)

    with pytest.raises(ObjectNotFoundError):
        await s3.delete("key")


async def test_delete_other_error(s3, patch_s3):
    """Кидает StorageError при прочих ошибках"""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.delete_object = AsyncMock(
        side_effect=ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")
    )
    patch_s3(s3, client)

    with pytest.raises(StorageError):
        await s3.delete("key")