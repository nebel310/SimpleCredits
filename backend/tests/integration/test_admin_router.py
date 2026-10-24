import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import database
from models.applications import ApplicationOrm
from router.admin import router as admin_router
from utils.security import require_admin


def _fake_admin():
    """Возвращает объект пользователя-админа"""
    from types import SimpleNamespace
    return SimpleNamespace(id=999, email="admin@test.local", role="admin")


def _fake_user():
    """Возвращает объект обычного пользователя"""
    from types import SimpleNamespace
    return SimpleNamespace(id=1000, email="user@test.local", role="user")


def _build_app_as(user):
    """Собирает FastAPI-приложение с переопределённым require_admin"""
    app = FastAPI()
    app.include_router(admin_router)
    if user.role == "admin":
        app.dependency_overrides[require_admin] = lambda: user
    else:
        from fastapi import HTTPException
        def _deny():
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        app.dependency_overrides[require_admin] = _deny
    return app


@pytest_asyncio.fixture
async def admin_client():
    app = _build_app_as(_fake_admin())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def user_client():
    app = _build_app_as(_fake_user())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _insert_application(user_id: int, status: str) -> None:
    """Вставляет заявку в БД от имени существующего пользователя"""
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    async with database.new_session() as session:
        session.add(
            ApplicationOrm(
                application_id=f"app-{uuid.uuid4().hex}",
                user_id=user_id,
                status=status,
                product_type="term_loan",
                requested_amount_rub=100000,
                term_months=12,
                purpose="other",
                segment="micro",
                submitted_at=now,
                inn="7701234567",
                ogrn="1027700132195",
                legal_name="ООО Тест",
                legal_form="llc",
                okved="62.01",
                region="Москва",
                registration_date=now,
                employee_count=1,
                annual_revenue_rub=0,
                annual_net_profit_rub=0,
                ebitda_rub=0,
                total_debt_rub=0,
                monthly_revenue_rub=0,
                monthly_expenses_rub=0,
                accounts_receivable_rub=0,
                cash_balance_rub=0,
                period_end=now,
                active_obligations_count=0,
                total_outstanding_rub=0,
                monthly_debt_payments_rub=0,
                max_days_past_due_12m=0,
                has_current_past_due=False,
                credit_utilization=0.0,
                closed_obligations_count=0,
                applications_last_6m=0,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def test_admin_applications_ok(admin_client, test_user):
    """Админ получает список всех заявок"""
    await _insert_application(test_user.id, "confirmed")
    await _insert_application(test_user.id, "declined")

    r = await admin_client.get("/admin/applications")
    assert r.status_code == 200
    assert len(r.json()["applications"]) == 2


async def test_admin_applications_empty(admin_client):
    """Пустая БД → пустой список"""
    r = await admin_client.get("/admin/applications")
    assert r.status_code == 200
    assert r.json()["applications"] == []


async def test_admin_applications_user_forbidden(user_client):
    """Обычный пользователь → 403"""
    r = await user_client.get("/admin/applications")
    assert r.status_code == 403


async def test_admin_applications_invalid_limit(admin_client):
    """limit=0 → 400"""
    r = await admin_client.get("/admin/applications?limit=0")
    assert r.status_code == 400


async def test_admin_applications_invalid_direction(admin_client):
    """Невалидное направление → 400"""
    r = await admin_client.get("/admin/applications?direction=unknown")
    assert r.status_code == 400


async def test_admin_applications_invalid_cursor(admin_client):
    """Невалидный курсор → 400"""
    r = await admin_client.get("/admin/applications?cursor=!!!")
    assert r.status_code == 400


async def test_stats_overview_ok(admin_client, test_user):
    """Статистика возвращает агрегаты"""
    await _insert_application(test_user.id, "confirmed")
    await _insert_application(test_user.id, "declined")

    r = await admin_client.get("/admin/stats/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["by_status"]["confirmed"] == 1
    assert body["by_status"]["declined"] == 1


async def test_stats_overview_user_forbidden(user_client):
    """Обычный пользователь → 403"""
    r = await user_client.get("/admin/stats/overview")
    assert r.status_code == 403