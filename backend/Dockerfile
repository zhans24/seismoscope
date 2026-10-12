FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --upgrade pip && pip install .

RUN useradd --create-home appuser && mkdir -p /data/waveforms && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
