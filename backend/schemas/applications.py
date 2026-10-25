from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ProductType = Literal["microloan", "term_loan", "overdraft", "credit_line", "leasing"]
FinancingPurpose = Literal["working_capital", "equipment", "expansion", "refinancing", "other"]
BusinessSegment = Literal["micro", "small"]
LegalForm = Literal["llc", "individual_entrepreneur", "joint_stock_company"]
RiskGrade = Literal["A", "B", "C", "D", "E"]
Decision = Literal["approve", "approve_with_conditions", "manual_review", "decline"]
ReasonImpact = Literal["positive", "negative", "neutral"]
ApplicationStatus = Literal[
    "pending", "failed", "confirmed", "different", "declined",
    # после решения: клиент принял предложение → кредит оформлен и выдан (синтетически),
    # или клиент отказался от предложения
    "accepted", "issued", "rejected_by_client",
]
# Уточнение статуса different: что именно предлагает банк
ApplicationOutcome = Literal["ALTERNATIVE_PRODUCT", "COUNTER_OFFER", "MANUAL_REVIEW"]
# Что клиент может сделать с заявкой сейчас (кнопки на фронте)
ApplicationAction = Literal["accept", "reject", "issue", "retry"]
ACCEPTABLE_OUTCOMES = ("ALTERNATIVE_PRODUCT", "COUNTER_OFFER")


def available_actions(status: str, outcome: str | None, has_offer: bool) -> list[str]:
    """
    Действия клиента по заявке. Одно правило для API, кнопок и проверок на сервере:
    принять/отказаться — одобрение или предложение банка с оффером; оформить — после
    принятия; повторить — после технической ошибки. Ручная проверка — не оффер.
    """
    if status == "failed":
        return ["retry"]
    if status == "accepted":
        return ["issue", "reject"]
    offer_ready = has_offer and (status == "confirmed" or (status == "different" and outcome in ACCEPTABLE_OUTCOMES))
    return ["accept", "reject"] if offer_ready else []

DEFAULT_PRODUCT_TYPE: ProductType = "term_loan"


def ensure_not_future(value: datetime | None, what: str) -> None:
    """
    Дата из анкеты не может быть в будущем. Сутки запаса — из-за часовых поясов:
    клиент в Москве после полуночи уже живёт «завтрашней» датой по UTC.
    """
    if value is None:
        return
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if moment > datetime.now(timezone.utc) + timedelta(days=1):
        raise ValueError(f"{what} не может быть в будущем")


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
    # Если на рекомендуемую сумму подходит другой продукт — какой (заполняет бэкенд)
    recommended_product_type: ProductType | None = None


class SOffer(BaseModel):
    """Условия предложения банка: ставка внутри диапазона продукта по грейду, аннуитетный платёж"""
    product_type: ProductType
    product_code: str
    product_name: str
    amount_rub: int
    term_months: int
    rate_percent: float
    monthly_payment_rub: int
    total_payment_rub: int
    overpayment_rub: int


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
    requested_amount_rub: int = Field(..., gt=0)
    term_months: int = Field(..., ge=1)
    purpose: FinancingPurpose
    segment: BusinessSegment
    company: SCompany | None = None
    financials: SFinancials | None = None
    credit_history: SCreditHistory | None = None

    @model_validator(mode="after")
    def check_dates(self):
        """Даты компании и отчётности не из будущего"""
        if self.company is not None:
            ensure_not_future(self.company.registration_date, "Дата регистрации компании")
        if self.financials is not None:
            ensure_not_future(self.financials.period_end, "Отчётный период")
        return self


class SBankDecision(BaseModel):
    """Решение сотрудника банка по заявке на ручной проверке"""
    decision: Literal["approve", "approve_with_conditions", "decline"]
    comment: str | None = None
    recommended_amount_rub: int | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None


class SBankDecisionRequest(BaseModel):
    """Тело POST /admin/applications/{id}/decision"""
    decision: Literal["approve", "approve_with_conditions", "decline"]
    recommended_amount_rub: int | None = Field(None, gt=0)
    comment: str | None = Field(None, max_length=1000)

    @model_validator(mode="after")
    def check_amount(self):
        """Для одобрения с условиями нужна сумма"""
        if self.decision == "approve_with_conditions" and self.recommended_amount_rub is None:
            raise ValueError("Для одобрения с условиями укажите recommended_amount_rub")
        return self


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
    product_selected_by_system: bool = False
    outcome: ApplicationOutcome | None = None
    offer: SOffer | None = None
    contract_number: str | None = None
    issued_at: datetime | None = None
    bank_decision: SBankDecision | None = None
    actions: list[ApplicationAction] = []
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
        product_selected_by_system=bool(getattr(application, "product_selected_by_system", False)),
        outcome=getattr(application, "outcome", None),
        offer=SOffer.model_validate(application.offer) if getattr(application, "offer", None) else None,
        contract_number=getattr(application, "contract_number", None),
        issued_at=getattr(application, "issued_at", None),
        bank_decision=getattr(application, "bank_decision", None),
        actions=available_actions(
            application.status, getattr(application, "outcome", None), bool(getattr(application, "offer", None))
        ),
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