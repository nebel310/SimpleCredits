from __future__ import annotations

from typing import Any

import joblib
import pandas as pd
from mlflow.pyfunc import PythonModel

from simplecredits.ml.scoring.model import CreditScorer


def score_frame(scorer: CreditScorer, frame: pd.DataFrame) -> pd.DataFrame:
    records = []
    for row in pd.DataFrame(frame).to_dict("records"):
        result = scorer.score(row)
        records.append(
            {
                "score": result.score,
                "pd": result.pd,
                "risk_grade": result.risk_grade,
                "decision": result.policy.decision,
                "decision_reasons": "|".join(result.policy.reasons),
                "model_version": result.model_version,
            }
        )
    return pd.DataFrame(records)


class CreditScorerPyfunc(PythonModel):
    def load_context(self, context: Any) -> None:
        artifact = joblib.load(context.artifacts["scorer"])
        self.scorer = CreditScorer(artifact)

    def predict(
        self,
        context: Any,
        model_input: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        return score_frame(self.scorer, pd.DataFrame(model_input))
