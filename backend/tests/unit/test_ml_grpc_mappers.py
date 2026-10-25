from datetime import datetime, timezone

import pytest

from google.protobuf.timestamp_pb2 import Timestamp

from ml_grpc.generated.simplecredits.scoring.v1 import scoring_pb2
from ml_grpc.mappers import (
    application_to_proto,
    company_to_proto,
    credit_history_to_proto,
    dt_to_timestamp,
    financials_to_proto,
    proto_to_decision_condition,
    proto_to_decision_result,
    proto_to_reason_code,
    proto_to_schema_batch_response,
    proto_to_schema_model_info,
    proto_to_schema_response,
    schema_to_proto_score_request,
    timestamp_to_dt,
)
from schemas.applications import (
    SApplication,
    SCompany,
    SCreditHistory,
    SFinancials,
    SScoreApplicationRequest,
)


def make_application():
    """Возвращает валидную SApplication для тестов"""
    return SApplication(
        product_type="term_loan",
        requested_amount_rub=1500000,
        term_months=24,
        purpose="equipment",
        segment="small",
        submitted_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


def make_company():
    """Возвращает валидную SCompany для тестов"""
    return SCompany(
        inn="7701234567",
        ogrn="1027700132195",
        legal_name="ООО Ромашка",
        legal_form="llc",
        okved="62.01",
        region="Москва",
        registration_date=datetime(2018, 4, 12, tzinfo=timezone.utc),
        employee_count=25,
    )


def make_financials():
    """Возвращает валидную SFinancials для тестов"""
    return SFinancials(
        annual_revenue_rub=42000000,
        annual_net_profit_rub=6500000,
        ebitda_rub=8200000,
        total_debt_rub=3000000,
        monthly_revenue_rub=3500000,
        monthly_expenses_rub=2800000,
        accounts_receivable_rub=1200000,
        cash_balance_rub=900000,
        period_end=datetime(2025, 12, 31, tzinfo=timezone.utc),
    )


def make_credit_history():
    """Возвращает валидную SCreditHistory для тестов"""
    return SCreditHistory(
        active_obligations_count=2,
        total_outstanding_rub=3000000,
        monthly_debt_payments_rub=120000,
        max_days_past_due_12m=0,
        has_current_past_due=False,
        credit_utilization=0.35,
        closed_obligations_count=4,
        applications_last_6m=1,
    )


def make_request():
    """Возвращает полный валидный SScoreApplicationRequest"""
    return SScoreApplicationRequest(
        application=make_application(),
        company=make_company(),
        financials=make_financials(),
        credit_history=make_credit_history(),
    )


def test_dt_to_timestamp_naive():
    """Конвертирует наивный datetime в Timestamp как UTC"""
    dt = datetime(2026, 3, 15, 10, 0, 0)
    ts = dt_to_timestamp(dt)
    assert isinstance(ts, Timestamp)
    assert ts.seconds > 0


def test_dt_to_timestamp_aware():
    """Конвертирует datetime с tzinfo в Timestamp"""
    dt = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    ts = dt_to_timestamp(dt)
    assert ts.ToDatetime(tzinfo=timezone.utc) == dt


def test_timestamp_to_dt_none():
    """Возвращает None для пустого Timestamp"""
    assert timestamp_to_dt(Timestamp()) is None


def test_timestamp_to_dt_none_passed():
    """Возвращает None если передан None"""
    assert timestamp_to_dt(None) is None


def test_timestamp_to_dt_valid():
    """Конвертирует Timestamp обратно в datetime UTC"""
    dt = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    ts = Timestamp()
    ts.FromDatetime(dt)
    assert timestamp_to_dt(ts) == dt


def test_application_to_proto_all_fields():
    """Конвертирует SApplication во все поля proto"""
    proto = application_to_proto(make_application())
    assert proto.product_type == scoring_pb2.PRODUCT_TYPE_TERM_LOAN
    assert proto.requested_amount_rub == 1500000
    assert proto.term_months == 24
    assert proto.purpose == scoring_pb2.FINANCING_PURPOSE_EQUIPMENT
    assert proto.segment == scoring_pb2.BUSINESS_SEGMENT_SMALL
    assert proto.submitted_at.seconds > 0


def test_application_to_proto_each_product_type():
    """Проверяет маппинг всех product_type"""
    pairs = [
        ("microloan", scoring_pb2.PRODUCT_TYPE_MICROLOAN),
        ("term_loan", scoring_pb2.PRODUCT_TYPE_TERM_LOAN),
        ("overdraft", scoring_pb2.PRODUCT_TYPE_OVERDRAFT),
        ("credit_line", scoring_pb2.PRODUCT_TYPE_CREDIT_LINE),
        ("leasing", scoring_pb2.PRODUCT_TYPE_LEASING),
    ]
    for value, expected in pairs:
        data = make_application().model_copy(update={"product_type": value})
        assert application_to_proto(data).product_type == expected


def test_application_to_proto_each_purpose():
    """Проверяет маппинг всех purpose"""
    pairs = [
        ("working_capital", scoring_pb2.FINANCING_PURPOSE_WORKING_CAPITAL),
        ("equipment", scoring_pb2.FINANCING_PURPOSE_EQUIPMENT),
        ("expansion", scoring_pb2.FINANCING_PURPOSE_EXPANSION),
        ("refinancing", scoring_pb2.FINANCING_PURPOSE_REFINANCING),
        ("other", scoring_pb2.FINANCING_PURPOSE_OTHER),
    ]
    for value, expected in pairs:
        data = make_application().model_copy(update={"purpose": value})
        assert application_to_proto(data).purpose == expected


def test_application_to_proto_each_segment():
    """Проверяет маппинг segment"""
    assert application_to_proto(
        make_application().model_copy(update={"segment": "micro"})
    ).segment == scoring_pb2.BUSINESS_SEGMENT_MICRO


def test_application_to_proto_invalid_product_type():
    """Кидает ValueError при неизвестном product_type"""
    data = make_application()
    object.__setattr__(data, "product_type", "unknown")
    with pytest.raises(ValueError, match="product_type"):
        application_to_proto(data)


def test_application_to_proto_invalid_purpose():
    """Кидает ValueError при неизвестном purpose"""
    data = make_application()
    object.__setattr__(data, "purpose", "unknown")
    with pytest.raises(ValueError, match="purpose"):
        application_to_proto(data)


def test_application_to_proto_invalid_segment():
    """Кидает ValueError при неизвестном segment"""
    data = make_application()
    object.__setattr__(data, "segment", "unknown")
    with pytest.raises(ValueError, match="segment"):
        application_to_proto(data)


def test_company_to_proto():
    """Конвертирует SCompany во все поля proto"""
    proto = company_to_proto(make_company())
    assert proto.inn == "7701234567"
    assert proto.ogrn == "1027700132195"
    assert proto.legal_name == "ООО Ромашка"
    assert proto.legal_form == scoring_pb2.LEGAL_FORM_LLC
    assert proto.okved == "62.01"
    assert proto.region == "Москва"
    assert proto.employee_count == 25


def test_company_to_proto_each_legal_form():
    """Проверяет маппинг всех legal_form"""
    pairs = [
        ("llc", scoring_pb2.LEGAL_FORM_LLC),
        ("individual_entrepreneur", scoring_pb2.LEGAL_FORM_INDIVIDUAL_ENTREPRENEUR),
        ("joint_stock_company", scoring_pb2.LEGAL_FORM_JOINT_STOCK_COMPANY),
    ]
    for value, expected in pairs:
        data = make_company().model_copy(update={"legal_form": value})
        assert company_to_proto(data).legal_form == expected


def test_company_to_proto_invalid_legal_form():
    """Кидает ValueError при неизвестном legal_form"""
    data = make_company()
    object.__setattr__(data, "legal_form", "unknown")
    with pytest.raises(ValueError, match="legal_form"):
        company_to_proto(data)


def test_financials_to_proto():
    """Конвертирует SFinancials во все поля proto"""
    proto = financials_to_proto(make_financials())
    assert proto.annual_revenue_rub == 42000000
    assert proto.annual_net_profit_rub == 6500000
    assert proto.ebitda_rub == 8200000
    assert proto.period_end.seconds > 0


def test_financials_to_proto_negative_profit():
    """Принимает отрицательный annual_net_profit_rub"""
    data = make_financials().model_copy(update={"annual_net_profit_rub": -1000000})
    assert financials_to_proto(data).annual_net_profit_rub == -1000000


def test_credit_history_to_proto():
    """Конвертирует SCreditHistory во все поля proto"""
    proto = credit_history_to_proto(make_credit_history())
    assert proto.active_obligations_count == 2
    assert proto.credit_utilization == pytest.approx(0.35)
    assert proto.has_current_past_due is False


def test_schema_to_proto_score_request():
    """Собирает proto ScoreApplicationRequest с application_id"""
    proto = schema_to_proto_score_request(make_request(), "abc123")
    assert proto.application_id == "abc123"
    assert proto.application.term_months == 24
    assert proto.company.inn == "7701234567"
    assert proto.financials.annual_revenue_rub == 42000000
    assert proto.credit_history.active_obligations_count == 2


def test_schema_to_proto_score_request_carries_extra_features():
    """extra_*_features из обогащения доходят до proto"""
    request = make_request()
    request = request.model_copy(
        update={
            "extra_numeric_features": {"bki_credit_score": 742.0, "tax_debt_rub": 15000.0},
            "extra_categorical_features": {"tax_regime": "usn"},
        }
    )

    proto = schema_to_proto_score_request(request, "abc-extra")

    assert proto.extra_numeric_features["bki_credit_score"] == 742.0
    assert proto.extra_numeric_features["tax_debt_rub"] == 15000.0
    assert proto.extra_categorical_features["tax_regime"] == "usn"


def test_schema_to_proto_score_request_extra_features_default_empty():
    """Без extra_*_features в proto уходят пустые map'ы, а не ошибка"""
    proto = schema_to_proto_score_request(make_request(), "abc-empty")

    assert dict(proto.extra_numeric_features) == {}
    assert dict(proto.extra_categorical_features) == {}


def test_proto_to_reason_code_positive():
    """Конвертирует proto ReasonCode с positive impact"""
    proto = scoring_pb2.ReasonCode(
        code="RC001",
        description="Стабильная история",
        feature="max_days_past_due_12m",
        impact=scoring_pb2.REASON_IMPACT_POSITIVE,
        contribution=-0.12,
    )
    result = proto_to_reason_code(proto)
    assert result.code == "RC001"
    assert result.impact == "positive"
    assert result.contribution == pytest.approx(-0.12)


def test_proto_to_reason_code_negative():
    """Конвертирует proto ReasonCode с negative impact"""
    proto = scoring_pb2.ReasonCode(
        code="RC002",
        description="Просрочка",
        feature="has_current_past_due",
        impact=scoring_pb2.REASON_IMPACT_NEGATIVE,
        contribution=0.5,
    )
    assert proto_to_reason_code(proto).impact == "negative"


def test_proto_to_reason_code_neutral():
    """Конвертирует proto ReasonCode с neutral impact"""
    proto = scoring_pb2.ReasonCode(impact=scoring_pb2.REASON_IMPACT_NEUTRAL)
    assert proto_to_reason_code(proto).impact == "neutral"


def test_proto_to_reason_code_invalid_impact():
    """Кидает ValueError при неизвестном impact"""
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="impact"):
        proto_to_reason_code(SimpleNamespace(impact=99))


def test_proto_to_decision_condition():
    """Конвертирует proto DecisionCondition в схему"""
    proto = scoring_pb2.DecisionCondition(
        code="C001",
        description="Уменьшить сумму",
        recommended_amount_rub=500000,
    )
    result = proto_to_decision_condition(proto)
    assert result.code == "C001"
    assert result.recommended_amount_rub == 500000


def test_proto_to_decision_result_approve():
    """Конвертирует decision=approve"""
    proto = scoring_pb2.DecisionResult(
        decision=scoring_pb2.DECISION_APPROVE,
        reason_codes=["RC001"],
    )
    result = proto_to_decision_result(proto)
    assert result.decision == "approve"
    assert result.reason_codes == ["RC001"]
    assert result.conditions == []


def test_proto_to_decision_result_approve_with_conditions():
    """Конвертирует decision=approve_with_conditions с условиями"""
    proto = scoring_pb2.DecisionResult(
        decision=scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS,
        conditions=[
            scoring_pb2.DecisionCondition(code="C1", recommended_amount_rub=100000),
        ],
    )
    result = proto_to_decision_result(proto)
    assert result.decision == "approve_with_conditions"
    assert len(result.conditions) == 1


def test_proto_to_decision_result_manual_review():
    """Конвертирует decision=manual_review"""
    proto = scoring_pb2.DecisionResult(decision=scoring_pb2.DECISION_MANUAL_REVIEW)
    assert proto_to_decision_result(proto).decision == "manual_review"


def test_proto_to_decision_result_decline():
    """Конвертирует decision=decline"""
    proto = scoring_pb2.DecisionResult(decision=scoring_pb2.DECISION_DECLINE)
    assert proto_to_decision_result(proto).decision == "decline"


def test_proto_to_decision_result_invalid():
    """Кидает ValueError при неизвестном decision"""
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="decision"):
        proto_to_decision_result(SimpleNamespace(decision=99))


def test_proto_to_schema_response_full():
    """Конвертирует полный proto-ответ в схему"""
    ts = Timestamp()
    ts.FromDatetime(datetime(2026, 3, 15, 10, 0, 1, tzinfo=timezone.utc))

    proto = scoring_pb2.ScoreApplicationResponse(
        application_id="abc123",
        score=712,
        pd=0.0421,
        risk_grade=scoring_pb2.RISK_GRADE_B,
        reason_codes=[
            scoring_pb2.ReasonCode(
                code="RC001",
                impact=scoring_pb2.REASON_IMPACT_POSITIVE,
            ),
        ],
        model_version="v1.0.0",
        scored_at=ts,
        decision=scoring_pb2.DecisionResult(
            decision=scoring_pb2.DECISION_APPROVE,
        ),
    )

    result = proto_to_schema_response(proto)
    assert result.application_id == "abc123"
    assert result.score == 712
    assert result.risk_grade == "B"
    assert len(result.reason_codes) == 1
    assert result.decision is not None
    assert result.decision.decision == "approve"


def test_proto_to_schema_response_no_decision():
    """Возвращает decision=None если поле не установлено"""
    proto = scoring_pb2.ScoreApplicationResponse(
        application_id="abc",
        risk_grade=scoring_pb2.RISK_GRADE_A,
    )
    assert proto_to_schema_response(proto).decision is None


def test_proto_to_schema_response_each_risk_grade():
    """Проверяет маппинг всех risk_grade"""
    pairs = [
        (scoring_pb2.RISK_GRADE_A, "A"),
        (scoring_pb2.RISK_GRADE_B, "B"),
        (scoring_pb2.RISK_GRADE_C, "C"),
        (scoring_pb2.RISK_GRADE_D, "D"),
        (scoring_pb2.RISK_GRADE_E, "E"),
    ]
    for proto_value, expected in pairs:
        proto = scoring_pb2.ScoreApplicationResponse(risk_grade=proto_value)
        assert proto_to_schema_response(proto).risk_grade == expected


def test_proto_to_schema_response_invalid_risk_grade():
    """Кидает ValueError при неизвестном risk_grade"""
    from types import SimpleNamespace

    with pytest.raises(ValueError, match="risk_grade"):
        proto_to_schema_response(SimpleNamespace(risk_grade=99))


def test_proto_to_schema_batch_response():
    """Конвертирует пакетный ответ в список схем"""
    response = scoring_pb2.BatchScoreApplicationsResponse(
        results=[
            scoring_pb2.ScoreApplicationResponse(
                application_id="a", risk_grade=scoring_pb2.RISK_GRADE_A
            ),
            scoring_pb2.ScoreApplicationResponse(
                application_id="b", risk_grade=scoring_pb2.RISK_GRADE_B
            ),
        ]
    )
    result = proto_to_schema_batch_response(response)
    assert len(result) == 2
    assert result[0].application_id == "a"
    assert result[1].risk_grade == "B"


def test_proto_to_schema_batch_response_empty():
    """Возвращает пустой список для пустого батча"""
    response = scoring_pb2.BatchScoreApplicationsResponse()
    assert proto_to_schema_batch_response(response) == []


def test_proto_to_schema_model_info():
    """Конвертирует информацию о модели"""
    ts = Timestamp()
    ts.FromDatetime(datetime(2026, 1, 1, tzinfo=timezone.utc))

    proto = scoring_pb2.GetModelInfoResponse(
        model_version="v1.0.0",
        model_type="logistic_regression",
        trained_at=ts,
        features=["income", "age"],
        metrics={"auc": 0.82, "ks": 0.35},
    )

    result = proto_to_schema_model_info(proto)
    assert result.model_version == "v1.0.0"
    assert result.model_type == "logistic_regression"
    assert result.features == ["income", "age"]
    assert result.metrics["auc"] == pytest.approx(0.82)


def test_proto_to_schema_model_info_no_trained_at():
    """Возвращает trained_at=None если поле не установлено"""
    proto = scoring_pb2.GetModelInfoResponse(model_version="v1")
    assert proto_to_schema_model_info(proto).trained_at is None