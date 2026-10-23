from datetime import datetime, timezone

from google.protobuf.timestamp_pb2 import Timestamp

from grpc.generated.simplecredits.scoring.v1 import scoring_pb2

from schemas.scoring import (
    SApplication,
    SCompany,
    SCreditHistory,
    SDecisionCondition,
    SDecisionResult,
    SFinancials,
    SModelInfoResponse,
    SReasonCode,
    SScoreApplicationRequest,
    SScoreApplicationResponse,
)


PRODUCT_TYPE_TO_PROTO = {
    "microloan": scoring_pb2.PRODUCT_TYPE_MICROLOAN,
    "term_loan": scoring_pb2.PRODUCT_TYPE_TERM_LOAN,
    "overdraft": scoring_pb2.PRODUCT_TYPE_OVERDRAFT,
    "credit_line": scoring_pb2.PRODUCT_TYPE_CREDIT_LINE,
    "leasing": scoring_pb2.PRODUCT_TYPE_LEASING,
}
PRODUCT_TYPE_FROM_PROTO = {v: k for k, v in PRODUCT_TYPE_TO_PROTO.items()}

PURPOSE_TO_PROTO = {
    "working_capital": scoring_pb2.FINANCING_PURPOSE_WORKING_CAPITAL,
    "equipment": scoring_pb2.FINANCING_PURPOSE_EQUIPMENT,
    "expansion": scoring_pb2.FINANCING_PURPOSE_EXPANSION,
    "refinancing": scoring_pb2.FINANCING_PURPOSE_REFINANCING,
    "other": scoring_pb2.FINANCING_PURPOSE_OTHER,
}
PURPOSE_FROM_PROTO = {v: k for k, v in PURPOSE_TO_PROTO.items()}

SEGMENT_TO_PROTO = {
    "micro": scoring_pb2.BUSINESS_SEGMENT_MICRO,
    "small": scoring_pb2.BUSINESS_SEGMENT_SMALL,
}
SEGMENT_FROM_PROTO = {v: k for k, v in SEGMENT_TO_PROTO.items()}

LEGAL_FORM_TO_PROTO = {
    "llc": scoring_pb2.LEGAL_FORM_LLC,
    "individual_entrepreneur": scoring_pb2.LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR,
    "joint_stock_company": scoring_pb2.LEGAL_FORM_JOINT_STOCK_COMPANY,
}
LEGAL_FORM_FROM_PROTO = {v: k for k, v in LEGAL_FORM_TO_PROTO.items()}

RISK_GRADE_TO_PROTO = {
    "A": scoring_pb2.RISK_GRADE_A,
    "B": scoring_pb2.RISK_GRADE_B,
    "C": scoring_pb2.RISK_GRADE_C,
    "D": scoring_pb2.RISK_GRADE_D,
    "E": scoring_pb2.RISK_GRADE_E,
}
RISK_GRADE_FROM_PROTO = {v: k for k, v in RISK_GRADE_TO_PROTO.items()}

DECISION_TO_PROTO = {
    "approve": scoring_pb2.DECISION_APPROVE,
    "approve_with_conditions": scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS,
    "manual_review": scoring_pb2.DECISION_MANUAL_REVIEW,
    "decline": scoring_pb2.DECISION_DECLINE,
}
DECISION_FROM_PROTO = {v: k for k, v in DECISION_TO_PROTO.items()}

IMPACT_TO_PROTO = {
    "positive": scoring_pb2.REASON_IMPACT_POSITIVE,
    "negative": scoring_pb2.REASON_IMPACT_NEGATIVE,
    "neutral": scoring_pb2.REASON_IMPACT_NEUTRAL,
}
IMPACT_FROM_PROTO = {v: k for k, v in IMPACT_TO_PROTO.items()}


def dt_to_timestamp(dt):
    """Конвертирует datetime в protobuf Timestamp с UTC"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(dt)
    return ts


def timestamp_to_dt(ts):
    """Конвертирует protobuf Timestamp в datetime UTC или None для пустого"""
    if ts is None:
        return None
    if ts.seconds == 0 and ts.nanos == 0:
        return None
    return ts.ToDatetime(tzinfo=timezone.utc)


def application_to_proto(data):
    """Конвертирует SApplication в proto Application"""
    try:
        product_type = PRODUCT_TYPE_TO_PROTO[data.product_type]
    except KeyError as exc:
        raise ValueError(f"Неизвестный product_type: {data.product_type}") from exc

    try:
        purpose = PURPOSE_TO_PROTO[data.purpose]
    except KeyError as exc:
        raise ValueError(f"Неизвестный purpose: {data.purpose}") from exc

    try:
        segment = SEGMENT_TO_PROTO[data.segment]
    except KeyError as exc:
        raise ValueError(f"Неизвестный segment: {data.segment}") from exc

    return scoring_pb2.Application(
        product_type=product_type,
        requested_amount_rub=data.requested_amount_rub,
        term_months=data.term_months,
        purpose=purpose,
        segment=segment,
        submitted_at=dt_to_timestamp(data.submitted_at),
    )


def company_to_proto(data):
    """Конвертирует SCompany в proto Company"""
    try:
        legal_form = LEGAL_FORM_TO_PROTO[data.legal_form]
    except KeyError as exc:
        raise ValueError(f"Неизвестный legal_form: {data.legal_form}") from exc

    return scoring_pb2.Company(
        inn=data.inn,
        ogrn=data.ogrn,
        legal_name=data.legal_name,
        legal_form=legal_form,
        okved=data.okved,
        region=data.region,
        registration_date=dt_to_timestamp(data.registration_date),
        employee_count=data.employee_count,
    )


def financials_to_proto(data):
    """Конвертирует SFinancials в proto Financials"""
    return scoring_pb2.Financials(
        annual_revenue_rub=data.annual_revenue_rub,
        annual_net_profit_rub=data.annual_net_profit_rub,
        ebitda_rub=data.ebitda_rub,
        total_debt_rub=data.total_debt_rub,
        monthly_revenue_rub=data.monthly_revenue_rub,
        monthly_expenses_rub=data.monthly_expenses_rub,
        accounts_receivable_rub=data.accounts_receivable_rub,
        cash_balance_rub=data.cash_balance_rub,
        period_end=dt_to_timestamp(data.period_end),
    )


def credit_history_to_proto(data):
    """Конвертирует SCreditHistory в proto CreditHistory"""
    return scoring_pb2.CreditHistory(
        active_obligations_count=data.active_obligations_count,
        total_outstanding_rub=data.total_outstanding_rub,
        monthly_debt_payments_rub=data.monthly_debt_payments_rub,
        max_days_past_due_12m=data.max_days_past_due_12m,
        has_current_past_due=data.has_current_past_due,
        credit_utilization=data.credit_utilization,
        closed_obligations_count=data.closed_obligations_count,
        applications_last_6m=data.applications_last_6m,
    )


def schema_to_proto_score_request(data, application_id):
    """Собирает proto ScoreApplicationRequest из схемы и application_id"""
    return scoring_pb2.ScoreApplicationRequest(
        application_id=application_id,
        application=application_to_proto(data.application),
        company=company_to_proto(data.company),
        financials=financials_to_proto(data.financials),
        credit_history=credit_history_to_proto(data.credit_history),
    )


def proto_to_reason_code(proto):
    """Конвертирует proto ReasonCode в SReasonCode"""
    try:
        impact = IMPACT_FROM_PROTO[proto.impact]
    except KeyError as exc:
        raise ValueError(f"Неизвестный impact: {proto.impact}") from exc

    return SReasonCode(
        code=proto.code,
        description=proto.description,
        feature=proto.feature,
        impact=impact,
        contribution=proto.contribution,
    )


def proto_to_decision_condition(proto):
    """Конвертирует proto DecisionCondition в SDecisionCondition"""
    return SDecisionCondition(
        code=proto.code,
        description=proto.description,
        recommended_amount_rub=proto.recommended_amount_rub,
    )


def proto_to_decision_result(proto):
    """Конвертирует proto DecisionResult в SDecisionResult"""
    try:
        decision = DECISION_FROM_PROTO[proto.decision]
    except KeyError as exc:
        raise ValueError(f"Неизвестное decision: {proto.decision}") from exc

    return SDecisionResult(
        decision=decision,
        reason_codes=list(proto.reason_codes),
        conditions=[proto_to_decision_condition(c) for c in proto.conditions],
    )


def proto_to_schema_response(proto):
    """Конвертирует proto ScoreApplicationResponse в SScoreApplicationResponse"""
    try:
        risk_grade = RISK_GRADE_FROM_PROTO[proto.risk_grade]
    except KeyError as exc:
        raise ValueError(f"Неизвестный risk_grade: {proto.risk_grade}") from exc

    decision = None
    if proto.HasField("decision"):
        decision = proto_to_decision_result(proto.decision)

    return SScoreApplicationResponse(
        application_id=proto.application_id,
        score=proto.score,
        pd=proto.pd,
        risk_grade=risk_grade,
        reason_codes=[proto_to_reason_code(rc) for rc in proto.reason_codes],
        model_version=proto.model_version,
        scored_at=timestamp_to_dt(proto.scored_at),
        decision=decision,
    )


def proto_to_schema_batch_response(proto):
    """Конвертирует proto BatchScoreApplicationsResponse в список схем"""
    return [proto_to_schema_response(r) for r in proto.results]


def proto_to_schema_model_info(proto):
    """Конвертирует proto GetModelInfoResponse в SModelInfoResponse"""
    return SModelInfoResponse(
        model_version=proto.model_version,
        model_type=proto.model_type,
        trained_at=timestamp_to_dt(proto.trained_at),
        features=list(proto.features),
        metrics=dict(proto.metrics),
    )