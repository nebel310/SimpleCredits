from datetime import datetime

import pytest
from sqlalchemy import select

import database
from models.scoring import ApplicationOrm, ScoringResultOrm
from repositories.scoring import ScoringRepository
from schemas.scoring import (
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


def make_result_dict(**overrides):
    """Возвращает словарь результата скоринга"""
    base = {
        "score": 712,
        "pd": 0.0421,
        "risk_grade": "B",
        "model_version": "v1.0.0",
        "scored_at": datetime(2026, 3, 15, 10, 0, 1),
        "decision": "approve",
        "reason_codes": [
            {
                "code": "RC001",
                "description": "Хорошая история",
                "feature": "max_days_past_due_12m",
                "impact": "positive",
                "contribution": -0.12,
            }
        ],
        "conditions": [],
    }
    base.update(overrides)
    return base


async def test_create_application_persists(test_user):
    """Сохраняет все поля заявки"""
    application = await ScoringRepository.create_application(test_user.id, make_request())

    assert application.application_id
    assert len(application.application_id) == 32
    assert application.user_id == test_user.id
    assert application.status == "pending"
    assert application.product_type == "term_loan"
    assert application.requested_amount_rub == 1500000
    assert application.inn == "7701234567"
    assert application.annual_revenue_rub == 42000000
    assert application.credit_utilization == pytest.approx(0.35)
    assert application.has_current_past_due is False


async def test_create_application_unique_ids(test_user):
    """Каждая заявка получает уникальный application_id"""
    app1 = await ScoringRepository.create_application(test_user.id, make_request())
    app2 = await ScoringRepository.create_application(test_user.id, make_request())
    assert app1.application_id != app2.application_id


async def test_save_scoring_result_success(test_user):
    """Сохраняет результат и переводит заявку в scored"""
    application = await ScoringRepository.create_application(test_user.id, make_request())

    result = await ScoringRepository.save_scoring_result(
        application.application_id, make_result_dict()
    )

    assert result.application_id == application.application_id
    assert result.score == 712
    assert result.risk_grade == "B"
    assert result.decision == "approve"

    refreshed = await ScoringRepository.get_application_by_application_id(
        application.application_id
    )
    assert refreshed.status == "scored"


async def test_save_scoring_result_with_conditions(test_user):
    """Сохраняет conditions как JSON"""
    application = await ScoringRepository.create_application(test_user.id, make_request())

    conditions = [
        {"code": "C1", "description": "Уменьшить сумму", "recommended_amount_rub": 500000}
    ]
    result = await ScoringRepository.save_scoring_result(
        application.application_id,
        make_result_dict(decision="approve_with_conditions", conditions=conditions),
    )
    assert result.conditions == conditions


async def test_mark_application_failed(test_user):
    """Переводит заявку в failed"""
    application = await ScoringRepository.create_application(test_user.id, make_request())

    await ScoringRepository.mark_application_failed(application.application_id)

    refreshed = await ScoringRepository.get_application_by_application_id(
        application.application_id
    )
    assert refreshed.status == "failed"


async def test_get_application_by_id_missing():
    """Возвращает None для отсутствующей заявки"""
    assert await ScoringRepository.get_application_by_application_id("nope") is None


async def test_get_scoring_result_missing():
    """Возвращает None для отсутствующего результата"""
    assert await ScoringRepository.get_scoring_result_by_application_id("nope") is None


async def test_get_scoring_result_by_application_id(test_user):
    """Возвращает сохранённый результат по application_id"""
    application = await ScoringRepository.create_application(test_user.id, make_request())
    await ScoringRepository.save_scoring_result(
        application.application_id, make_result_dict()
    )

    result = await ScoringRepository.get_scoring_result_by_application_id(
        application.application_id
    )
    assert result is not None
    assert result.score == 712


async def test_paginated_forward_no_cursor(test_user):
    """Возвращает первые N заявок в прямом порядке"""
    for _ in range(3):
        await ScoringRepository.create_application(test_user.id, make_request())

    apps, next_id, prev_id = await ScoringRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=2
    )
    assert len(apps) == 2
    assert next_id is not None
    assert prev_id is None


async def test_paginated_forward_with_cursor(test_user):
    """Возвращает следующую страницу и prev_cursor"""
    for _ in range(3):
        await ScoringRepository.create_application(test_user.id, make_request())

    _, next_id, _ = await ScoringRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=2
    )
    apps2, next2, prev2 = await ScoringRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=next_id, direction="forward", limit=2
    )
    assert len(apps2) == 1
    assert next2 is None
    assert prev2 is not None


async def test_paginated_backward_no_cursor(test_user):
    """Backward без курсора отдаёт последние N"""
    for _ in range(3):
        await ScoringRepository.create_application(test_user.id, make_request())

    apps, _, _ = await ScoringRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="backward", limit=2
    )
    assert len(apps) == 2


async def test_paginated_invalid_direction(test_user):
    """Кидает ValueError для неизвестного направления"""
    with pytest.raises(ValueError):
        await ScoringRepository.get_user_applications_paginated(
            user_id=test_user.id, cursor_id=None, direction="unknown", limit=10
        )


async def test_paginated_filters_by_user(test_user, admin_user):
    """Возвращает только заявки указанного пользователя"""
    await ScoringRepository.create_application(test_user.id, make_request())
    await ScoringRepository.create_application(admin_user.id, make_request())

    apps, _, _ = await ScoringRepository.get_user_applications_paginated(
        user_id=test_user.id, cursor_id=None, direction="forward", limit=10
    )
    assert len(apps) == 1
    assert apps[0].user_id == test_user.id


async def test_cascade_delete_removes_applications(test_user):
    """Удаление пользователя каскадно удаляет его заявки"""
    await ScoringRepository.create_application(test_user.id, make_request())

    async with database.new_session() as session:
        user = await session.get(type(test_user), test_user.id)
        await session.delete(user)
        await session.commit()

    async with database.new_session() as session:
        result = await session.execute(select(ApplicationOrm))
        assert result.scalars().all() == []


async def test_cascade_delete_removes_scoring_results(test_user):
    """Удаление заявки каскадно удаляет результат скоринга"""
    application = await ScoringRepository.create_application(test_user.id, make_request())
    await ScoringRepository.save_scoring_result(
        application.application_id, make_result_dict()
    )

    async with database.new_session() as session:
        record = await session.get(ApplicationOrm, application.id)
        await session.delete(record)
        await session.commit()

    async with database.new_session() as session:
        result = await session.execute(select(ScoringResultOrm))
        assert result.scalars().all() == []