from datetime import datetime, timezone
from types import SimpleNamespace

from schemas.scoring import application_orm_to_schema


def make_application_orm():
    """Возвращает ORM-подобный объект заявки для тестов"""
    return SimpleNamespace(
        application_id="abc123",
        status="scored",
        created_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        product_type="term_loan",
        requested_amount_rub=1500000,
        term_months=24,
        purpose="equipment",
        segment="small",
        submitted_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        inn="7701234567",
        ogrn="1027700132195",
        legal_name="ООО Ромашка",
        legal_form="llc",
        okved="62.01",
        region="Москва",
        registration_date=datetime(2018, 4, 12, tzinfo=timezone.utc),
        employee_count=25,
        annual_revenue_rub=42000000,
        annual_net_profit_rub=6500000,
        ebitda_rub=8200000,
        total_debt_rub=3000000,
        monthly_revenue_rub=3500000,
        monthly_expenses_rub=2800000,
        accounts_receivable_rub=1200000,
        cash_balance_rub=900000,
        period_end=datetime(2025, 12, 31, tzinfo=timezone.utc),
        active_obligations_count=2,
        total_outstanding_rub=3000000,
        monthly_debt_payments_rub=120000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
    )


def make_result_orm():
    """Возвращает ORM-подобный объект результата скоринга"""
    return SimpleNamespace(
        application_id="abc123",
        score=712,
        pd=0.0421,
        risk_grade="B",
        model_version="v1.0.0",
        scored_at=datetime(2026, 3, 15, 10, 0, 1, tzinfo=timezone.utc),
        decision="approve",
        reason_codes=[
            {
                "code": "RC001",
                "description": "X",
                "feature": "y",
                "impact": "positive",
                "contribution": -0.12,
            }
        ],
        conditions=[],
    )


def test_application_orm_to_schema_without_result():
    """Собирает заявку без результата скоринга"""
    detail = application_orm_to_schema(make_application_orm())
    assert detail.application_id == "abc123"
    assert detail.status == "scored"
    assert detail.scoring_result is None


def test_application_orm_to_schema_with_result():
    """Собирает заявку с результатом скоринга"""
    detail = application_orm_to_schema(make_application_orm(), make_result_orm())
    assert detail.scoring_result is not None
    assert detail.scoring_result.score == 712
    assert detail.scoring_result.risk_grade == "B"
    assert detail.scoring_result.decision.decision == "approve"


def test_application_orm_to_schema_with_conditions():
    """Собирает заявку с условиями в decision"""
    result = make_result_orm()
    result.conditions = [
        {"code": "C1", "description": "Уменьшить сумму", "recommended_amount_rub": 500000}
    ]
    detail = application_orm_to_schema(make_application_orm(), result)
    assert len(detail.scoring_result.decision.conditions) == 1
    assert detail.scoring_result.decision.conditions[0].recommended_amount_rub == 500000


def test_application_orm_to_schema_result_without_decision():
    """Собирает заявку с результатом без decision"""
    result = make_result_orm()
    result.decision = None
    detail = application_orm_to_schema(make_application_orm(), result)
    assert detail.scoring_result.decision is None