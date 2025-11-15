# syntax=docker/dockerfile:1.7
FROM python:3.10-slim AS base
ENV POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .
COPY src ./src
COPY docs ./docs
COPY examples ./examples
COPY reports ./reports

EXPOSE 8000
CMD ["uvicorn", "idp.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
