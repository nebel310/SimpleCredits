from datetime import datetime, timezone

from sqlalchemy import select

import database
from models.applications import ApplicationOrm
from repositories.admin import AdminRepository


def _scoring(score: int, risk_grade: str) -> dict:
    """Собирает минимальный scoring_result JSON"""
    return {
        "application_id": "x",
        "score": score,
        "pd": 0.04,
        "risk_grade": risk_grade,
        "reason_codes": [],
        "model_version": "v1",
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "decision": None,
    }


async def _insert_application(
    user_id: int,
    status: str,
    product_type: str | None,
    scoring_result: dict | None,
) -> ApplicationOrm:
    """Прямо вставляет заявку в БД (без событий)"""
    import uuid

    now = datetime.now(timezone.utc)
    async with database.new_session() as session:
        application = ApplicationOrm(
            application_id=f"app-{uuid.uuid4().hex}",
            user_id=user_id,
            status=status,
            product_type=product_type,
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
            scoring_result=scoring_result,
            created_at=now,
            updated_at=now,
        )
        session.add(application)
        await session.commit()
        await session.refresh(application)
        return application


async def test_stats_overview_empty():
    """Пустая БД → нули"""
    stats = await AdminRepository.stats_overview()
    assert stats["total"] == 0
    assert stats["by_status"] == {}
    assert stats["by_product_type"] == {}
    assert stats["by_risk_grade"] == {}
    assert stats["avg_score"] is None


async def test_stats_overview_counts(test_user):
    """Считает total, by_status, by_product_type, avg_score, by_risk_grade"""
    await _insert_application(test_user.id, "confirmed", "term_loan", _scoring(700, "B"))
    await _insert_application(test_user.id, "confirmed", "term_loan", _scoring(800, "A"))
    await _insert_application(test_user.id, "declined", "microloan", None)

    stats = await AdminRepository.stats_overview()
    assert stats["total"] == 3
    assert stats["by_status"] == {"confirmed": 2, "declined": 1}
    assert stats["by_product_type"] == {"term_loan": 2, "microloan": 1}
    assert stats["by_risk_grade"] == {"B": 1, "A": 1}
    assert stats["avg_score"] == 750.0


async def test_stats_overview_null_product_type(test_user):
    """product_type=None попадает в 'unknown'"""
    await _insert_application(test_user.id, "different", None, None)
    stats = await AdminRepository.stats_overview()
    assert stats["by_product_type"] == {"unknown": 1}


async def test_list_all_paginated_forward(test_user, admin_user):
    """Forward-пагинация всех заявок"""
    for _ in range(3):
        await _insert_application(test_user.id, "confirmed", "term_loan", None)

    apps, next_id, prev_id = await AdminRepository.list_all_paginated(
        cursor_id=None, direction="forward", limit=2
    )
    assert len(apps) == 2
    assert next_id is not None
    assert prev_id is None


async def test_list_all_paginated_backward(test_user):
    """Backward-пагинация без курсора отдаёт последние N"""
    for _ in range(3):
        await _insert_application(test_user.id, "confirmed", "term_loan", None)

    apps, _, _ = await AdminRepository.list_all_paginated(
        cursor_id=None, direction="backward", limit=2
    )
    assert len(apps) == 2


async def test_list_all_paginated_invalid_direction(test_user):
    """Невалидное направление → ValueError"""
    import pytest
    with pytest.raises(ValueError):
        await AdminRepository.list_all_paginated(
            cursor_id=None, direction="unknown", limit=10
        )


async def test_list_all_paginated_includes_all_users(test_user, admin_user):
    """Листинг админа видит заявки всех пользователей"""
    await _insert_application(test_user.id, "confirmed", "term_loan", None)
    await _insert_application(admin_user.id, "confirmed", "term_loan", None)

    apps, _, _ = await AdminRepository.list_all_paginated(
        cursor_id=None, direction="forward", limit=10
    )
    assert len(apps) == 2