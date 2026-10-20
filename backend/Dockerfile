# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
ENV PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import tomllib; config = tomllib.load(open('pyproject.toml', 'rb')); print('\\n'.join(config['project']['dependencies'] + config['build-system']['requires']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt
COPY src ./src
RUN pip install --no-deps --no-build-isolation .
COPY alembic.ini ./
COPY migrations ./migrations

RUN useradd --create-home appuser && mkdir -p /data/waveforms && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
