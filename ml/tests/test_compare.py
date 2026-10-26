import json
from types import SimpleNamespace

import pytest

from simplecredits.ml.tracking import compare


def make_run(
    run_id="run-1",
    run_name="first run",
    status="FINISHED",
    metrics=None,
    params=None,
    tags=None,
):
    return SimpleNamespace(
        info=SimpleNamespace(run_id=run_id, run_name=run_name, status=status),
        data=SimpleNamespace(
            metrics=metrics or {},
            params=params or {},
            tags=tags or {},
        ),
    )


def make_mlflow(experiment, runs):
    calls = {}

    class Client:
        def search_runs(self, experiment_ids, order_by, max_results):
            calls["experiment_ids"] = experiment_ids
            calls["order_by"] = order_by
            calls["max_results"] = max_results
            return runs

    def get_experiment_by_name(name):
        if name == "missing":
            return None
        return experiment

    return SimpleNamespace(
        get_experiment_by_name=get_experiment_by_name,
        MlflowClient=Client,
    ), calls


def test_format_value():
    assert compare._format_value(None) == ""
    assert compare._format_value(0.123456) == "0.1235"
    assert compare._format_value(7) == "7"
    assert compare._format_value("text") == "text"


def test_print_table_aligns_rows(capsys):
    rows = [
        {"run": "a", "metric": 0.5},
        {"run": "long-name", "metric": None},
    ]
    compare._print_table(rows, ["run", "metric"])

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("run")
    assert lines[1].startswith("--------")
    assert "long-name" in lines[3]


def test_compare_main_outputs_json(monkeypatch, capsys):
    experiment = SimpleNamespace(experiment_id="exp-1")
    run = make_run(
        metrics={"roc_auc_test": 0.81, "brier_test": 0.12},
        params={"seed": "7", "n_samples": "400"},
        tags={"model_type": "catboost", "model_version": "catboost-v2"},
    )
    mlflow, calls = make_mlflow(experiment, [run])
    monkeypatch.setattr(compare, "_configure", lambda *_: (mlflow, "file:///tmp/mlruns"))
    monkeypatch.setattr(
        "sys.argv",
        ["simplecredits-compare", "--json", "--limit", "5", "--experiment", "test"],
    )

    compare.main()

    rows = json.loads(capsys.readouterr().out)
    assert rows == [
        {
            "run_id": "run-1",
            "run_name": "first run",
            "status": "FINISHED",
            "roc_auc_test": 0.81,
            "brier_test": 0.12,
            "approval_rate": None,
            "approved_default_rate": None,
            "seed": "7",
            "n_samples": "400",
            "model_type": "catboost",
            "model_version": "catboost-v2",
        }
    ]
    assert calls == {
        "experiment_ids": ["exp-1"],
        "order_by": ["metrics.roc_auc_test DESC"],
        "max_results": 5,
    }


def test_compare_main_prints_table(monkeypatch, capsys):
    experiment = SimpleNamespace(experiment_id="exp-1")
    run = make_run(metrics={"roc_auc_test": 0.81})
    mlflow, _ = make_mlflow(experiment, [run])
    monkeypatch.setattr(compare, "_configure", lambda *_: (mlflow, "file:///tmp/mlruns"))
    monkeypatch.setattr("sys.argv", ["simplecredits-compare"])

    compare.main()

    output = capsys.readouterr().out
    assert "run_id" in output
    assert "run-1" in output


def test_compare_main_handles_empty_runs(monkeypatch, capsys):
    experiment = SimpleNamespace(experiment_id="exp-1")
    mlflow, _ = make_mlflow(experiment, [])
    monkeypatch.setattr(compare, "_configure", lambda *_: (mlflow, "file:///tmp/mlruns"))
    monkeypatch.setattr("sys.argv", ["simplecredits-compare"])

    compare.main()

    assert capsys.readouterr().out.strip() == "no runs found"


def test_compare_main_rejects_unknown_experiment(monkeypatch):
    mlflow, _ = make_mlflow(SimpleNamespace(experiment_id="exp-1"), [])
    monkeypatch.setattr(compare, "_configure", lambda *_: (mlflow, "file:///tmp/mlruns"))
    monkeypatch.setattr("sys.argv", ["simplecredits-compare", "--experiment", "missing"])

    with pytest.raises(SystemExit, match="experiment not found: missing"):
        compare.main()
