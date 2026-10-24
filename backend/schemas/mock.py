from datetime import datetime

from pydantic import BaseModel


class SEgrulResponse(BaseModel):
    """Ответ мока ЕГРЮЛ"""
    inn: str
    ogrn: str
    legal_name: str
    legal_form: str
    status: str
    okved: str
    okved_description: str
    region: str
    registration_date: datetime
    employee_count: int
    director: str
    address: str


class SFnsResponse(BaseModel):
    """Ответ мока ФНС"""
    inn: str
    tax_regime: str
    tax_debt_rub: int
    disqualified_persons: bool
    mass_address: bool
    mass_director: bool
    reliability_score: int
    last_reporting_date: datetime


class SBkiResponse(BaseModel):
    """Ответ мока БКИ"""
    inn: str
    credit_score: int
    active_obligations_count: int
    total_outstanding_rub: int
    monthly_debt_payments_rub: int
    max_days_past_due_12m: int
    has_current_past_due: bool
    credit_utilization: float
    closed_obligations_count: int
    applications_last_6m: int
    last_update: datetime