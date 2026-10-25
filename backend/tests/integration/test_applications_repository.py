from datetime import datetime, timezone

import pytest
from sqlalchemy import select

import database
from models.applications import ApplicationEventOrm, ApplicationOrm
from repositories.applications import ApplicationRepository
from schemas.applications import (
    SApplication,
    SCompany,
    SCreditHistory,
    SFinancials,
    SScoreApplicationRequest,
)


def make_request():
    """Возвращает валидный SScoreApplicationRequest"""
    return SScoreApplicationRequest(
        application=SApplication(
            product_type="term_loan",
            requested_amount_rub=1500000,
            term_months=24,
            purpose="equipment",
            segment="small",
            submitted_at=datetime(2026, 3, 15, 10, 0, 0),
        ),
        company=SCompany(
            inn="7701234567",
            ogrn="1027700132195",
            legal_name="ООО Ромашка",
            legal_form="llc",
            okved="62.01",
            region="Москва",
            registration_date=datetime(2018, 4, 12),
            employee_count=25,
        ),
        financials=SFinancials(
            annual_revenue_rub=42000000,
            annual_net_profit_rub=6500000,
            ebitda_rub=8200000,
            total_debt_rub=3000000,
            monthly_revenue_rub=3500000,
            monthly_expenses_rub=2800000,
            accounts_receivable_rub=1200000,
            cash_balance_rub=900000,
            period_end=datetime(2025, 12, 31),
        ),
        credit_history=SCreditHistory(
            active_obligations_count=2,
            total_outstanding_rub=3000000,
            monthly_debt_payments_rub=120000,
            max_days_past_due_12m=0,
            has_current_past_due=False,
            credit_utilization=0.35,
            closed_obligations_count=4,
            applications_last_6m=1,
        ),
    )


def make_scoring_result(**overrides):
    """Возвращает JSONB-совместимый результат скоринга"""
    base = {
        "application_id": "x",
        "score": 712,
        "pd": 0.0421,
        "risk_grade": "B",
        "reason_codes": [],
        "model_version": "v1.0.0",
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "decision": {"decision": "approve", "reason_codes": [], "conditions": []},
    }
    base.update(overrides)
    return base


async def test_create_persists_snapshot(test_user):
    """create сохраняет все поля заявки"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    assert app.application_id
    assert len(app.application_id) == 32
    assert app.user_id == test_user.id
    assert app.status == "pending"
    assert app.inn == "7701234567"
    assert app.annual_revenue_rub == 42000000
    assert app.credit_utilization == pytest.approx(0.35)
    assert app.enriched_data is None
    assert app.scoring_result is None
    assert app.explanation is None


async def test_create_writes_event(test_user):
    """create пишет событие created"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    events = await ApplicationRepository.list_events(app.application_id)
    assert len(events) == 1
    assert events[0].event_type == "created"
    assert events[0].payload == {"user_id": test_user.id}


async def test_create_unique_ids(test_user):
    """Каждая заявка получает уникальный application_id"""
    a = await ApplicationRepository.create(test_user.id, make_request())
    b = await ApplicationRepository.create(test_user.id, make_request())
    assert a.application_id != b.application_id


async def test_update_scoring_saves_result_and_status(test_user):
    """update_scoring сохраняет JSONB, статус и пишет два события"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    result = make_scoring_result(application_id=app.application_id)

    updated = await ApplicationRepository.update_scoring(
        app.application_id, result, status="scored"
    )

    assert updated is not None
    assert updated.status == "scored"
    assert updated.scoring_result == result
    events = await ApplicationRepository.list_events(app.application_id)
    event_types = [e.event_type for e in events]
    assert "scored" in event_types
    assert "status_changed" in event_types


async def test_update_scoring_with_explanation_and_enriched(test_user):
    """update_scoring сохраняет explanation и enriched_data"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    result = make_scoring_result()
    enriched = {"egrul": {"okved": "62.01"}}

    updated = await ApplicationRepository.update_scoring(
        app.application_id,
        result,
        status="confirmed",
        explanation="Одобрено",
        enriched_data=enriched,
    )

    assert updated.explanation == "Одобрено"
    assert updated.enriched_data == enriched


async def test_mark_failed_sets_status_and_event(test_user):
    """mark_failed выставляет статус и пишет событие"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    await ApplicationRepository.mark_failed(app.application_id, "ML down")

    updated = await ApplicationRepository.get_by_application_id(app.application_id)
    assert updated.status == "failed"
    events = await ApplicationRepository.list_events(app.application_id)
    assert any(e.event_type == "failed" for e in events)


async def test_add_event(test_user):
    """add_event пишет произвольное событие"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    await ApplicationRepository.add_event(
        app.application_id, "enriched", {"sources": ["egrul", "fns", "bki"]}
    )
    events = await ApplicationRepository.list_events(app.application_id)
    types = [e.event_type for e in events]
    assert "enriched" in types


async def test_get_by_application_id_missing():
    """Возвращает None для отсутствующей заявки"""
    assert await ApplicationRepository.get_by_application_id("nope") is None


async def test_list_events_empty_for_missing():
    """Пустой список для несуществующей заявки"""
    assert await ApplicationRepository.list_events("nope") == []


async def test_paginated_forward_no_cursor(test_user):
    """Первая страница forward без курсора"""
    for _ in range(3):
        await ApplicationRepository.create(test_user.id, make_request())
    apps, next_id, prev_id = await ApplicationRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=2
    )
    assert len(apps) == 2
    assert next_id is not None
    assert prev_id is None


async def test_paginated_forward_with_cursor(test_user):
    """Вторая страница forward"""
    for _ in range(3):
        await ApplicationRepository.create(test_user.id, make_request())
    _, next_id, _ = await ApplicationRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=2
    )
    apps2, next2, prev2 = await ApplicationRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=next_id, direction="forward", limit=2
    )
    assert len(apps2) == 1
    assert next2 is None
    assert prev2 is not None


async def test_paginated_backward_no_cursor(test_user):
    """Backward без курсора отдаёт последние N"""
    for _ in range(3):
        await ApplicationRepository.create(test_user.id, make_request())
    apps, _, _ = await ApplicationRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="backward", limit=2
    )
    assert len(apps) == 2


async def test_paginated_invalid_direction(test_user):
    """Кидает ValueError для неизвестного направления"""
    with pytest.raises(ValueError):
        await ApplicationRepository.get_user_applications_paginated(
            user_id=test_user.id, cursor_id=None, direction="unknown", limit=10
        )


async def test_paginated_filters_by_user(test_user, admin_user):
    """Возвращает только заявки пользователя"""
    await ApplicationRepository.create(test_user.id, make_request())
    await ApplicationRepository.create(admin_user.id, make_request())
    apps, _, _ = await ApplicationRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=10
    )
    assert len(apps) == 1
    assert apps[0].user_id == test_user.id


async def test_cascade_delete_removes_applications(test_user):
    """Удаление пользователя каскадно удаляет заявки"""
    await ApplicationRepository.create(test_user.id, make_request())
    async with database.new_session() as session:
        user = await session.get(type(test_user), test_user.id)
        await session.delete(user)
        await session.commit()
    async with database.new_session() as session:
        result = await session.execute(select(ApplicationOrm))
        assert result.scalars().all() == []


async def test_cascade_delete_removes_events(test_user):
    """Удаление заявки каскадно удаляет события"""
    app = await ApplicationRepository.create(test_user.id, make_request())
    async with database.new_session() as session:
        record = await session.get(ApplicationOrm, app.id)
        await session.delete(record)
        await session.commit()
    async with database.new_session() as session:
        result = await session.execute(select(ApplicationEventOrm))
        assert result.scalars().all() == []

async def test_backfill_outcomes_for_old_different_applications(test_user):
    """Старые заявки different без outcome получают тип результата по решению модели"""
    import uuid
    from datetime import datetime, timezone
    import database
    from models.applications import ApplicationOrm
    from repositories.applications import ApplicationRepository

    now = datetime.now(timezone.utc)
    common = dict(user_id=test_user.id, product_type="term_loan", requested_amount_rub=100000, term_months=12,
                  purpose="other", segment="micro", submitted_at=now, inn="7701234567", ogrn="1027700132195",
                  legal_name="ООО", legal_form="llc", okved="62.01", region="Москва", registration_date=now,
                  employee_count=1, annual_revenue_rub=1, annual_net_profit_rub=0, ebitda_rub=0, total_debt_rub=0,
                  monthly_revenue_rub=0, monthly_expenses_rub=0, accounts_receivable_rub=0, cash_balance_rub=0,
                  period_end=now, active_obligations_count=0, total_outstanding_rub=0, monthly_debt_payments_rub=0,
                  max_days_past_due_12m=0, has_current_past_due=False, credit_utilization=0.0,
                  closed_obligations_count=0, applications_last_6m=0)
    async with database.new_session() as session:
        for status, decision in [("different", "manual_review"), ("different", "approve_with_conditions"), ("confirmed", "approve")]:
            session.add(ApplicationOrm(application_id=uuid.uuid4().hex, status=status,
                                       scoring_result={"decision": {"decision": decision}}, **common))
        await session.commit()
    assert await ApplicationRepository.backfill_outcomes() == 2
    assert await ApplicationRepository.backfill_outcomes() == 0
