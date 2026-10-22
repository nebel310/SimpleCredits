import json
from pathlib import Path

import pytest

mlflow = pytest.importorskip("mlflow")

from simplecredits.ml.data.schema import TARGET_COLUMN
from simplecredits.ml.tracking import log_training_run
from simplecredits.ml.training.train import save_model, train_model_with_evaluation


def test_training_run_logs_metrics_data_and_model(tmp_path):
    artifact, evaluation, data = train_model_with_evaluation(n_samples=400, seed=7)
    model_path = save_model(artifact, tmp_path / "model.joblib")
    data_path = tmp_path / "dataset.csv"
    data.to_csv(data_path, index=False)

    result = log_training_run(
        artifact=artifact,
        data=data,
        evaluation=evaluation,
        model_path=model_path,
        params={
            "seed": 7,
            "n_samples": len(data),
            "model_version": artifact["model_version"],
        },
        tracking_uri=(tmp_path / "mlruns").as_uri(),
        experiment="test-tracking",
        run_name="test-run",
        data_path=data_path,
    )

    client = mlflow.MlflowClient()
    run = client.get_run(result.run_id)
    assert run.data.metrics["roc_auc_test"] > 0.5
    assert run.data.params["seed"] == "7"
    assert run.data.tags["dataset_digest"] == result.dataset_digest
    assert result.dataset_digest

    root_artifacts = {item.path for item in client.list_artifacts(result.run_id)}
    assert {"data", "model_weights", "evaluation"} <= root_artifacts
    assert result.model_uri.startswith("models:/")

    loaded = mlflow.pyfunc.load_model(result.model_uri)
    predictions = loaded.predict(data.drop(columns=[TARGET_COLUMN]).head(2))
    assert len(predictions) == 2
    assert {"score", "pd", "decision"} <= set(predictions.columns)

    evaluation_artifacts = {
        Path(item.path).name for item in client.list_artifacts(result.run_id, "evaluation")
    }
    assert {"metrics.json", "test_predictions.csv", "data_manifest.json"} <= evaluation_artifacts
    metrics_path = Path(
        client.download_artifacts(result.run_id, "evaluation/metrics.json")
    )
    assert json.loads(metrics_path.read_text(encoding="utf-8"))["roc_auc_test"] > 0.5
