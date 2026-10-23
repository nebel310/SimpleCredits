from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from router.scoring import get_model_info, score_application
from schemas.scoring import (
    SDecisionResult,
    SModelInfoResponse,
    SScoreApplicationResponse,
)
from scoring.client import (
    ScoringResponseError,
    ScoringUnavailableError,
)
from tests.unit.test_scoring_mapping import make_request


class FakeScoringClient:
    def __init__(self, response: SScoreApplicationResponse | None = None):
        self.response = response

    async def score(self, request):
        return self.response

    async def model_info(self):
        return SModelInfoResponse(
            model_version="scorecard-linear-v1",
            model_type="logistic_scorecard",
            features=["annual_revenue_rub"],
            metrics={"roc_auc": 0.8648},
        )


class FailingScoringClient:
    def __init__(self, error: Exception):
        self.error = error

    async def score(self, request):
        raise self.error

    async def model_info(self):
        raise self.error


def make_response() -> SScoreApplicationResponse:
    return SScoreApplicationResponse(
        application_id="test-001",
        score=842,
        pd=0.158,
        risk_grade="RISK_GRADE_C",
        reason_codes=[],
        model_version="scorecard-linear-v1",
        scored_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        decision=SDecisionResult(
            decision="DECISION_APPROVE_WITH_CONDITIONS",
            reason_codes=["REDUCE_AMOUNT"],
        ),
    )


@pytest.mark.asyncio
async def test_score_application_returns_client_response():
    response = make_response()

    result = await score_application(
        make_request(),
        object(),
        FakeScoringClient(response),
    )

    assert result is response


@pytest.mark.asyncio
async def test_get_model_info_returns_client_response():
    result = await get_model_info(object(), FakeScoringClient())

    assert result.model_version == "scorecard-linear-v1"


@pytest.mark.asyncio
async def test_score_application_maps_unavailable_to_503():
    with pytest.raises(HTTPException) as error:
        await score_application(
            make_request(),
            object(),
            FailingScoringClient(ScoringUnavailableError("down")),
        )

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_score_application_maps_ml_error_to_502():
    with pytest.raises(HTTPException) as error:
        await score_application(
            make_request(),
            object(),
            FailingScoringClient(ScoringResponseError("bad response")),
        )

    assert error.value.status_code == 502
