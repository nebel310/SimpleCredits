import json
import sys

import pytest

import simplecredits.ml.tracking as tracking
from simplecredits.ml.training.train import MODEL_VERSION, main


def test_train_cli_writes_model_without_tracking(tmp_path, monkeypatch, capsys):
    output = tmp_path / "model.joblib"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-train",
            "--samples",
            "400",
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
    assert payload["model_version"] == MODEL_VERSION
    assert payload["tracking"] is None


def test_train_cli_warns_when_tracking_fails(tmp_path, monkeypatch, capsys):
    def fail_tracking(**_):
        raise RuntimeError("tracking offline")

    monkeypatch.setattr(tracking, "log_training_run", fail_tracking)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-train",
            "--samples",
            "400",
            "--seed",
            "7",
            "--out",
            str(tmp_path / "model.joblib"),
        ],
    )

    main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["tracking"] is None
    assert "warning: MLflow tracking skipped: tracking offline" in captured.err


def test_train_cli_requires_tracking_raises(tmp_path, monkeypatch):
    def fail_tracking(**_):
        raise RuntimeError("tracking offline")

    monkeypatch.setattr(tracking, "log_training_run", fail_tracking)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "simplecredits-train",
            "--samples",
            "400",
            "--seed",
            "7",
            "--out",
            str(tmp_path / "model.joblib"),
            "--require-tracking",
        ],
    )

    with pytest.raises(RuntimeError, match="tracking offline"):
        main()


def test_train_cli_alias_requires_registration(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["simplecredits-train", "--alias", "prod"],
    )

    with pytest.raises(SystemExit):
        main()
