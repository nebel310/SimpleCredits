import pytest

from simplecredits.ml.scoring.model import CreditScorer
from simplecredits.ml.training.train import train_model


@pytest.fixture(scope="session")
def scorer():
    artifact = train_model(n_samples=3000, seed=42)
    return CreditScorer(artifact)
