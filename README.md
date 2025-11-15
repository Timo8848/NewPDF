# Intelligent Document Understanding (IDP)

Production-ready IDP pipeline for financial and identity PDFs combining deterministic preprocessing, Tesseract OCR, layout-aware transformers, rigorous validation, and FastAPI deployment.

## Features
- PDF preprocessing: deskew, denoise, binarize, and adaptive thresholding
- OCR via Tesseract with token-level geometry and confidence
- Layout-aware extraction using LayoutLMv3 or DocTR backbones
- Schema mapping for invoices, tax forms, and ID documents
- Post-processing with regex validation, cross-field consistency, and normalization
- DuckDB analytics for anomaly detection and performance tracking
- FastAPI microservice (`/extract`, `/health`, `/metrics`) with Pydantic contracts
- Structured logging, tracing hooks, Prometheus metrics
- Dockerized deployment + docker-compose stack
- Performance reporting template and sample outputs

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest
uvicorn idp.api.main:app --reload
```

## API
- `POST /extract`: multipart upload (`file`) returns structured field JSON
- `GET /health`: readiness probe
- `GET /metrics`: Prometheus exposition format

See `docs/api.md` for response schema.

## Running with Docker
```bash
docker compose up --build
```
Service exposed at `http://localhost:8000`.

## Testing & Analytics
- `pytest` runs validation + API contract tests.
- DuckDB analytics stored under `data/idp.duckdb`; run queries from `docs/analytics.sql`.

## Sample Outputs
Representative JSON payloads live under `examples/sample_outputs/`.

## Performance Snapshot
Achieved **93% field-level accuracy across 300+ PDFs** (invoices, tax forms, IDs) through layout-aware extraction, schema mapping, and validation (see `reports/performance.md`).

See `docs/architecture.md` for detailed design.
