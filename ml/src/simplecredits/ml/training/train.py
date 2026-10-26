from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from simplecredits.ml.config import (
    DEFAULT_EXPERIMENT,
    DEFAULT_REGISTERED_MODEL,
)
from simplecredits.ml.data.generator import generate_dataset
from simplecredits.ml.data.schema import (
    CATEGORICAL_FEATURES,
    HISTORY_NUMERIC_FEATURES,
    TARGET_COLUMN,
)
from simplecredits.ml.features.features import NUMERIC_FEATURES, build_features
from simplecredits.ml.scoring.model import pd_to_risk_grade, pd_to_score
from simplecredits.ml.scoring.policy import (
    DECISION_APPROVE,
    DECISION_APPROVE_WITH_CONDITIONS,
    DECISION_DECLINE,
    DECISION_MANUAL_REVIEW,
    PD_DECLINE_THRESHOLD,
    evaluate_policy,
)

MODEL_VERSION = "scorecard-linear-v1"
DEFAULT_MODEL_PATH = Path("artifacts/model.joblib")
LOGREG_C = 0.003
LOGREG_MAX_ITER = 3000
LOGREG_SOLVER = "lbfgs"
DECISIONS = (
    DECISION_APPROVE,
    DECISION_APPROVE_WITH_CONDITIONS,
    DECISION_MANUAL_REVIEW,
    DECISION_DECLINE,
)
RISK_GRADES = ("A", "B", "C", "D", "E")
LINEAR_NUMERIC_FEATURES = [
    name for name in NUMERIC_FEATURES if name not in HISTORY_NUMERIC_FEATURES
]
LINEAR_FEATURE_COLUMNS = LINEAR_NUMERIC_FEATURES + CATEGORICAL_FEATURES


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    false_positive, true_positive, _ = roc_curve(y_true, y_score)
    return float(np.max(true_positive - false_positive))


def build_pipeline(seed: int) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), LINEAR_NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(
        C=LOGREG_C,
        max_iter=LOGREG_MAX_ITER,
        solver=LOGREG_SOLVER,
        random_state=seed,
        class_weight=None,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])


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


def _fit_artifact(
    data: pd.DataFrame,
    features_train: pd.DataFrame,
    features_test: pd.DataFrame,
    target_train: pd.Series,
    target_test: pd.Series,
    seed: int,
    test_size: float,
) -> dict:
    pipeline = build_pipeline(seed)
    pipeline.fit(features_train, target_train)

    train_probability = pipeline.predict_proba(features_train)[:, 1]
    test_probability = pipeline.predict_proba(features_test)[:, 1]

    metrics = {
        "roc_auc_train": round(float(roc_auc_score(target_train, train_probability)), 4),
        "roc_auc_test": round(float(roc_auc_score(target_test, test_probability)), 4),
        "gini_test": round(2.0 * float(roc_auc_score(target_test, test_probability)) - 1.0, 4),
        "ks_test": round(ks_statistic(target_test.to_numpy(), test_probability), 4),
        "brier_test": round(float(brier_score_loss(target_test, test_probability)), 4),
        "pd_mean_test": round(float(test_probability.mean()), 4),
    }

    return {
        "pipeline": pipeline,
        "model_version": MODEL_VERSION,
        "model_type": "logistic_scorecard",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "feature_columns": LINEAR_FEATURE_COLUMNS,
        "numeric_features": LINEAR_NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "training": {
            "n_samples": int(len(data)),
            "n_train": int(len(features_train)),
            "n_test": int(len(features_test)),
            "default_rate": round(float(data[TARGET_COLUMN].mean()), 4),
            "seed": seed,
            "test_size": test_size,
        },
    }


def _prediction_frame(
    raw_frame: pd.DataFrame,
    target: pd.Series,
    probabilities: np.ndarray,
    split: str,
) -> pd.DataFrame:
    rows = raw_frame.to_dict("records")
    decisions = [
        evaluate_policy(row, float(probability)).decision
        for row, probability in zip(rows, probabilities, strict=True)
    ]
    return pd.DataFrame(
        {
            "row_id": raw_frame.index.to_numpy(),
            "split": split,
            "y_true": target.to_numpy(dtype=int),
            "pd": [round(float(probability), 6) for probability in probabilities],
            "score": [pd_to_score(float(probability)) for probability in probabilities],
            "risk_grade": [pd_to_risk_grade(float(probability)) for probability in probabilities],
            "policy_decision": decisions,
        }
    )


def build_evaluation(
    artifact: dict,
    data: pd.DataFrame,
    features_train: pd.DataFrame,
    features_test: pd.DataFrame,
    target_train: pd.Series,
    target_test: pd.Series,
) -> dict:
    pipeline = artifact["pipeline"]
    feature_columns = artifact.get("feature_columns")
    train_matrix = features_train[feature_columns] if feature_columns else features_train
    test_matrix = features_test[feature_columns] if feature_columns else features_test
    train_probability = pipeline.predict_proba(train_matrix)[:, 1]
    test_probability = pipeline.predict_proba(test_matrix)[:, 1]

    train_predictions = _prediction_frame(
        data.loc[features_train.index],
        target_train,
        train_probability,
        "train",
    )
    test_predictions = _prediction_frame(
        data.loc[features_test.index],
        target_test,
        test_probability,
        "test",
    )

    decision_counts = {
        decision: int((test_predictions["policy_decision"] == decision).sum())
        for decision in DECISIONS
    }
    decision_rates = {
        f"{decision}_rate": round(decision_counts[decision] / len(test_predictions), 4)
        for decision in DECISIONS
    }
    risk_grade_counts = {
        grade: int((test_predictions["risk_grade"] == grade).sum()) for grade in RISK_GRADES
    }
    approved_mask = test_predictions["policy_decision"].isin(
        (DECISION_APPROVE, DECISION_APPROVE_WITH_CONDITIONS)
    )

    threshold_predictions = (test_probability >= PD_DECLINE_THRESHOLD).astype(int)
    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        target_test.to_numpy(dtype=int),
        threshold_predictions,
        labels=[0, 1],
    ).ravel()
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(true_positive + false_negative, 1)
    specificity = true_negative / max(true_negative + false_positive, 1)
    accuracy = (true_positive + true_negative) / len(target_test)
    f1 = 2.0 * precision * recall / max(precision + recall, 1e-12)

    threshold_metrics = {
        "threshold": PD_DECLINE_THRESHOLD,
        "threshold_accuracy": round(float(accuracy), 4),
        "threshold_precision": round(float(precision), 4),
        "threshold_recall": round(float(recall), 4),
        "threshold_specificity": round(float(specificity), 4),
        "threshold_f1": round(float(f1), 4),
        "threshold_true_positive": int(true_positive),
        "threshold_true_negative": int(true_negative),
        "threshold_false_positive": int(false_positive),
        "threshold_false_negative": int(false_negative),
    }

    approved_default_rate = (
        round(float(test_predictions.loc[approved_mask, "y_true"].mean()), 4)
        if approved_mask.any()
        else 0.0
    )
    metrics: dict[str, Any] = {
        **artifact["metrics"],
        "default_rate_test": round(float(target_test.mean()), 4),
        "approval_rate": round(float(approved_mask.mean()), 4),
        "approved_default_rate": approved_default_rate,
        **decision_rates,
        **{f"risk_grade_{grade}_count": risk_grade_counts[grade] for grade in RISK_GRADES},
        **threshold_metrics,
    }

    return {
        "metrics": metrics,
        "policy_summary": {
            "counts": decision_counts,
            "rates": decision_rates,
            "approval_rate": round(float(approved_mask.mean()), 4),
            "approved_default_rate": approved_default_rate,
        },
        "threshold_metrics": threshold_metrics,
        "risk_grade_counts": risk_grade_counts,
        "train_predictions": train_predictions,
        "test_predictions": test_predictions,
    }


def train_model(
    frame: pd.DataFrame | None = None,
    n_samples: int = 20_000,
    seed: int = 42,
    test_size: float = 0.25,
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
    )


def train_model_with_evaluation(
    frame: pd.DataFrame | None = None,
    n_samples: int = 20_000,
    seed: int = 42,
    test_size: float = 0.25,
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


def save_model(artifact: dict, path: str | Path = DEFAULT_MODEL_PATH) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the SimpleCredits scoring model")
    parser.add_argument("--data", help="CSV with raw features and target; generated when omitted")
    parser.add_argument("--out", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.25)
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

    if args.no_tracking:
        artifact = train_model(
            frame=frame,
            n_samples=args.samples,
            seed=args.seed,
            test_size=args.test_size,
        )
        destination = save_model(artifact, args.out)
    else:
        artifact, evaluation, data = train_model_with_evaluation(
            frame=frame,
            n_samples=args.samples,
            seed=args.seed,
            test_size=args.test_size,
        )
        destination = save_model(artifact, args.out)
        try:
            from simplecredits.ml.tracking import log_training_run

            tracking_result = log_training_run(
                artifact=artifact,
                data=data,
                evaluation=evaluation,
                model_path=destination,
                params={
                    "model_version": artifact["model_version"],
                    "model_type": artifact["model_type"],
                    "n_samples": artifact["training"]["n_samples"],
                    "n_train": artifact["training"]["n_train"],
                    "n_test": artifact["training"]["n_test"],
                    "default_rate": artifact["training"]["default_rate"],
                    "seed": artifact["training"]["seed"],
                    "test_size": artifact["training"]["test_size"],
                    "logreg_C": LOGREG_C,
                    "logreg_max_iter": LOGREG_MAX_ITER,
                    "logreg_solver": LOGREG_SOLVER,
                    "data_source": "file" if args.data else "synthetic_generator",
                },
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
