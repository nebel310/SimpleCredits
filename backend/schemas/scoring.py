from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProductType = Literal["microloan", "term_loan", "overdraft", "credit_line", "leasing"]
FinancingPurpose = Literal["working_capital", "equipment", "expansion", "refinancing", "other"]
BusinessSegment = Literal["micro", "small"]
LegalForm = Literal["llc", "individual_entrepreneur", "joint_stock_company"]
RiskGrade = Literal["A", "B", "C", "D", "E"]
Decision = Literal["approve", "approve_with_conditions", "manual_review", "decline"]
ReasonImpact = Literal["positive", "negative", "neutral"]


class SApplication(BaseModel):
    """Параметры кредитной заявки"""
    product_type: ProductType
    requested_amount_rub: int = Field(..., ge=0)
    term_months: int = Field(..., ge=1)
    purpose: FinancingPurpose
    segment: BusinessSegment
    submitted_at: datetime


class SCompany(BaseModel):
    """Данные компании-заемщика"""
    inn: str = Field(..., min_length=10, max_length=12)
    ogrn: str = Field(..., min_length=13, max_length=15)
    legal_name: str
    legal_form: LegalForm
    okved: str
    region: str
    registration_date: datetime
    employee_count: int = Field(..., ge=0)


class SFinancials(BaseModel):
    """Финансовые показатели компании"""
    annual_revenue_rub: int = Field(..., ge=0)
    annual_net_profit_rub: int
    ebitda_rub: int
    total_debt_rub: int = Field(..., ge=0)
    monthly_revenue_rub: int = Field(..., ge=0)
    monthly_expenses_rub: int = Field(..., ge=0)
    accounts_receivable_rub: int = Field(..., ge=0)
    cash_balance_rub: int = Field(..., ge=0)
    period_end: datetime


class SCreditHistory(BaseModel):
    """Кредитная история заемщика"""
    active_obligations_count: int = Field(..., ge=0)
    total_outstanding_rub: int = Field(..., ge=0)
    monthly_debt_payments_rub: int = Field(..., ge=0)
    max_days_past_due_12m: int = Field(..., ge=0)
    has_current_past_due: bool
    credit_utilization: float = Field(..., ge=0.0, le=1.0)
    closed_obligations_count: int = Field(..., ge=0)
    applications_last_6m: int = Field(..., ge=0)


class SScoreApplicationRequest(BaseModel):
    """Тело запроса скоринга от клиента"""
    application: SApplication
    company: SCompany
    financials: SFinancials
    credit_history: SCreditHistory

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "application": {
                        "product_type": "term_loan",
                        "requested_amount_rub": 1500000,
                        "term_months": 24,
                        "purpose": "equipment",
                        "segment": "small",
                        "submitted_at": "2026-03-15T10:00:00Z"
                    },
                    "company": {
                        "inn": "7701234567",
                        "ogrn": "1027700132195",
                        "legal_name": "ООО Ромашка",
                        "legal_form": "llc",
                        "okved": "62.01",
                        "region": "Москва",
                        "registration_date": "2018-04-12T00:00:00Z",
                        "employee_count": 25
                    },
                    "financials": {
                        "annual_revenue_rub": 42000000,
                        "annual_net_profit_rub": 6500000,
                        "ebitda_rub": 8200000,
                        "total_debt_rub": 3000000,
                        "monthly_revenue_rub": 3500000,
                        "monthly_expenses_rub": 2800000,
                        "accounts_receivable_rub": 1200000,
                        "cash_balance_rub": 900000,
                        "period_end": "2025-12-31T00:00:00Z"
                    },
                    "credit_history": {
                        "active_obligations_count": 2,
                        "total_outstanding_rub": 3000000,
                        "monthly_debt_payments_rub": 120000,
                        "max_days_past_due_12m": 0,
                        "has_current_past_due": False,
                        "credit_utilization": 0.35,
                        "closed_obligations_count": 4,
                        "applications_last_6m": 1
                    }
                }
            ]
        }
    )


class SReasonCode(BaseModel):
    """Фактор, повлиявший на скоринговый балл"""
    code: str
    description: str
    feature: str
    impact: ReasonImpact
    contribution: float


class SDecisionCondition(BaseModel):
    """Условие, при котором банк готов одобрить заявку"""
    code: str
    description: str
    recommended_amount_rub: int


class SDecisionResult(BaseModel):
    """Итоговое кредитное решение"""
    decision: Decision
    reason_codes: list[str] = []
    conditions: list[SDecisionCondition] = []


class SScoreApplicationResponse(BaseModel):
    """Ответ ML-сервиса с результатом скоринга"""
    application_id: str
    score: int
    pd: float
    risk_grade: RiskGrade
    reason_codes: list[SReasonCode]
    model_version: str
    scored_at: datetime
    decision: SDecisionResult | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "application_id": "8a3f9c2e1b4d4f5a9c7d6b5a4e3f2d1c",
                    "score": 712,
                    "pd": 0.0421,
                    "risk_grade": "B",
                    "reason_codes": [
                        {
                            "code": "RC001",
                            "description": "Стабильная кредитная история",
                            "feature": "max_days_past_due_12m",
                            "impact": "positive",
                            "contribution": -0.12
                        }
                    ],
                    "model_version": "v1.0.0",
                    "scored_at": "2026-03-15T10:00:01Z",
                    "decision": {
                        "decision": "approve",
                        "reason_codes": ["RC001"],
                        "conditions": []
                    }
                }
            ]
        }
    )


class SBatchScoreApplicationsRequest(BaseModel):
    """Пакетный запрос скоринга"""
    applications: list[SScoreApplicationRequest] = Field(..., min_length=1, max_length=100)


class SBatchScoreApplicationsResponse(BaseModel):
    """Пакетный ответ скоринга"""
    results: list[SScoreApplicationResponse]


class SModelInfoResponse(BaseModel):
    """Информация о загруженной ML-модели"""
    model_version: str
    model_type: str
    trained_at: datetime | None = None
    features: list[str] = []
    metrics: dict[str, float] = {}
    
    
class SApplicationDetail(BaseModel):
    """Полные данные заявки с результатом скоринга"""
    application_id: str
    status: str
    created_at: datetime
    application: SApplication
    company: SCompany
    financials: SFinancials
    credit_history: SCreditHistory
    scoring_result: SScoreApplicationResponse | None = None


class SApplicationListResponse(BaseModel):
    """Список заявок с курсорной пагинацией"""
    applications: list[SApplicationDetail]
    next_cursor: str | None = None
    previous_cursor: str | None = None


def application_orm_to_schema(application, scoring_result=None) -> SApplicationDetail:
    """Собирает SApplicationDetail из ORM-моделей заявки и результата скоринга"""
    detail = SApplicationDetail(
        application_id=application.application_id,
        status=application.status,
        created_at=application.created_at,
        application=SApplication(
            product_type=application.product_type,
            requested_amount_rub=application.requested_amount_rub,
            term_months=application.term_months,
            purpose=application.purpose,
            segment=application.segment,
            submitted_at=application.submitted_at,
        ),
        company=SCompany(
            inn=application.inn,
            ogrn=application.ogrn,
            legal_name=application.legal_name,
            legal_form=application.legal_form,
            okved=application.okved,
            region=application.region,
            registration_date=application.registration_date,
            employee_count=application.employee_count,
        ),
        financials=SFinancials(
            annual_revenue_rub=application.annual_revenue_rub,
            annual_net_profit_rub=application.annual_net_profit_rub,
            ebitda_rub=application.ebitda_rub,
            total_debt_rub=application.total_debt_rub,
            monthly_revenue_rub=application.monthly_revenue_rub,
            monthly_expenses_rub=application.monthly_expenses_rub,
            accounts_receivable_rub=application.accounts_receivable_rub,
            cash_balance_rub=application.cash_balance_rub,
            period_end=application.period_end,
        ),
        credit_history=SCreditHistory(
            active_obligations_count=application.active_obligations_count,
            total_outstanding_rub=application.total_outstanding_rub,
            monthly_debt_payments_rub=application.monthly_debt_payments_rub,
            max_days_past_due_12m=application.max_days_past_due_12m,
            has_current_past_due=application.has_current_past_due,
            credit_utilization=application.credit_utilization,
            closed_obligations_count=application.closed_obligations_count,
            applications_last_6m=application.applications_last_6m,
        ),
    )

    if scoring_result is not None:
        decision = None
        if scoring_result.decision is not None:
            decision = SDecisionResult(
                decision=scoring_result.decision,
                reason_codes=[],
                conditions=[
                    SDecisionCondition(**c) for c in (scoring_result.conditions or [])
                ],
            )

        detail.scoring_result = SScoreApplicationResponse(
            application_id=scoring_result.application_id,
            score=scoring_result.score,
            pd=scoring_result.pd,
            risk_grade=scoring_result.risk_grade,
            reason_codes=[
                SReasonCode(**rc) for rc in (scoring_result.reason_codes or [])
            ],
            model_version=scoring_result.model_version,
            scored_at=scoring_result.scored_at,
            decision=decision,
        )

    return detail