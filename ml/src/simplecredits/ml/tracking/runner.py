from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from simplecredits.ml.config import (
    DEFAULT_DATASET_NAME,
    DEFAULT_EXPERIMENT,
    DEFAULT_REGISTERED_MODEL,
    DEFAULT_TRACKING_DIR,
)
from simplecredits.ml.data.schema import CATEGORICAL_FEATURES, RAW_NUMERIC_FEATURES, TARGET_COLUMN
from simplecredits.ml.scoring.model import CreditScorer
from simplecredits.ml.tracking.pyfunc import CreditScorerPyfunc, score_frame


@dataclass(frozen=True)
class TrackingResult:
    run_id: str
    experiment_id: str
    tracking_uri: str
    model_uri: str
    dataset_digest: str
    dataset_source: str
    registered_model_version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_id": self.experiment_id,
            "tracking_uri": self.tracking_uri,
            "model_uri": self.model_uri,
            "dataset_digest": self.dataset_digest,
            "dataset_source": self.dataset_source,
            "registered_model_version": self.registered_model_version,
        }


def project_root() -> Path:
    candidate = Path(__file__).resolve().parents[5]
    if (candidate / "ml").is_dir():
        return candidate
    return Path.cwd()


def resolve_tracking_uri(tracking_uri: str | None = None) -> str:
    value = tracking_uri or os.getenv("MLFLOW_TRACKING_URI")
    if value:
        if "://" in value:
            return value
        return Path(value).expanduser().resolve().as_uri()
    return (project_root() / DEFAULT_TRACKING_DIR).as_uri()


def _is_http_uri(tracking_uri: str) -> bool:
    return tracking_uri.startswith(("http://", "https://"))


def _import_mlflow():
    try:
        import mlflow
    except ImportError as error:
        raise RuntimeError(
            "MLflow is not installed. Install tracking dependencies with "
            "`pip install -r ml/requirements-tracking.txt`."
        ) from error
    return mlflow


def _configure(tracking_uri: str | None, experiment: str):
    uri = resolve_tracking_uri(tracking_uri)
    if not _is_http_uri(uri):
        os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
    os.environ.setdefault("MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT", "1")
    mlflow = _import_mlflow()
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment)
    return mlflow, uri


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project_root(),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except Exception:
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _frame_digest(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _persist_dataset(
    frame: pd.DataFrame,
    data_path: Path | None,
) -> Path:
    if data_path is not None:
        resolved = data_path.expanduser().resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"dataset file not found: {resolved}")
        return resolved

    digest = _frame_digest(frame)
    destination = project_root() / "ml" / "data" / f"{digest[:16]}.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        frame.to_csv(destination, index=False)
    return destination


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    return str(value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _flatten_params(params: dict[str, Any]) -> dict[str, str | int | float | bool]:
    flattened: dict[str, str | int | float | bool] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (bool, int, float, str)):
            flattened[key] = value
        else:
            flattened[key] = json.dumps(value, ensure_ascii=False, default=_json_default)
    return flattened


def _data_manifest(
    data: pd.DataFrame,
    dataset_digest: str,
    dataset_source: str,
) -> dict[str, Any]:
    return {
        "name": DEFAULT_DATASET_NAME,
        "digest": dataset_digest,
        "source": dataset_source,
        "target": TARGET_COLUMN,
        "rows": int(len(data)),
        "columns": list(data.columns),
        "dtypes": {column: str(dtype) for column, dtype in data.dtypes.items()},
        "default_rate": round(float(data[TARGET_COLUMN].mean()), 6),
    }


def _model_manifest(artifact: dict) -> dict[str, Any]:
    return {
        "model_version": artifact["model_version"],
        "model_type": artifact["model_type"],
        "trained_at": artifact["trained_at"],
        "metrics": artifact["metrics"],
        "training": artifact["training"],
        "feature_columns": list(artifact["feature_columns"]),
        "numeric_features": list(artifact["numeric_features"]),
        "categorical_features": list(artifact["categorical_features"]),
    }


def _evaluation_manifest(evaluation: dict) -> dict[str, Any]:
    return {
        "metrics": evaluation["metrics"],
        "policy_summary": evaluation["policy_summary"],
        "threshold_metrics": evaluation["threshold_metrics"],
        "risk_grade_counts": evaluation["risk_grade_counts"],
    }


def _split_frame(evaluation: dict) -> pd.DataFrame:
    train = evaluation["train_predictions"].loc[:, ["row_id", "split"]]
    test = evaluation["test_predictions"].loc[:, ["row_id", "split"]]
    return pd.concat([train, test], ignore_index=True).sort_values("row_id")


def _log_evaluation_artifacts(
    mlflow,
    evaluation: dict,
    data: pd.DataFrame,
    artifact: dict,
    dataset_digest: str,
    dataset_source: str,
) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        evaluation["train_predictions"].to_csv(
            directory / "train_predictions.csv",
            index=False,
        )
        evaluation["test_predictions"].to_csv(
            directory / "test_predictions.csv",
            index=False,
        )
        _split_frame(evaluation).to_csv(directory / "split.csv", index=False)
        _write_json(directory / "metrics.json", evaluation["metrics"])
        _write_json(directory / "policy_summary.json", evaluation["policy_summary"])
        _write_json(directory / "threshold_metrics.json", evaluation["threshold_metrics"])
        _write_json(directory / "risk_grade_counts.json", evaluation["risk_grade_counts"])
        _write_json(directory / "evaluation.json", _evaluation_manifest(evaluation))
        _write_json(directory / "model_manifest.json", _model_manifest(artifact))
        _write_json(
            directory / "data_manifest.json",
            _data_manifest(data, dataset_digest, dataset_source),
        )
        mlflow.log_artifacts(str(directory), artifact_path="evaluation")


def log_training_run(
    artifact: dict,
    data: pd.DataFrame,
    evaluation: dict,
    model_path: str | Path,
    params: dict[str, Any],
    tracking_uri: str | None = None,
    experiment: str = DEFAULT_EXPERIMENT,
    run_name: str | None = None,
    data_path: str | Path | None = None,
    register_model: bool = False,
    registered_model_name: str = DEFAULT_REGISTERED_MODEL,
    alias: str | None = None,
) -> TrackingResult:
    mlflow, uri = _configure(tracking_uri, experiment)
    if register_model and not _is_http_uri(uri):
        raise RuntimeError("Model registration requires an MLflow tracking server URI")
    resolved_model_path = Path(model_path).expanduser().resolve()
    resolved_data_path = _persist_dataset(
        data,
        Path(data_path) if data_path is not None else None,
    )
    dataset_source = resolved_data_path.as_uri()
    dataset = mlflow.data.from_pandas(
        data,
        source=dataset_source,
        name=DEFAULT_DATASET_NAME,
        targets=TARGET_COLUMN,
    )
    input_columns = RAW_NUMERIC_FEATURES + CATEGORICAL_FEATURES
    input_example = data.loc[:, input_columns].head(3).copy()
    output_example = score_frame(CreditScorer(artifact), input_example)
    signature = mlflow.models.infer_signature(input_example, output_example)
    resolved_run_name = run_name or (
        f"{artifact['model_version']}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"
    )

    with mlflow.start_run(run_name=resolved_run_name) as run:
        mlflow.log_params(
            _flatten_params(
                {
                    **params,
                    "model_type": artifact.get("model_type", "unknown"),
                    "dataset_digest": dataset.digest,
                    "dataset_source": dataset_source,
                    "n_features": len(artifact["feature_columns"]),
                    "python_version": platform.python_version(),
                    "pandas_version": pd.__version__,
                    "scikit_learn_version": sklearn.__version__,
                    "mlflow_version": mlflow.__version__,
                }
            )
        )
        mlflow.set_tags(
            {
                "git_commit": _git_commit(),
                "model_version": artifact["model_version"],
                "model_type": artifact.get("model_type", "unknown"),
                "dataset_digest": dataset.digest,
                "dataset_source": dataset_source,
                "tracking_schema_version": "v1",
            }
        )
        mlflow.log_input(dataset, context="training")
        mlflow.log_metrics(
            {key: float(value) for key, value in evaluation["metrics"].items()}
        )
        mlflow.log_metrics(
            {
                f"policy_{decision}_count": float(count)
                for decision, count in evaluation["policy_summary"]["counts"].items()
            }
        )
        _log_evaluation_artifacts(
            mlflow,
            evaluation,
            data,
            artifact,
            dataset.digest,
            dataset_source,
        )
        mlflow.log_artifact(str(resolved_data_path), artifact_path="data")
        mlflow.log_artifact(str(resolved_model_path), artifact_path="model_weights")
        model_info = mlflow.pyfunc.log_model(
            name="model",
            python_model=CreditScorerPyfunc(),
            artifacts={"scorer": str(resolved_model_path)},
            code_paths=[str(Path(__file__).resolve().parents[2])],
            input_example=input_example,
            signature=signature,
            pip_requirements=[
                "numpy==2.5.4",
                "pandas==3.1.0",
                "scipy==1.18.1",
                "scikit-learn==1.9.1",
                "joblib==1.6.0",
                *(
                    ["catboost==1.2.10"]
                    if artifact.get("model_type") == "catboost"
                    else []
                ),
            ],
        )

        registered_model_version = None
        if register_model:
            registered = mlflow.register_model(
                model_uri=model_info.model_uri,
                name=registered_model_name,
            )
            registered_model_version = registered.version
            if alias:
                mlflow.MlflowClient().set_registered_model_alias(
                    registered_model_name,
                    alias,
                    registered_model_version,
                )

        return TrackingResult(
            run_id=run.info.run_id,
            experiment_id=run.info.experiment_id,
            tracking_uri=uri,
            model_uri=model_info.model_uri,
            dataset_digest=dataset.digest,
            dataset_source=dataset_source,
            registered_model_version=registered_model_version,
        )
