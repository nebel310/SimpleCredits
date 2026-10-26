import sys

import pandas as pd
import pytest

from simplecredits.ml.data.generator import generate_dataset, main, save_dataset
from simplecredits.ml.data.schema import RAW_FEATURES, TARGET_COLUMN


def test_generator_shape_and_columns():
    frame = generate_dataset(n_samples=500, seed=7)
    assert len(frame) == 500
    assert list(frame.columns) == RAW_FEATURES + [TARGET_COLUMN]


def test_generator_is_deterministic():
    first = generate_dataset(n_samples=300, seed=11)
    second = generate_dataset(n_samples=300, seed=11)
    pd.testing.assert_frame_equal(first, second)


def test_generator_default_rate_is_realistic():
    frame = generate_dataset(n_samples=3000, seed=3)
    rate = frame[TARGET_COLUMN].mean()
    assert 0.05 < rate < 0.30


def test_generator_rejects_small_dataset():
    with pytest.raises(ValueError, match="at least 100"):
        generate_dataset(n_samples=99)


def test_save_dataset_writes_csv(tmp_path):
    destination = save_dataset(tmp_path / "nested" / "data.csv", n_samples=120, seed=5)

    frame = pd.read_csv(destination)
    assert destination.exists()
    assert len(frame) == 120
    assert TARGET_COLUMN in frame.columns


def test_generator_main_prints_summary(tmp_path, monkeypatch, capsys):
    output = tmp_path / "data.csv"
    monkeypatch.setattr(
        sys,
        "argv",
        ["simplecredits-generator", "--out", str(output), "--samples", "120", "--seed", "5"],
    )

    main()

    printed = capsys.readouterr().out
    assert output.exists()
    assert "saved 120 rows" in printed
    assert "default_rate=" in printed
