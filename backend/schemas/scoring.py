from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProductType = Literal[
    "PRODUCT_TYPE_UNSPECIFIED",
    "PRODUCT_TYPE_MICROLOAN",
    "PRODUCT_TYPE_TERM_LOAN",
    "PRODUCT_TYPE_OVERDRAFT",
    "PRODUCT_TYPE_CREDIT_LINE",
    "PRODUCT_TYPE_LEASING",
]

FinancingPurpose = Literal[
    "FINANCING_PURPOSE_UNSPECIFIED",
    "FINANCING_PURPOSE_WORKING_CAPITAL",
    "FINANCING_PURPOSE_EQUIPMENT",
    "FINANCING_PURPOSE_EXPANSION",
    "FINANCING_PURPOSE_REFINANCING",
    "FINANCING_PURPOSE_OTHER",
]

BusinessSegment = Literal[
    "BUSINESS_SEGMENT_UNSPECIFIED",
    "BUSINESS_SEGMENT_MICRO",
    "BUSINESS_SEGMENT_SMALL",
]

LegalForm = Literal[
    "LEGAL_FORM_UNSPECIFIED",
    "LEGAL_FORM_LLC",
    "LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR",
    "LEGAL_FORM_JOINT_STOCK_COMPANY",
]

RiskGrade = Literal[
    "RISK_GRADE_UNSPECIFIED",
    "RISK_GRADE_A",
    "RISK_GRADE_B",
    "RISK_GRADE_C",
    "RISK_GRADE_D",
    "RISK_GRADE_E",
]

ReasonImpact = Literal[
    "REASON_IMPACT_UNSPECIFIED",
    "REASON_IMPACT_POSITIVE",
    "REASON_IMPACT_NEGATIVE",
    "REASON_IMPACT_NEUTRAL",
]

Decision = Literal[
    "DECISION_UNSPECIFIED",
    "DECISION_APPROVE",
    "DECISION_APPROVE_WITH_CONDITIONS",
    "DECISION_MANUAL_REVIEW",
    "DECISION_DECLINE",
]


class SApplication(BaseModel):
    product_type: ProductType = "PRODUCT_TYPE_UNSPECIFIED"
    requested_amount_rub: int = Field(default=0, ge=0)
    term_months: int = Field(default=0, ge=0)
    purpose: FinancingPurpose = "FINANCING_PURPOSE_UNSPECIFIED"
    segment: BusinessSegment = "BUSINESS_SEGMENT_UNSPECIFIED"
    submitted_at: datetime | None = None


class SCompany(BaseModel):
    inn: str = Field(default="", max_length=12)
    ogrn: str = Field(default="", max_length=15)
    legal_name: str = ""
    legal_form: LegalForm = "LEGAL_FORM_UNSPECIFIED"
    okved: str = ""
    region: str = ""
    registration_date: datetime | None = None
    employee_count: int = Field(default=0, ge=0)


class SFinancials(BaseModel):
    annual_revenue_rub: int = Field(default=0, ge=0)
    annual_net_profit_rub: int = 0
    ebitda_rub: int = 0
    total_debt_rub: int = Field(default=0, ge=0)
    monthly_revenue_rub: int = Field(default=0, ge=0)
    monthly_expenses_rub: int = Field(default=0, ge=0)
    accounts_receivable_rub: int = Field(default=0, ge=0)
    cash_balance_rub: int = 0
    period_end: datetime | None = None


class SCreditHistory(BaseModel):
    active_obligations_count: int = Field(default=0, ge=0)
    total_outstanding_rub: int = Field(default=0, ge=0)
    monthly_debt_payments_rub: int = Field(default=0, ge=0)
    max_days_past_due_12m: int = Field(default=0, ge=0)
    has_current_past_due: bool = False
    credit_utilization: float = Field(default=0.0, ge=0.0)
    closed_obligations_count: int = Field(default=0, ge=0)
    applications_last_6m: int = Field(default=0, ge=0)


class SScoreApplicationRequest(BaseModel):
    application_id: str = Field(min_length=1, max_length=128)
    application: SApplication
    company: SCompany
    financials: SFinancials
    credit_history: SCreditHistory

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "application_id": "demo-good-001",
                    "application": {
                        "product_type": "PRODUCT_TYPE_TERM_LOAN",
                        "requested_amount_rub": 3000000,
                        "term_months": 24,
                        "purpose": "FINANCING_PURPOSE_EQUIPMENT",
                        "segment": "BUSINESS_SEGMENT_SMALL",
                    },
                    "company": {
                        "inn": "7700000001",
                        "ogrn": "1167746000001",
                        "legal_name": "ООО Пример",
                        "legal_form": "LEGAL_FORM_LLC",
                        "okved": "62.01",
                        "region": "Москва",
                        "registration_date": "2016-05-10T00:00:00Z",
                        "employee_count": 30,
                    },
                    "financials": {
                        "annual_revenue_rub": 120000000,
                        "annual_net_profit_rub": 18000000,
                        "ebitda_rub": 24000000,
                        "total_debt_rub": 10000000,
                        "monthly_revenue_rub": 10000000,
                        "monthly_expenses_rub": 7500000,
                        "accounts_receivable_rub": 4000000,
                        "cash_balance_rub": 5000000,
                        "period_end": "2025-12-31T00:00:00Z",
                    },
                    "credit_history": {
                        "active_obligations_count": 1,
                        "total_outstanding_rub": 2000000,
                        "monthly_debt_payments_rub": 150000,
                        "max_days_past_due_12m": 0,
                        "has_current_past_due": False,
                        "credit_utilization": 0.2,
                        "closed_obligations_count": 5,
                        "applications_last_6m": 0,
                    },
                }
            ]
        }
    )


class SReasonCode(BaseModel):
    code: str
    description: str
    feature: str
    impact: ReasonImpact
    contribution: float


class SDecisionCondition(BaseModel):
    code: str
    description: str
    recommended_amount_rub: int


class SDecisionResult(BaseModel):
    decision: Decision
    reason_codes: list[str] = Field(default_factory=list)
    conditions: list[SDecisionCondition] = Field(default_factory=list)


class SScoreApplicationResponse(BaseModel):
    application_id: str
    score: int
    pd: float
    risk_grade: RiskGrade
    reason_codes: list[SReasonCode]
    model_version: str
    scored_at: datetime
    decision: SDecisionResult


class SModelInfoResponse(BaseModel):
    model_version: str
    model_type: str
    trained_at: datetime | None = None
    features: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
