from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from simplecredits.ml.data.generator import generate_dataset
from simplecredits.ml.data.schema import CATEGORICAL_FEATURES, TARGET_COLUMN
from simplecredits.ml.features.features import FEATURE_COLUMNS, NUMERIC_FEATURES, build_features

MODEL_VERSION = "scorecard-linear-v1"
DEFAULT_MODEL_PATH = Path("artifacts/model.joblib")


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    false_positive, true_positive, _ = roc_curve(y_true, y_score)
    return float(np.max(true_positive - false_positive))


def build_pipeline(seed: int) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )
    classifier = LogisticRegression(
        C=1.0,
        max_iter=3000,
        solver="lbfgs",
        random_state=seed,
        class_weight=None,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])


def train_model(
    frame: pd.DataFrame | None = None,
    n_samples: int = 20_000,
    seed: int = 42,
    test_size: float = 0.25,
) -> dict:
    data = generate_dataset(n_samples=n_samples, seed=seed) if frame is None else frame.copy()
    if TARGET_COLUMN not in data.columns:
        raise ValueError(f"dataset must contain target column '{TARGET_COLUMN}'")

    features = build_features(data)
    target = data[TARGET_COLUMN].astype(int)

    features_train, features_test, target_train, target_test = train_test_split(
        features,
        target,
        test_size=test_size,
        random_state=seed,
        stratify=target,
    )

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

    artifact = {
        "pipeline": pipeline,
        "model_version": MODEL_VERSION,
        "model_type": "logistic_scorecard",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "feature_columns": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "training": {
            "n_samples": int(len(data)),
            "n_train": int(len(features_train)),
            "n_test": int(len(features_test)),
            "default_rate": round(float(target.mean()), 4),
            "seed": seed,
            "test_size": test_size,
        },
    }
    return artifact


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
    args = parser.parse_args()

    frame = pd.read_csv(args.data) if args.data else None
    artifact = train_model(
        frame=frame,
        n_samples=args.samples,
        seed=args.seed,
        test_size=args.test_size,
    )
    destination = save_model(artifact, args.out)
    print(
        json.dumps(
            {
                "model_path": str(destination),
                "model_version": artifact["model_version"],
                "metrics": artifact["metrics"],
                "training": artifact["training"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
