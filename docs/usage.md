# Usage Guide

## Local Development
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -e .[dev]`
3. (Optional) export `TESSDATA_PREFIX` for custom language packs.
4. `uvicorn idp.api.main:app --reload`

## Example Request
```bash
curl -X POST http://localhost:8000/extract \
  -F "file=@examples/sample_invoice.pdf"
```

## Testing
```bash
pytest
```

## Metrics & Analytics
- Prometheus scrape `http://localhost:8000/metrics`
- DuckDB file `data/idp.duckdb`
- Run SQL from `docs/analytics.sql`

## Deployment Pipeline
- Build & push container: `docker build -t registry/idp:latest .`
- Deploy via docker-compose, Kubernetes, or serverless containers.
