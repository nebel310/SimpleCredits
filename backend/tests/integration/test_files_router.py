"""Файлы: доступ только владельцу и админу, Range, безопасное имя, лимиты загрузки"""
from types import SimpleNamespace

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from minio.exceptions import ObjectNotFoundError
from repositories.files import FileRepository
from router.files import router as files_router
from utils.security import get_current_user

OWNER = SimpleNamespace(id=1, email="owner@test.local", role="user")
STRANGER = SimpleNamespace(id=2, email="stranger@test.local", role="user")
ADMIN = SimpleNamespace(id=3, email="admin@test.local", role="admin")
CONTENT = b"0123456789abcdefghij"


@pytest_asyncio.fixture
def storage(monkeypatch):
    """Подменяет репозиторий файлов: один файл id=7 владельца OWNER"""
    state = {"deleted": []}
    meta = SimpleNamespace(
        id=7, object_key="k.pdf", original_name='отчёт"\r\nX-Evil: 1.pdf', size=len(CONTENT),
        uploaded_by=OWNER.id, content_type="application/pdf", extension="pdf",
        created_at="2026-10-25T10:00:00Z",
    )

    async def info(file_id):
        if file_id != 7:
            raise ObjectNotFoundError("нет")
        return meta

    async def stream(file_id, start=None, end=None):
        data = CONTENT if start is None else CONTENT[start:end + 1]
        yield data

    async def delete(file_id):
        state["deleted"].append(file_id)

    monkeypatch.setattr(FileRepository, "get_file_info_by_id", info)
    monkeypatch.setattr(FileRepository, "stream_file_range", stream)
    monkeypatch.setattr(FileRepository, "delete_file_by_id", delete)
    return state


def _client(user):
    app = FastAPI()
    app.include_router(files_router)
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_owner_downloads_and_range_works(storage):
    async with _client(OWNER) as c:
        full = await c.get("/files/7")
        part = await c.get("/files/7", headers={"Range": "bytes=0-9"})
    assert full.status_code == 200 and full.content == CONTENT
    assert part.status_code == 206 and part.content == CONTENT[:10]
    assert part.headers["content-range"] == f"bytes 0-9/{len(CONTENT)}"


async def test_filename_cannot_inject_headers(storage):
    """Перевод строки и кавычка в имени не создают новый заголовок; кириллица не роняет ответ"""
    async with _client(OWNER) as c:
        r = await c.get("/files/7")
    assert r.status_code == 200
    assert "x-evil" not in r.headers
    cd = r.headers["content-disposition"]
    assert "\r" not in cd and "\n" not in cd
    assert "filename*=UTF-8''" in cd and "%D0%BE%D1%82%D1%87%D1%91%D1%82" in cd


async def test_stranger_gets_404_everywhere(storage):
    async with _client(STRANGER) as c:
        assert (await c.get("/files/7")).status_code == 404
        assert (await c.get("/files/7/info")).status_code == 404
        assert (await c.delete("/files/7")).status_code == 404
    assert storage["deleted"] == []


async def test_admin_can_access(storage):
    async with _client(ADMIN) as c:
        assert (await c.get("/files/7/info")).status_code == 200
        assert (await c.delete("/files/7")).status_code == 200
    assert storage["deleted"] == [7]


async def test_single_download_route():
    paths = [r.path for r in files_router.routes if "GET" in getattr(r, "methods", set())]
    assert paths.count("/files/{file_id}") == 1


async def test_upload_rejects_empty_and_too_big(monkeypatch):
    import router.files as files_module
    monkeypatch.setattr(files_module, "MAX_UPLOAD_BYTES", 10)
    async with _client(OWNER) as c:
        empty = await c.post("/files/", files={"file": ("a.pdf", b"", "application/pdf")})
        big = await c.post("/files/", files={"file": ("a.pdf", b"x" * 11, "application/pdf")})
    assert empty.status_code == 400
    assert big.status_code == 413
