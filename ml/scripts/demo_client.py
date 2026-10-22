from __future__ import annotations

import argparse
import json
from pathlib import Path

import grpc
from google.protobuf import json_format

from simplecredits.scoring.v1 import scoring_pb2, scoring_pb2_grpc

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXAMPLES = [
    REPO_ROOT / "examples" / "good_application.json",
    REPO_ROOT / "examples" / "medium_application.json",
    REPO_ROOT / "examples" / "review_application.json",
    REPO_ROOT / "examples" / "bad_application.json",
]


def show_model_info(stub: scoring_pb2_grpc.ScoringServiceStub) -> None:
    info = stub.GetModelInfo(scoring_pb2.GetModelInfoRequest())
    print(f"model: {info.model_version} ({info.model_type})")
    print(f"features: {len(info.features)}")
    for name, value in info.metrics.items():
        print(f"  {name}: {value}")
    print()


def score_file(stub: scoring_pb2_grpc.ScoringServiceStub, path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = json_format.ParseDict(payload, scoring_pb2.ScoreApplicationRequest())
    response = stub.ScoreApplication(request)
    grade = scoring_pb2.RiskGrade.Name(response.risk_grade).removeprefix("RISK_GRADE_")
    decision = scoring_pb2.Decision.Name(response.decision.decision).removeprefix("DECISION_")
    print(
        f"{path.name}: score={response.score} pd={response.pd:.4f} "
        f"grade={grade} decision={decision}"
    )
    for reason in response.reason_codes:
        impact = scoring_pb2.ReasonImpact.Name(reason.impact).removeprefix("REASON_IMPACT_")
        print(f"  [{impact}] {reason.description} ({reason.contribution:.4f})")
    for reason in response.decision.reason_codes:
        print(f"  policy: {reason}")
    for condition in response.decision.conditions:
        print(f"  condition: {condition.code} -> {condition.recommended_amount_rub}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Call the SimpleCredits scoring service")
    parser.add_argument("--target", default="localhost:50051")
    parser.add_argument("files", nargs="*", type=Path, default=DEFAULT_EXAMPLES)
    args = parser.parse_args()

    with grpc.insecure_channel(args.target) as channel:
        stub = scoring_pb2_grpc.ScoringServiceStub(channel)
        show_model_info(stub)
        for path in args.files:
            score_file(stub, path)


if __name__ == "__main__":
    main()
