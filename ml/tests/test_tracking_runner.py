from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from simplecredits.ml.tracking.runner import (
    TrackingResult,
    _flatten_params,
    _frame_digest,
    _json_default,
    _persist_dataset,
    resolve_tracking_uri,
)


def test_resolve_tracking_uri_keeps_http():
    assert resolve_tracking_uri("http://localhost:5000") == "http://localhost:5000"


def test_resolve_tracking_uri_resolves_local_path(tmp_path):
    expected = (tmp_path / "mlruns").resolve().as_uri()

    assert resolve_tracking_uri(str(tmp_path / "mlruns")) == expected


def test_resolve_tracking_uri_reads_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", str(tmp_path / "tracking"))

    assert resolve_tracking_uri() == (tmp_path / "tracking").resolve().as_uri()


def test_flatten_params_serializes_complex_values():
    flattened = _flatten_params(
        {
            "seed": 7,
            "enabled": True,
            "ratio": 0.5,
            "label": "model",
            "missing": None,
            "nested": {"depth": 1},
            "items": [1, 2],
        }
    )

    assert flattened["seed"] == 7
    assert flattened["enabled"] is True
    assert flattened["ratio"] == 0.5
    assert flattened["label"] == "model"
    assert "missing" not in flattened
    assert flattened["nested"] == '{"depth": 1}'
    assert flattened["items"] == "[1, 2]"


def test_json_default_handles_numpy_and_paths(tmp_path):
    assert _json_default(np.int64(3)) == 3
    assert _json_default(tmp_path) == str(tmp_path)
    assert _json_default(object()).startswith("<object object at")


def test_persist_dataset_returns_existing_file(tmp_path):
    data_path = tmp_path / "dataset.csv"
    data_path.write_text("value\n1\n", encoding="utf-8")

    assert _persist_dataset(pd.DataFrame(), data_path) == data_path.resolve()


def test_persist_dataset_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="dataset file not found"):
        _persist_dataset(pd.DataFrame(), tmp_path / "missing.csv")


def test_frame_digest_is_stable():
    frame = pd.DataFrame({"value": [1, 2]})

    assert _frame_digest(frame) == _frame_digest(frame.copy())
    assert len(_frame_digest(frame)) == 64


def test_tracking_result_as_dict():
    result = TrackingResult(
        run_id="run-1",
        experiment_id="exp-1",
        tracking_uri="file:///tmp/mlruns",
        model_uri="models:/model/1",
        dataset_digest="digest",
        dataset_source="file:///tmp/data.csv",
        registered_model_version="1",
    )

    payload = result.as_dict()
    assert payload["run_id"] == "run-1"
    assert payload["registered_model_version"] == "1"
    assert set(payload) == {
        "run_id",
        "experiment_id",
        "tracking_uri",
        "model_uri",
        "dataset_digest",
        "dataset_source",
        "registered_model_version",
    }


def test_project_root_contains_ml_directory():
    from simplecredits.ml.tracking.runner import project_root

    assert (project_root() / "ml").is_dir()


def test_default_tracking_uri_is_local(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

    assert resolve_tracking_uri().startswith("file://")
    assert resolve_tracking_uri().endswith("/mlruns")


def test_json_default_path_type():
    assert _json_default(Path("data.csv")) == "data.csv"
