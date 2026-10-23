from datetime import datetime, timezone

from simplecredits.scoring.v1 import scoring_pb2

from schemas.scoring import (
    SDecisionCondition,
    SDecisionResult,
    SModelInfoResponse,
    SReasonCode,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
)


PRODUCT_TYPES = {
    "PRODUCT_TYPE_UNSPECIFIED": scoring_pb2.PRODUCT_TYPE_UNSPECIFIED,
    "PRODUCT_TYPE_MICROLOAN": scoring_pb2.PRODUCT_TYPE_MICROLOAN,
    "PRODUCT_TYPE_TERM_LOAN": scoring_pb2.PRODUCT_TYPE_TERM_LOAN,
    "PRODUCT_TYPE_OVERDRAFT": scoring_pb2.PRODUCT_TYPE_OVERDRAFT,
    "PRODUCT_TYPE_CREDIT_LINE": scoring_pb2.PRODUCT_TYPE_CREDIT_LINE,
    "PRODUCT_TYPE_LEASING": scoring_pb2.PRODUCT_TYPE_LEASING,
}

FINANCING_PURPOSES = {
    "FINANCING_PURPOSE_UNSPECIFIED": scoring_pb2.FINANCING_PURPOSE_UNSPECIFIED,
    "FINANCING_PURPOSE_WORKING_CAPITAL": scoring_pb2.FINANCING_PURPOSE_WORKING_CAPITAL,
    "FINANCING_PURPOSE_EQUIPMENT": scoring_pb2.FINANCING_PURPOSE_EQUIPMENT,
    "FINANCING_PURPOSE_EXPANSION": scoring_pb2.FINANCING_PURPOSE_EXPANSION,
    "FINANCING_PURPOSE_REFINANCING": scoring_pb2.FINANCING_PURPOSE_REFINANCING,
    "FINANCING_PURPOSE_OTHER": scoring_pb2.FINANCING_PURPOSE_OTHER,
}

BUSINESS_SEGMENTS = {
    "BUSINESS_SEGMENT_UNSPECIFIED": scoring_pb2.BUSINESS_SEGMENT_UNSPECIFIED,
    "BUSINESS_SEGMENT_MICRO": scoring_pb2.BUSINESS_SEGMENT_MICRO,
    "BUSINESS_SEGMENT_SMALL": scoring_pb2.BUSINESS_SEGMENT_SMALL,
}

LEGAL_FORMS = {
    "LEGAL_FORM_UNSPECIFIED": scoring_pb2.LEGAL_FORM_UNSPECIFIED,
    "LEGAL_FORM_LLC": scoring_pb2.LEGAL_FORM_LLC,
    "LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR": scoring_pb2.LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR,
    "LEGAL_FORM_JOINT_STOCK_COMPANY": scoring_pb2.LEGAL_FORM_JOINT_STOCK_COMPANY,
}

RISK_GRADES = {
    scoring_pb2.RISK_GRADE_UNSPECIFIED: "RISK_GRADE_UNSPECIFIED",
    scoring_pb2.RISK_GRADE_A: "RISK_GRADE_A",
    scoring_pb2.RISK_GRADE_B: "RISK_GRADE_B",
    scoring_pb2.RISK_GRADE_C: "RISK_GRADE_C",
    scoring_pb2.RISK_GRADE_D: "RISK_GRADE_D",
    scoring_pb2.RISK_GRADE_E: "RISK_GRADE_E",
}

REASON_IMPACTS = {
    scoring_pb2.REASON_IMPACT_UNSPECIFIED: "REASON_IMPACT_UNSPECIFIED",
    scoring_pb2.REASON_IMPACT_POSITIVE: "REASON_IMPACT_POSITIVE",
    scoring_pb2.REASON_IMPACT_NEGATIVE: "REASON_IMPACT_NEGATIVE",
    scoring_pb2.REASON_IMPACT_NEUTRAL: "REASON_IMPACT_NEUTRAL",
}

DECISIONS = {
    scoring_pb2.DECISION_UNSPECIFIED: "DECISION_UNSPECIFIED",
    scoring_pb2.DECISION_APPROVE: "DECISION_APPROVE",
    scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS: "DECISION_APPROVE_WITH_CONDITIONS",
    scoring_pb2.DECISION_MANUAL_REVIEW: "DECISION_MANUAL_REVIEW",
    scoring_pb2.DECISION_DECLINE: "DECISION_DECLINE",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_proto_request(request: SScoreApplicationRequest) -> scoring_pb2.ScoreApplicationRequest:
    message = scoring_pb2.ScoreApplicationRequest(application_id=request.application_id)

    application = request.application
    message.application.product_type = PRODUCT_TYPES[application.product_type]
    message.application.requested_amount_rub = application.requested_amount_rub
    message.application.term_months = application.term_months
    message.application.purpose = FINANCING_PURPOSES[application.purpose]
    message.application.segment = BUSINESS_SEGMENTS[application.segment]
    if application.submitted_at is not None:
        message.application.submitted_at.FromDatetime(_utc(application.submitted_at))

    company = request.company
    message.company.inn = company.inn
    message.company.ogrn = company.ogrn
    message.company.legal_name = company.legal_name
    message.company.legal_form = LEGAL_FORMS[company.legal_form]
    message.company.okved = company.okved
    message.company.region = company.region
    if company.registration_date is not None:
        message.company.registration_date.FromDatetime(_utc(company.registration_date))
    message.company.employee_count = company.employee_count

    financials = request.financials
    message.financials.annual_revenue_rub = financials.annual_revenue_rub
    message.financials.annual_net_profit_rub = financials.annual_net_profit_rub
    message.financials.ebitda_rub = financials.ebitda_rub
    message.financials.total_debt_rub = financials.total_debt_rub
    message.financials.monthly_revenue_rub = financials.monthly_revenue_rub
    message.financials.monthly_expenses_rub = financials.monthly_expenses_rub
    message.financials.accounts_receivable_rub = financials.accounts_receivable_rub
    message.financials.cash_balance_rub = financials.cash_balance_rub
    if financials.period_end is not None:
        message.financials.period_end.FromDatetime(_utc(financials.period_end))

    history = request.credit_history
    message.credit_history.active_obligations_count = history.active_obligations_count
    message.credit_history.total_outstanding_rub = history.total_outstanding_rub
    message.credit_history.monthly_debt_payments_rub = history.monthly_debt_payments_rub
    message.credit_history.max_days_past_due_12m = history.max_days_past_due_12m
    message.credit_history.has_current_past_due = history.has_current_past_due
    message.credit_history.credit_utilization = history.credit_utilization
    message.credit_history.closed_obligations_count = history.closed_obligations_count
    message.credit_history.applications_last_6m = history.applications_last_6m

    message.extra_numeric_features.update(request.extra_numeric_features)
    message.extra_categorical_features.update(request.extra_categorical_features)

    return message


def from_proto_response(response: scoring_pb2.ScoreApplicationResponse) -> SScoreApplicationResponse:
    scored_at = datetime.now(timezone.utc)
    if response.HasField("scored_at"):
        scored_at = response.scored_at.ToDatetime(tzinfo=timezone.utc)

    reasons = [
        SReasonCode(
            code=reason.code,
            description=reason.description,
            feature=reason.feature,
            impact=REASON_IMPACTS.get(reason.impact, "REASON_IMPACT_UNSPECIFIED"),
            contribution=reason.contribution,
        )
        for reason in response.reason_codes
    ]

    conditions = [
        SDecisionCondition(
            code=condition.code,
            description=condition.description,
            recommended_amount_rub=condition.recommended_amount_rub,
        )
        for condition in response.decision.conditions
    ]

    return SScoreApplicationResponse(
        application_id=response.application_id,
        score=response.score,
        pd=response.pd,
        risk_grade=RISK_GRADES.get(response.risk_grade, "RISK_GRADE_UNSPECIFIED"),
        reason_codes=reasons,
        model_version=response.model_version,
        scored_at=scored_at,
        decision=SDecisionResult(
            decision=DECISIONS.get(response.decision.decision, "DECISION_UNSPECIFIED"),
            reason_codes=list(response.decision.reason_codes),
            conditions=conditions,
        ),
    )


def from_proto_model_info(response: scoring_pb2.GetModelInfoResponse) -> SModelInfoResponse:
    trained_at = None
    if response.HasField("trained_at"):
        trained_at = response.trained_at.ToDatetime(tzinfo=timezone.utc)

    return SModelInfoResponse(
        model_version=response.model_version,
        model_type=response.model_type,
        trained_at=trained_at,
        features=list(response.features),
        metrics={key: float(value) for key, value in response.metrics.items()},
    )
