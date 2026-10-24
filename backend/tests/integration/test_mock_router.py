import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from router.mock import router as mock_router


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    """Отключает искусственную задержку моков"""

    async def fast_delay():
        return None

    monkeypatch.setattr("router.mock._delay", fast_delay)


@pytest_asyncio.fixture
async def client():
    """HTTP-клиент с подключённым мок-роутером"""
    app = FastAPI()
    app.include_router(mock_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_egrul_valid(client):
    """GET /mock/egrul/{valid} → 200"""
    r = await client.get("/mock/egrul/7701234567")
    assert r.status_code == 200
    data = r.json()
    assert data["inn"] == "7701234567"
    assert "legal_name" in data


async def test_egrul_12_digits(client):
    """12-значный ИНН тоже валиден"""
    r = await client.get("/mock/egrul/770123456789")
    assert r.status_code == 200


async def test_egrul_invalid_inn(client):
    """GET /mock/egrul/{invalid} → 404"""
    r = await client.get("/mock/egrul/123")
    assert r.status_code == 404


async def test_egrul_fail_param(client):
    """?fail=true → 500"""
    r = await client.get("/mock/egrul/7701234567?fail=true")
    assert r.status_code == 500


async def test_fns_valid(client):
    """GET /mock/fns/{valid} → 200"""
    r = await client.get("/mock/fns/7701234567")
    assert r.status_code == 200
    assert "tax_regime" in r.json()


async def test_fns_invalid(client):
    """GET /mock/fns/{invalid} → 404"""
    r = await client.get("/mock/fns/abc")
    assert r.status_code == 404


async def test_fns_fail(client):
    """?fail=true → 500"""
    r = await client.get("/mock/fns/7701234567?fail=true")
    assert r.status_code == 500


async def test_bki_valid(client):
    """GET /mock/bki/{valid} → 200"""
    r = await client.get("/mock/bki/7701234567")
    assert r.status_code == 200
    assert "credit_score" in r.json()


async def test_bki_invalid(client):
    """GET /mock/bki/{invalid} → 404"""
    r = await client.get("/mock/bki/short")
    assert r.status_code == 404


async def test_bki_fail(client):
    """?fail=true → 500"""
    r = await client.get("/mock/bki/7701234567?fail=true")
    assert r.status_code == 500


async def test_egrul_deterministic_over_http(client):
    """Два запроса дают одинаковые числовые поля"""
    r1 = await client.get("/mock/egrul/7701234567")
    r2 = await client.get("/mock/egrul/7701234567")
    d1, d2 = r1.json(), r2.json()
    assert d1["employee_count"] == d2["employee_count"]
    assert d1["legal_name"] == d2["legal_name"]
    assert d1["ogrn"] == d2["ogrn"]


async def test_fns_deterministic_over_http(client):
    """ФНС детерминирован"""
    r1 = await client.get("/mock/fns/7701234567")
    r2 = await client.get("/mock/fns/7701234567")
    assert r1.json()["reliability_score"] == r2.json()["reliability_score"]


async def test_bki_deterministic_over_http(client):
    """БКИ детерминирован"""
    r1 = await client.get("/mock/bki/7701234567")
    r2 = await client.get("/mock/bki/7701234567")
    assert r1.json()["credit_score"] == r2.json()["credit_score"]