from google.protobuf.timestamp_pb2 import Timestamp

from simplecredits.ml.scoring.model import ScoreResult
from simplecredits.ml.scoring.policy import PolicyDecision
from simplecredits.ml.serving.server import request_to_raw_row, to_response
from simplecredits.scoring.v1 import scoring_pb2


def test_request_to_raw_row_maps_proto_fields():
    registration = Timestamp()
    registration.GetCurrentTime()

    request = scoring_pb2.ScoreApplicationRequest(
        application_id="app-1",
        application=scoring_pb2.Application(
            product_type=scoring_pb2.PRODUCT_TYPE_OVERDRAFT,
            requested_amount_rub=2_000_000,
            term_months=12,
            purpose=scoring_pb2.FINANCING_PURPOSE_EQUIPMENT,
        ),
        company=scoring_pb2.Company(
            inn="7700000000",
            employee_count=12,
            registration_date=registration,
        ),
        financials=scoring_pb2.Financials(
            annual_revenue_rub=24_000_000,
            annual_net_profit_rub=2_000_000,
            monthly_revenue_rub=2_000_000,
            monthly_expenses_rub=1_700_000,
        ),
        credit_history=scoring_pb2.CreditHistory(
            active_obligations_count=1,
            monthly_debt_payments_rub=100_000,
            has_current_past_due=False,
            credit_utilization=0.3,
        ),
    )

    row = request_to_raw_row(request)
    assert row["product_type"] == "overdraft"
    assert row["purpose"] == "equipment"
    assert row["requested_amount_rub"] == 2_000_000
    assert row["employee_count"] == 12
    assert row["has_current_past_due"] is False
    assert row["company_age_months"] == 0

def test_to_response_maps_policy_decision():
    result = ScoreResult(
        score=900,
        pd=0.08,
        risk_grade="C",
        reasons=[
            {
                "code": "DEBT_BURDEN",
                "description": "Высокая долговая нагрузка",
                "feature": "debt_to_revenue",
                "impact": "negative",
                "contribution": 0.5,
            }
        ],
        model_version="test-model",
        policy=PolicyDecision(
            decision="manual_review",
            reasons=("HIGH_DEBT_SERVICE_RATIO",),
        ),
    )

    response = to_response("app-2", result)
    assert response.application_id == "app-2"
    assert response.risk_grade == scoring_pb2.RISK_GRADE_C
    assert response.decision.decision == scoring_pb2.DECISION_MANUAL_REVIEW
    assert list(response.decision.reason_codes) == ["HIGH_DEBT_SERVICE_RATIO"]
    assert response.reason_codes[0].impact == scoring_pb2.REASON_IMPACT_NEGATIVE
