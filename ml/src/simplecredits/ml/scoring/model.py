from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from simplecredits.ml.data.schema import normalize_raw_row
from simplecredits.ml.features.features import build_features
from simplecredits.ml.scoring.policy import PolicyDecision, evaluate_policy
from simplecredits.ml.scoring.reasons import compute_reasons

RISK_GRADE_THRESHOLDS: tuple[tuple[str, float], ...] = (
    ("A", 0.02),
    ("B", 0.05),
    ("C", 0.10),
    ("D", 0.20),
    ("E", 1.01),
)


@dataclass(frozen=True)
class ScoreResult:
    score: int
    pd: float
    risk_grade: str
    reasons: list[dict]
    model_version: str
    policy: PolicyDecision


def pd_to_risk_grade(pd_value: float) -> str:
    for grade, threshold in RISK_GRADE_THRESHOLDS:
        if pd_value < threshold:
            return grade
    return "E"


def pd_to_score(pd_value: float) -> int:
    return max(0, min(1000, int(round((1.0 - pd_value) * 1000))))


class CreditScorer:
    def __init__(self, artifact: dict):
        self.artifact = artifact
        self.pipeline = artifact["pipeline"]
        self.model_version = artifact.get("model_version", "unknown")
        self.feature_columns = artifact.get("feature_columns")
        self.preprocessor = self.pipeline.named_steps["preprocessor"]
        self.classifier = self.pipeline.named_steps["classifier"]

    @classmethod
    def load(cls, path: str | Path) -> "CreditScorer":
        artifact = joblib.load(Path(path))
        return cls(artifact)

    def predict_pd(self, raw_row: dict) -> float:
        features = build_features(pd.DataFrame([normalize_raw_row(raw_row)]))
        if self.feature_columns is not None:
            features = features[self.feature_columns]
        probability = self.pipeline.predict_proba(features)[0][1]
        return float(probability)

    def score(self, raw_row: dict, top_reasons: int = 5) -> ScoreResult:
        normalized = normalize_raw_row(raw_row)
        features = build_features(pd.DataFrame([normalized]))
        if self.feature_columns is not None:
            features = features[self.feature_columns]

        pd_value = float(self.pipeline.predict_proba(features)[0][1])
        risk_grade = pd_to_risk_grade(pd_value)
        reasons = compute_reasons(self.preprocessor, self.classifier, features, top_k=top_reasons)
        return ScoreResult(
            score=pd_to_score(pd_value),
            pd=pd_value,
            risk_grade=risk_grade,
            reasons=reasons,
            model_version=self.model_version,
            policy=evaluate_policy(normalized, pd_value),
        )

    def model_info(self) -> dict:
        return {
            "model_version": self.model_version,
            "model_type": self.artifact.get("model_type", "logistic_scorecard"),
            "trained_at": self.artifact.get("trained_at"),
            "metrics": self.artifact.get("metrics", {}),
            "feature_columns": list(self.feature_columns or []),
            "training": self.artifact.get("training", {}),
        }
