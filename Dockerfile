FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Project metadata + source
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
COPY dbt /app/dbt
COPY scripts /app/scripts
COPY ledger /app/ledger

# Install package + dev/dbt dependencies
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Default warehouse location expected via GRID_DATABASE
ENV GRID_DATABASE=/app/data/grid.duckdb

CMD ["bash"]