# Deployment Guide

## Local Docker
```bash
docker compose up --build
```
FastAPI will be available at `http://localhost:8000`. Use `/docs` for interactive Swagger UI.

## Environment Variables
- `SERVICE_ENV`: dev/staging/prod
- `LOG_LEVEL`: DEBUG/INFO/WARNING/ERROR
- `OCR_LANGUAGES`: comma-separated language packs for Tesseract
- `LAYOUT_PROVIDER`: layoutlmv3 or doctr
- `LAYOUT_MODEL`: HuggingFace model id

## Production
- Push container to registry and deploy behind API gateway.
- Mount persistent volume for `/app/data` to keep DuckDB analytics.
- Configure Prometheus scrape for `/metrics` and forward structured logs to ELK/Datadog.
