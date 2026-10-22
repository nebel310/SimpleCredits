import pandas as pd

from simplecredits.ml.data.generator import generate_dataset
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
