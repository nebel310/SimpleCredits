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
ApplicationStatus = Literal["pending", "failed", "confirmed", "different", "declined"]

DEFAULT_PRODUCT_TYPE: ProductType = "term_loan"


class SApplication(BaseModel):
    """Параметры кредитной заявки для ML-сервиса"""
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
    # Расширенные признаки для ML. Клиент их не заполняет — их собирает бэкенд
    # из ответов мок-госуслуг (services.enrichment.extract_ml_extra_features).
    # Ключи должны входить в RAW_NUMERIC_FEATURES / CATEGORICAL_FEATURES на
    # стороне ML, иначе скоринг отклонит запрос с unknown features.
    extra_numeric_features: dict[str, float] = Field(default_factory=dict, max_length=512)
    extra_categorical_features: dict[str, str] = Field(default_factory=dict, max_length=512)


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
    scored_at: datetime | None = None
    decision: SDecisionResult | None = None


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


class SApplicationCreateRequest(BaseModel):
    """Тело запроса на создание кредитной заявки"""
    product_type: ProductType | None = None
    requested_amount_rub: int = Field(..., ge=0)
    term_months: int = Field(..., ge=1)
    purpose: FinancingPurpose
    segment: BusinessSegment
    company: SCompany | None = None
    financials: SFinancials | None = None
    credit_history: SCreditHistory | None = None


class SApplicationEventResponse(BaseModel):
    """Событие по заявке для отображения в таймлайне"""
    id: int
    event_type: str
    payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SApplicationDetail(BaseModel):
    """Полные данные заявки с результатом скоринга"""
    application_id: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    application: SApplication
    company: SCompany
    financials: SFinancials
    credit_history: SCreditHistory
    scoring_result: SScoreApplicationResponse | None = None
    enriched_data: dict | None = None
    explanation: str | None = None


class SApplicationListResponse(BaseModel):
    """Список заявок с курсорной пагинацией"""
    applications: list[SApplicationDetail]
    next_cursor: str | None = None
    previous_cursor: str | None = None


def application_orm_to_schema(application) -> SApplicationDetail:
    """Собирает SApplicationDetail из ORM-модели заявки"""
    scoring_result = None
    if application.scoring_result is not None:
        scoring_result = SScoreApplicationResponse.model_validate(application.scoring_result)

    return SApplicationDetail(
        application_id=application.application_id,
        status=application.status,
        created_at=application.created_at,
        updated_at=application.updated_at,
        application=SApplication(
            product_type=application.product_type or DEFAULT_PRODUCT_TYPE,
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
        scoring_result=scoring_result,
        enriched_data=application.enriched_data,
        explanation=application.explanation,
    )