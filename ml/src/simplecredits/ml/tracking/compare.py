from __future__ import annotations

import argparse
import json
from typing import Any

from simplecredits.ml.config import DEFAULT_EXPERIMENT
from simplecredits.ml.tracking.runner import _configure


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    widths = {
        column: max(len(column), *(len(_format_value(row.get(column))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(_format_value(row.get(column)).ljust(widths[column]) for column in columns))


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare MLflow training runs")
    parser.add_argument("--tracking-uri")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--metric", default="roc_auc_test")
    parser.add_argument("--order", choices=("asc", "desc"), default="desc")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    mlflow, _ = _configure(args.tracking_uri, args.experiment)
    experiment = mlflow.get_experiment_by_name(args.experiment)
    if experiment is None:
        raise SystemExit(f"experiment not found: {args.experiment}")

    order = "DESC" if args.order == "desc" else "ASC"
    runs = mlflow.MlflowClient().search_runs(
        [experiment.experiment_id],
        order_by=[f"metrics.{args.metric} {order}"],
        max_results=args.limit,
    )

    metric_columns = [args.metric]
    for column in (
        "roc_auc_test",
        "brier_test",
        "approval_rate",
        "approved_default_rate",
    ):
        if column not in metric_columns:
            metric_columns.append(column)
    columns = [
        "run_id",
        "run_name",
        "status",
        *metric_columns,
        "seed",
        "n_samples",
        "model_version",
    ]

    rows = [
        {
            "run_id": run.info.run_id,
            "run_name": run.info.run_name,
            "status": run.info.status,
            **{column: run.data.metrics.get(column) for column in metric_columns},
            "seed": run.data.params.get("seed"),
            "n_samples": run.data.params.get("n_samples"),
            "model_version": run.data.tags.get("model_version"),
        }
        for run in runs
    ]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if not rows:
        print("no runs found")
        return

    _print_table(rows, columns)


if __name__ == "__main__":
    main()
