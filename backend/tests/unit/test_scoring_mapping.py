from datetime import datetime, timezone

from simplecredits.scoring.v1 import scoring_pb2

from schemas.scoring import SScoreApplicationRequest
from scoring.mapping import (
    from_proto_model_info,
    from_proto_response,
    to_proto_request,
)


def make_request() -> SScoreApplicationRequest:
    return SScoreApplicationRequest.model_validate(
        {
            "application_id": "test-001",
            "application": {
                "product_type": "PRODUCT_TYPE_TERM_LOAN",
                "requested_amount_rub": 3000000,
                "term_months": 24,
                "purpose": "FINANCING_PURPOSE_EQUIPMENT",
                "segment": "BUSINESS_SEGMENT_SMALL",
                "submitted_at": "2026-01-01T10:00:00Z",
            },
            "company": {
                "inn": "7700000001",
                "ogrn": "1167746000001",
                "legal_name": "Тестовая компания",
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
    )


def test_to_proto_request_maps_nested_fields_and_enums():
    message = to_proto_request(make_request())

    assert message.application_id == "test-001"
    assert message.application.product_type == scoring_pb2.PRODUCT_TYPE_TERM_LOAN
    assert message.application.purpose == scoring_pb2.FINANCING_PURPOSE_EQUIPMENT
    assert message.application.segment == scoring_pb2.BUSINESS_SEGMENT_SMALL
    assert message.application.requested_amount_rub == 3000000
    assert message.company.legal_form == scoring_pb2.LEGAL_FORM_LLC
    assert message.company.employee_count == 30
    assert message.financials.annual_revenue_rub == 120000000
    assert message.credit_history.monthly_debt_payments_rub == 150000


def test_to_proto_request_maps_timestamps():
    message = to_proto_request(make_request())

    assert message.application.submitted_at.ToDatetime(tzinfo=timezone.utc) == datetime(
        2026, 1, 1, 10, tzinfo=timezone.utc
    )
    assert message.company.registration_date.ToDatetime(tzinfo=timezone.utc) == datetime(
        2016, 5, 10, tzinfo=timezone.utc
    )
    assert message.financials.period_end.ToDatetime(tzinfo=timezone.utc) == datetime(
        2025, 12, 31, tzinfo=timezone.utc
    )


def test_from_proto_response_maps_score_decision_and_reasons():
    proto = scoring_pb2.ScoreApplicationResponse(
        application_id="test-001",
        score=842,
        pd=0.158,
        risk_grade=scoring_pb2.RISK_GRADE_C,
        model_version="scorecard-linear-v1",
        reason_codes=[
            scoring_pb2.ReasonCode(
                code="HIGH_UTILIZATION",
                description="Высокая загрузка",
                feature="credit_utilization",
                impact=scoring_pb2.REASON_IMPACT_NEGATIVE,
                contribution=-0.14,
            )
        ],
        decision=scoring_pb2.DecisionResult(
            decision=scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS,
            reason_codes=["REDUCE_AMOUNT"],
            conditions=[
                scoring_pb2.DecisionCondition(
                    code="REDUCE_AMOUNT",
                    description="Уменьшить сумму",
                    recommended_amount_rub=2000000,
                )
            ],
        ),
    )
    proto.scored_at.FromDatetime(datetime(2026, 1, 1, tzinfo=timezone.utc))

    response = from_proto_response(proto)

    assert response.application_id == "test-001"
    assert response.score == 842
    assert response.risk_grade == "RISK_GRADE_C"
    assert response.reason_codes[0].impact == "REASON_IMPACT_NEGATIVE"
    assert response.decision.decision == "DECISION_APPROVE_WITH_CONDITIONS"
    assert response.decision.conditions[0].recommended_amount_rub == 2000000
    assert response.scored_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_from_proto_model_info_maps_metrics_and_features():
    proto = scoring_pb2.GetModelInfoResponse(
        model_version="scorecard-linear-v1",
        model_type="logistic_scorecard",
        features=["annual_revenue_rub", "credit_utilization"],
        metrics={"roc_auc": 0.8648, "gini": 0.7297},
    )
    proto.trained_at.FromDatetime(datetime(2026, 1, 1, tzinfo=timezone.utc))

    info = from_proto_model_info(proto)

    assert info.model_version == "scorecard-linear-v1"
    assert info.features == ["annual_revenue_rub", "credit_utilization"]
    assert info.metrics["roc_auc"] == 0.8648
    assert info.trained_at == datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_invalid_enum_is_rejected():
    payload = make_request().model_dump()
    payload["application"]["product_type"] = "term_loan"

    try:
        SScoreApplicationRequest.model_validate(payload)
    except ValueError:
        return
    raise AssertionError("expected validation error")
