FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install "setuptools==84.2.1" wheel

COPY ml/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY proto /app/proto
COPY ml/pyproject.toml /app/ml/pyproject.toml
COPY ml/src /app/ml/src
COPY ml/scripts /app/ml/scripts

WORKDIR /app/ml

RUN python scripts/generate_proto.py \
    && pip install --no-build-isolation -e . \
    && python -m simplecredits.ml.training.train --out /app/ml/artifacts/model.joblib

ENV MODEL_PATH=/app/ml/artifacts/model.joblib \
    GRPC_PORT=50051 \
    GRPC_WORKERS=8

EXPOSE 50051

CMD ["python", "-m", "simplecredits.ml.serving.server"]
