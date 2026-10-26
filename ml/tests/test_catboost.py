import json
import sys

import pandas as pd
import pytest

pytest.importorskip("catboost")

from catboost import CatBoostClassifier

import simplecredits.ml.tracking as tracking
from simplecredits.ml.data.generator import generate_dataset
from simplecredits.ml.features.features import build_features
from simplecredits.ml.scoring.model import CatBoostProbabilityModel, CreditScorer
from simplecredits.ml.training.catboost import (
    CATBOOST_MODEL_VERSION,
    CATBOOST_PARAMS,
    _split_dataset,
    _training_params,
    main,
    train_catboost_model,
    train_catboost_model_with_evaluation,
)
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
    assert good.model_version == CATBOOST_MODEL_VERSION
    assert scorer.model_info()["model_type"] == "catboost"


def test_catboost_reasons_survive_narrower_cat_features():
    """Артефакт с узким набором категориальных признаков остаётся скоримым.

    Раньше compute_catboost_reasons строил Pool по глобальному CATEGORICAL_FEATURES,
    поэтому артефакт, обученный на меньшем числе категориальных колонок, падал с
    ValueError вроде "'company_segment' is not in list".
    """
    data = generate_dataset(n_samples=300, seed=11)
    features = build_features(data)
    target = data["default"].astype(int)

    # Обучаем только на двух категориальных признаках, как в старых артефактах.
    narrow_columns = [c for c in features.columns if c not in {"company_segment", "legal_form", "tax_regime", "client_rating"}]
    model = CatBoostClassifier(
        iterations=30,
        depth=2,
        learning_rate=0.1,
        loss_function="Logloss",
        random_seed=11,
        verbose=False,
        allow_writing_files=False,
        cat_features=["product_type", "purpose"],
    )
    model.fit(features[narrow_columns], target)

    artifact = {
        "model": model,
        "pipeline": CatBoostProbabilityModel(model),
        "model_version": "catboost-v1",
        "model_type": "catboost",
        "feature_columns": narrow_columns,
    }
    scorer = CreditScorer(artifact)

    result = scorer.score(GOOD_APPLICATION)

    assert result.reasons
    assert result.model_version == "catboost-v1"


def test_split_keeps_companies_disjoint():
    """Компания целиком попадает либо в train, либо в test — иначе утечка."""
    data = generate_dataset(n_samples=800, seed=5)
    companies = [f"cmp-{i % 120}" for i in range(len(data))]
    data["company_id"] = companies

    features_train, features_test, target_train, target_test = _split_dataset(
        data, seed=5, test_size=0.25
    )

    train_ids = set(data.loc[features_train.index, "company_id"])
    test_ids = set(data.loc[features_test.index, "company_id"])
    assert train_ids & test_ids == set()
    assert len(features_train) + len(features_test) == len(data)
    assert target_train.isin((0, 1)).all() and target_test.isin((0, 1)).all()


def test_training_records_grouped_split_metadata():
    """При наличии company_id сплит групповой, и это отражено в метаданных."""
    data = generate_dataset(n_samples=1200, seed=9)
    data["company_id"] = [f"cmp-{i % 150}" for i in range(len(data))]

    artifact = train_catboost_model(frame=data, seed=9, test_size=0.25)

    assert artifact["model_version"] == CATBOOST_MODEL_VERSION
    assert artifact["metrics"]["roc_auc_test"] > 0.5
    assert artifact["training"]["split"] == "grouped_by_company"
    assert artifact["training"]["n_companies"] == 150
    assert artifact["training"]["n_train"] + artifact["training"]["n_test"] == len(data)
    # early stopping не используется: итерации фиксированы CATBOOST_PARAMS
    assert artifact["training"]["params"]["iterations"] == CATBOOST_PARAMS["iterations"]


def test_training_falls_back_to_stratified_split_without_groups():
    """Синтетика без company_id обучается стратифицированным случайным сплитом."""
    data = generate_dataset(n_samples=600, seed=3)
    assert "company_id" not in data.columns

    artifact = train_catboost_model(frame=data, seed=3, test_size=0.25)

    assert artifact["training"]["split"] == "stratified_random"
    assert artifact["training"]["n_companies"] is None
    assert artifact["metrics"]["roc_auc_test"] > 0.5


def test_catboost_training_with_evaluation_returns_evaluation_and_data():
    artifact, evaluation, data = train_catboost_model_with_evaluation(
        n_samples=500,
        seed=13,
        params={"iterations": 25},
    )

    assert len(data) == 500
    assert artifact["model_version"] == CATBOOST_MODEL_VERSION
    assert artifact["training"]["params"]["iterations"] == 25
    assert 0.0 <= evaluation["metrics"]["roc_auc_test"] <= 1.0
    assert evaluation["policy_summary"]["counts"]
    assert len(evaluation["train_predictions"]) + len(evaluation["test_predictions"]) == 500


def test_catboost_training_params_describe_source():
    artifact = train_catboost_model(n_samples=400, seed=7, params={"iterations": 20})
    params = _training_params(artifact, "file")

    assert params["data_source"] == "file"
    assert params["model_version"] == CATBOOST_MODEL_VERSION
    assert params["n_samples"] == 400
    assert params["n_train"] + params["n_test"] == 400
    assert "cat_features" not in params


def test_catboost_cli_writes_model_without_tracking(tmp_path, monkeypatch, capsys):
    output = tmp_path / "catboost.joblib"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-catboost",
            "--samples",
            "400",
            "--iterations",
            "20",
            "--seed",
            "7",
            "--out",
            str(output),
            "--no-tracking",
        ],
    )

    main()

    payload = json.loads(capsys.readouterr().out)
    assert output.exists()
    assert payload["model_path"] == str(output)
    assert payload["model_version"] == CATBOOST_MODEL_VERSION
    assert payload["tracking"] is None


def test_catboost_cli_warns_when_tracking_fails(tmp_path, monkeypatch, capsys):
    def fail_tracking(**_):
        raise RuntimeError("tracking offline")

    monkeypatch.setattr(tracking, "log_training_run", fail_tracking)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-catboost",
            "--samples",
            "400",
            "--iterations",
            "20",
            "--seed",
            "7",
            "--out",
            str(tmp_path / "catboost.joblib"),
        ],
    )

    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["tracking"] is None
    assert "warning: MLflow tracking skipped: tracking offline" in captured.err


def test_catboost_cli_requires_tracking_raises(tmp_path, monkeypatch):
    def fail_tracking(**_):
        raise RuntimeError("tracking offline")

    monkeypatch.setattr(tracking, "log_training_run", fail_tracking)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-catboost",
            "--samples",
            "400",
            "--iterations",
            "20",
            "--seed",
            "7",
            "--out",
            str(tmp_path / "catboost.joblib"),
            "--require-tracking",
        ],
    )

    with pytest.raises(RuntimeError, match="tracking offline"):
        main()


def test_catboost_cli_alias_requires_registration(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["simplecredits-catboost", "--alias", "prod"],
    )

    with pytest.raises(SystemExit):
        main()
