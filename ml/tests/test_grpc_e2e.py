import json
from concurrent import futures
from pathlib import Path

import grpc
import pytest
from google.protobuf import json_format

from simplecredits.ml.serving.server import ScoringService
from simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def load_request(name: str) -> scoring_pb2.ScoreApplicationRequest:
    payload = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    return json_format.ParseDict(payload, scoring_pb2.ScoreApplicationRequest())


@pytest.fixture(scope="module")
def stub(scorer):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    scoring_pb2_grpc.add_ScoringServiceServicer_to_server(ScoringService(scorer), server)
    port = server.add_insecure_port("localhost:0")
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    try:
        yield scoring_pb2_grpc.ScoringServiceStub(channel)
    finally:
        channel.close()
        server.stop(0)


def test_grpc_scores_approved_application(stub):
    response = stub.ScoreApplication(load_request("good_application.json"))
    assert response.application_id == "demo-good-001"
    assert response.risk_grade == scoring_pb2.RISK_GRADE_A
    assert response.decision.decision == scoring_pb2.DECISION_APPROVE
    assert response.reason_codes
    assert response.scored_at.ToSeconds() > 0


def test_grpc_declines_problem_application(stub):
    response = stub.ScoreApplication(load_request("bad_application.json"))
    assert response.decision.decision == scoring_pb2.DECISION_DECLINE
    assert "CURRENT_PAST_DUE" in response.decision.reason_codes


def test_grpc_offers_conditions(stub):
    response = stub.ScoreApplication(load_request("medium_application.json"))
    assert response.decision.decision == scoring_pb2.DECISION_APPROVE_WITH_CONDITIONS
    assert response.decision.conditions[0].recommended_amount_rub == 10_000_000


def test_grpc_batch_and_model_info(stub):
    request = scoring_pb2.BatchScoreApplicationsRequest(
        applications=[
            load_request("good_application.json"),
            load_request("bad_application.json"),
        ]
    )
    response = stub.BatchScoreApplications(request)
    assert len(response.results) == 2
    assert response.results[0].score > response.results[1].score

    info = stub.GetModelInfo(scoring_pb2.GetModelInfoRequest())
    assert info.model_version == "scorecard-linear-v1"
    assert info.features
    assert "roc_auc_test" in info.metrics
    assert info.trained_at.ToSeconds() > 0
