import socket
import sys
from types import SimpleNamespace

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from simplecredits.ml.scoring.model import ScoreResult
from simplecredits.ml.scoring.policy import PolicyDecision
from simplecredits.ml.serving.server import (
    ScoringService,
    create_server,
    ensure_model,
    main as run_server,
    to_response,
)
from simplecredits.ml.training.train import save_model
from simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def grpc_channel(scorer):
    port = free_port()
    server = create_server(scorer, port=port, max_workers=2)
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    grpc.channel_ready_future(channel).result(timeout=5)
    try:
        yield channel
    finally:
        channel.close()
        server.stop(0)


def test_create_server_exposes_health_status(grpc_channel):
    health = health_pb2_grpc.HealthStub(grpc_channel)
    response = health.Check(
        health_pb2.HealthCheckRequest(
            service="simplecredits.scoring.v1.ScoringService"
        )
    )
    assert response.status == health_pb2.HealthCheckResponse.SERVING


def test_score_application_reports_invalid_features(grpc_channel):
    stub = scoring_pb2_grpc.ScoringServiceStub(grpc_channel)
    request = scoring_pb2.ScoreApplicationRequest(
        application_id="bad-features",
        extra_numeric_features={"unknown": 1.0},
    )

    with pytest.raises(grpc.RpcError) as error:
        stub.ScoreApplication(request)

    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "unknown numeric features" in error.value.details()


def test_batch_score_reports_invalid_features(grpc_channel):
    stub = scoring_pb2_grpc.ScoringServiceStub(grpc_channel)
    valid = scoring_pb2.ScoreApplicationRequest(application_id="valid")
    invalid = scoring_pb2.ScoreApplicationRequest(
        application_id="invalid",
        extra_categorical_features={"unknown": "x"},
    )

    with pytest.raises(grpc.RpcError) as error:
        stub.BatchScoreApplications(
            scoring_pb2.BatchScoreApplicationsRequest(applications=[valid, invalid])
        )

    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "unknown categorical features" in error.value.details()


def test_get_model_info_accepts_naive_timestamp():
    scorer = SimpleNamespace(
        model_info=lambda: {
            "model_version": "test-v1",
            "model_type": "test",
            "feature_columns": ["feature"],
            "metrics": {"roc_auc_test": 0.5},
            "trained_at": "2026-01-01T00:00:00",
        }
    )

    response = ScoringService(scorer).GetModelInfo(None, None)

    assert response.model_version == "test-v1"
    assert response.trained_at.ToSeconds() > 0


def test_to_response_uses_safe_fallbacks():
    result = ScoreResult(
        score=500,
        pd=0.5,
        risk_grade="unknown",
        reasons=[
            {
                "code": "CUSTOM",
                "description": "custom",
                "feature": "custom_feature",
                "impact": "unknown",
                "contribution": 0.1,
            }
        ],
        model_version="test-v1",
        policy=PolicyDecision(
            decision="unknown",
            reasons=("CUSTOM",),
            conditions=({"code": "CUSTOM_CONDITION"},),
        ),
    )

    response = to_response("app-1", result)

    assert response.risk_grade == scoring_pb2.RISK_GRADE_E
    assert response.decision.decision == scoring_pb2.DECISION_UNSPECIFIED
    assert response.reason_codes[0].impact == scoring_pb2.REASON_IMPACT_NEUTRAL
    assert response.decision.conditions[0].recommended_amount_rub == 0


def test_ensure_model_loads_existing_artifact(tmp_path, scorer):
    artifact_path = save_model(scorer.artifact, tmp_path / "model.joblib")

    loaded = ensure_model(artifact_path)

    assert loaded.model_version == scorer.model_version
    assert loaded.feature_columns == scorer.feature_columns


def test_ensure_model_trains_fallback_artifact(tmp_path, monkeypatch, scorer):
    artifact_path = tmp_path / "missing" / "model.joblib"
    monkeypatch.setattr(
        "simplecredits.ml.serving.server.train_catboost_model",
        lambda **_: scorer.artifact,
    )

    loaded = ensure_model(artifact_path)

    assert artifact_path.exists()
    assert loaded.model_version == scorer.model_version
    assert loaded.model_type == scorer.model_type


def test_server_main_stops_on_keyboard_interrupt(monkeypatch, scorer):
    stopped = {}

    class FakeServer:
        def start(self):
            self.started = True

        def wait_for_termination(self):
            raise KeyboardInterrupt

        def stop(self, grace):
            stopped["grace"] = grace

    fake_server = FakeServer()
    monkeypatch.setattr(sys, "argv", ["simplecredits-scoring", "--port", "50051"])
    monkeypatch.setattr(
        "simplecredits.ml.serving.server.ensure_model",
        lambda _: scorer,
    )
    monkeypatch.setattr(
        "simplecredits.ml.serving.server.create_server",
        lambda *_args, **_kwargs: fake_server,
    )

    run_server()

    assert fake_server.started is True
    assert stopped["grace"] == 2
