import pytest

pytest.importorskip("catboost")

from simplecredits.ml.scoring.model import CreditScorer
from simplecredits.ml.training.catboost import train_catboost_model
from tests.test_scoring import BAD_APPLICATION, GOOD_APPLICATION


def test_catboost_training_and_scoring():
    artifact = train_catboost_model(n_samples=600, seed=7)
    scorer = CreditScorer(artifact)

    good = scorer.score(GOOD_APPLICATION)
    bad = scorer.score(BAD_APPLICATION)

    assert artifact["metrics"]["roc_auc_test"] > 0.5
    assert good.pd < bad.pd
    assert good.score > bad.score
    assert good.risk_grade in {"A", "B", "C", "D", "E"}
    assert good.reasons
    assert bad.reasons
    assert good.model_version == "catboost-v1"
    assert scorer.model_info()["model_type"] == "catboost"
