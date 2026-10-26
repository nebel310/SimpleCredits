"""Проверяет, что артефакт пригоден для прода.

Главный инвариант: каждый признак модели должен быть доступен в проде, то есть
backend действительно передаёт его значение. Признак, которого нет в прод-пуле,
в проде всегда равен дефолту схемы, поэтому модель подбирает под него веса,
которые никогда не отработают. На catboost-v3 это дало коллапс: PD всех заявок
схлопнулся в диапазон 0.23-0.32 и все получили грейд E с manual_review.

Запуск:
    python scripts/verify_prod_model.py [path/to/artifact.joblib]
"""

from __future__ import annotations

import sys
from pathlib import Path

from simplecredits.ml.features.availability import serving_available_features
from simplecredits.ml.scoring.model import CreditScorer
from simplecredits.ml.training.catboost import DEFAULT_CATBOOST_MODEL_PATH

EXPECTED_MODEL_TYPE = "catboost"


def verify(artifact_path: Path) -> CreditScorer:
    """Проверяет артефакт; кидает AssertionError с описанием проблемы."""
    if not artifact_path.exists():
        raise AssertionError(f"artifact not found: {artifact_path}")

    scorer = CreditScorer.load(artifact_path)

    if scorer.model_type != EXPECTED_MODEL_TYPE:
        raise AssertionError(
            f"expected model_type {EXPECTED_MODEL_TYPE}, got {scorer.model_type}"
        )
    if not scorer.feature_columns:
        raise AssertionError("artifact has no feature columns")

    available = set(serving_available_features())
    off_pool = sorted(set(scorer.feature_columns) - available)
    if off_pool:
        raise AssertionError(
            "model relies on features backend cannot supply "
            f"({len(off_pool)}): {', '.join(off_pool)}"
        )

    return scorer


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    artifact_path = Path(args[0]) if args else DEFAULT_CATBOOST_MODEL_PATH

    try:
        scorer = verify(artifact_path)
    except AssertionError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(
        f"OK: {artifact_path} -> {scorer.model_version} ({scorer.model_type}), "
        f"{len(scorer.feature_columns)} features, all serving-available"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
