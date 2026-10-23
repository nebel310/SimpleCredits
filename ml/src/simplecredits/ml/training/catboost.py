from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

from simplecredits.ml.config import (
    DEFAULT_EXPERIMENT,
    DEFAULT_REGISTERED_MODEL,
)
from simplecredits.ml.data.generator import generate_dataset
from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    TARGET_COLUMN,
)
from simplecredits.ml.features.features import (
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    build_features,
)
from simplecredits.ml.scoring.model import CatBoostProbabilityModel
from simplecredits.ml.training.train import build_evaluation, ks_statistic, save_model

CATBOOST_MODEL_VERSION = "catboost-v1"
DEFAULT_CATBOOST_MODEL_PATH = Path("artifacts/catboost_model.joblib")
CATBOOST_PARAMS: dict[str, Any] = {
    "iterations": 400,
    "learning_rate": 0.03,
    "depth": 2,
    "l2_leaf_reg": 10.0,
    "loss_function": "Logloss",
    "eval_metric": "AUC",
    "random_seed": 42,
    "verbose": False,
    "allow_writing_files": False,
    "thread_count": -1,
    "cat_features": CATEGORICAL_FEATURES,
}


def _prepare_frame(
    frame: pd.DataFrame | None,
    n_samples: int,
    seed: int,
) -> pd.DataFrame:
    data = generate_dataset(n_samples=n_samples, seed=seed) if frame is None else frame.copy()
    if TARGET_COLUMN not in data.columns:
        raise ValueError(f"dataset must contain target column '{TARGET_COLUMN}'")
    return data.reset_index(drop=True)


def _split_dataset(
    data: pd.DataFrame,
    seed: int,
    test_size: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    features = build_features(data)
    target = data[TARGET_COLUMN].astype(int)
    return train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=seed,
        stratify=target,
    )


def _resolve_params(
    seed: int,
    params: dict[str, Any] | None,
) -> dict[str, Any]:
    return {**CATBOOST_PARAMS, **(params or {}), "random_seed": seed}


def build_model(
    seed: int,
    params: dict[str, Any] | None = None,
) -> CatBoostClassifier:
    return CatBoostClassifier(**_resolve_params(seed, params))


def _fit_artifact(
    data: pd.DataFrame,
    features_train: pd.DataFrame,
    features_test: pd.DataFrame,
    target_train: pd.Series,
    target_test: pd.Series,
    seed: int,
    test_size: float,
    params: dict[str, Any] | None,
) -> dict:
    resolved_params = _resolve_params(seed, params)
    model = build_model(seed, params)
    model.fit(features_train, target_train)

    train_probability = model.predict_proba(features_train)[:, 1]
    test_probability = model.predict_proba(features_test)[:, 1]
    test_auc = float(roc_auc_score(target_test, test_probability))
    metrics = {
        "roc_auc_train": round(float(roc_auc_score(target_train, train_probability)), 4),
        "roc_auc_test": round(test_auc, 4),
        "gini_test": round(2.0 * test_auc - 1.0, 4),
        "ks_test": round(ks_statistic(target_test.to_numpy(), test_probability), 4),
        "brier_test": round(float(brier_score_loss(target_test, test_probability)), 4),
        "pd_mean_test": round(float(test_probability.mean()), 4),
    }

    return {
        "model": model,
        "pipeline": CatBoostProbabilityModel(model),
        "model_version": CATBOOST_MODEL_VERSION,
        "model_type": "catboost",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "training": {
            "n_samples": int(len(data)),
            "n_train": int(len(features_train)),
            "n_test": int(len(features_test)),
            "default_rate": round(float(data[TARGET_COLUMN].mean()), 4),
            "seed": seed,
            "test_size": test_size,
            "params": {
                key: value
                for key, value in resolved_params.items()
                if key != "cat_features"
            },
        },
    }


def train_catboost_model(
    frame: pd.DataFrame | None = None,
    n_samples: int = 20_000,
    seed: int = 42,
    test_size: float = 0.25,
    params: dict[str, Any] | None = None,
) -> dict:
    data = _prepare_frame(frame, n_samples, seed)
    features_train, features_test, target_train, target_test = _split_dataset(
        data,
        seed,
        test_size,
    )
    return _fit_artifact(
        data,
        features_train,
        features_test,
        target_train,
        target_test,
        seed,
        test_size,
        params,
    )


def train_catboost_model_with_evaluation(
    frame: pd.DataFrame | None = None,
    n_samples: int = 20_000,
    seed: int = 42,
    test_size: float = 0.25,
    params: dict[str, Any] | None = None,
) -> tuple[dict, dict, pd.DataFrame]:
    data = _prepare_frame(frame, n_samples, seed)
    features_train, features_test, target_train, target_test = _split_dataset(
        data,
        seed,
        test_size,
    )
    artifact = _fit_artifact(
        data,
        features_train,
        features_test,
        target_train,
        target_test,
        seed,
        test_size,
        params,
    )
    evaluation = build_evaluation(
        artifact,
        data,
        features_train,
        features_test,
        target_train,
        target_test,
    )
    return artifact, evaluation, data


def _training_params(artifact: dict, data_source: str) -> dict[str, Any]:
    params = {
        **artifact["training"]["params"],
        "model_version": artifact["model_version"],
        "model_type": artifact["model_type"],
        "n_samples": artifact["training"]["n_samples"],
        "n_train": artifact["training"]["n_train"],
        "n_test": artifact["training"]["n_test"],
        "default_rate": artifact["training"]["default_rate"],
        "seed": artifact["training"]["seed"],
        "test_size": artifact["training"]["test_size"],
        "data_source": data_source,
    }
    return params


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SimpleCredits CatBoost model")
    parser.add_argument("--data", help="CSV with raw features and target; generated when omitted")
    parser.add_argument("--out", default=str(DEFAULT_CATBOOST_MODEL_PATH))
    parser.add_argument("--samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--iterations", type=int)
    parser.add_argument("--depth", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--l2-leaf-reg", type=float)
    parser.add_argument("--tracking-uri", help="MLflow tracking URI; defaults to MLFLOW_TRACKING_URI or ./mlruns")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--run-name")
    parser.add_argument("--no-tracking", action="store_true")
    parser.add_argument("--require-tracking", action="store_true")
    parser.add_argument("--register-model", action="store_true")
    parser.add_argument("--registered-model-name", default=DEFAULT_REGISTERED_MODEL)
    parser.add_argument("--alias")
    args = parser.parse_args()

    if args.alias and not args.register_model:
        parser.error("--alias requires --register-model")

    frame = pd.read_csv(args.data) if args.data else None
    tracking_result = None
    catboost_params = {
        key: value
        for key, value in {
            "iterations": args.iterations,
            "depth": args.depth,
            "learning_rate": args.learning_rate,
            "l2_leaf_reg": args.l2_leaf_reg,
        }.items()
        if value is not None
    }

    if args.no_tracking:
        artifact = train_catboost_model(
            frame=frame,
            n_samples=args.samples,
            seed=args.seed,
            test_size=args.test_size,
            params=catboost_params,
        )
        destination = save_model(artifact, args.out)
    else:
        artifact, evaluation, data = train_catboost_model_with_evaluation(
            frame=frame,
            n_samples=args.samples,
            seed=args.seed,
            test_size=args.test_size,
            params=catboost_params,
        )
        destination = save_model(artifact, args.out)
        try:
            from simplecredits.ml.tracking import log_training_run

            tracking_result = log_training_run(
                artifact=artifact,
                data=data,
                evaluation=evaluation,
                model_path=destination,
                params=_training_params(
                    artifact,
                    "file" if args.data else "synthetic_generator",
                ),
                tracking_uri=args.tracking_uri,
                experiment=args.experiment,
                run_name=args.run_name,
                data_path=Path(args.data) if args.data else None,
                register_model=args.register_model,
                registered_model_name=args.registered_model_name,
                alias=args.alias,
            )
        except Exception as error:
            if args.require_tracking:
                raise
            print(f"warning: MLflow tracking skipped: {error}", file=sys.stderr)

    payload: dict[str, Any] = {
        "model_path": str(destination),
        "model_version": artifact["model_version"],
        "metrics": artifact["metrics"],
        "training": artifact["training"],
        "tracking": tracking_result.as_dict() if tracking_result else None,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
