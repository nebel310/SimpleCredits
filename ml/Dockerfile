FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

RUN pip install "setuptools==84.2.1" wheel

COPY ml/requirements.txt /app/requirements.txt
COPY ml/requirements-tracking.txt /app/requirements-tracking.txt
RUN pip install -r /app/requirements.txt -r /app/requirements-tracking.txt

COPY proto /app/proto
COPY ml/pyproject.toml /app/ml/pyproject.toml
COPY ml/src /app/ml/src
COPY ml/scripts /app/ml/scripts
# Production model (catboost-v3), trained on the raw-as-of-v4 pipeline table.
COPY ml/artifacts/catboost_model.joblib /app/ml/artifacts/catboost_model.joblib

WORKDIR /app/ml

RUN python scripts/generate_proto.py \
    && pip install --no-build-isolation -e .

# Fail the build instead of silently serving a different model at runtime.
RUN python -c "from simplecredits.ml.scoring.model import CreditScorer; \
s = CreditScorer.load('/app/ml/artifacts/catboost_model.joblib'); \
assert s.model_type == 'catboost', s.model_type; \
assert len(s.feature_columns) == 30, len(s.feature_columns); \
print('model verified:', s.model_version, s.model_type, len(s.feature_columns), 'features')"

ENV MODEL_PATH=/app/ml/artifacts/catboost_model.joblib \
    GRPC_PORT=50051 \
    GRPC_WORKERS=8

EXPOSE 50051

CMD ["python", "-m", "simplecredits.ml.serving.server"]
