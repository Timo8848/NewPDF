# Intelligent Document Processing (IDP)

A lightweight, production-style PDF field-extraction service for invoices and
ID documents. The pipeline is intentionally simple — Tesseract OCR feeds an
anchor-based regex extractor, then a rule-based validator catches arithmetic
and date inconsistencies. Results are exposed via a FastAPI service and
persisted to DuckDB for offline analytics.

> **v0.2 refactor (April 2026):** removed an unused LayoutLMv3 / DocTR
> placeholder that previous versions advertised but never executed; the
> extractor was always rule-based. See [`REFACTOR_NOTES.md`](REFACTOR_NOTES.md)
> for the full change log.

## What it does

- **Preprocess** PDFs page-by-page: render → grayscale → denoise → deskew → adaptive binarize.
- **OCR** with Tesseract, retaining word-level bounding boxes and confidence.
- **Extract** canonical fields (invoice number, dates, subtotal/tax/total, tax ID,
  routing/account numbers, ID number, MRZ lines) with anchor-based regexes.
- **Validate** field-format regexes plus cross-field checks (subtotal+tax≈total
  within tolerance, invoice date ≤ due date, expiry ≥ birth).
- **Persist** every run summary to DuckDB so you can query failure patterns.
- **Serve** the pipeline behind FastAPI (`/extract`, `/health`, `/metrics`) with
  Prometheus metrics and structured JSON logs.

## Architecture

```
PDF
  → preprocess (pdf2image + OpenCV)
  → OCR        (Tesseract, token-level)
  → extract    (anchor regex → FieldPrediction)
  → validate   (regex + cross-field)
  → persist    (DuckDB)
  → respond    (FastAPI JSON)
```

See [`docs/architecture.md`](docs/architecture.md) for details.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Tesseract must be on PATH:
#   macOS:    brew install tesseract
#   Debian:   sudo apt-get install tesseract-ocr poppler-utils

pytest                       # 5 tests, includes a real Tesseract e2e
python scripts/eval.py       # writes reports/eval_results.{json,md}
uvicorn idp.api.main:app --reload
```

## API

| Endpoint   | Method | Description                                       |
| ---------- | ------ | ------------------------------------------------- |
| `/extract` | POST   | Multipart `file` (PDF) → JSON with fields + validation |
| `/health`  | GET    | Liveness/uptime                                   |
| `/metrics` | GET    | Prometheus exposition format                      |

Response schema is documented in [`docs/api.md`](docs/api.md).

## Evaluation

Accuracy claims are backed by [`scripts/eval.py`](scripts/eval.py), which
generates a synthetic dataset (deterministic from a seed) of invoices and ID
cards with known ground truth, runs the production pipeline end-to-end, and
reports per-field precision/recall/F1.

Latest run on 30 synthetic samples (20 invoices + 10 ID cards):

| Metric          | Value  |
| --------------- | ------ |
| Micro precision | 0.955  |
| Micro recall    | 1.000  |
| Micro F1        | 0.977  |

Full per-field breakdown lives in [`reports/eval_results.md`](reports/eval_results.md)
and is regenerated on every CI run.

These numbers are produced by Tesseract-on-rendered-PNGs against synthetic
fixtures, not against a real labeled corpus — they are an upper bound that
measures the regex layer's correctness, not real-world OCR accuracy. A real
labeled benchmark is the obvious next step (see *Roadmap*).

## Running with Docker

```bash
docker compose up --build
```

Service exposed at `http://localhost:8000`. The compose file mounts `./data`
as the DuckDB volume.

## Project layout

```
src/idp/
  api/         FastAPI app + Pydantic contracts
  config/      Pydantic Settings + schema.yaml
  models/      HeuristicExtractor (regex-based field extraction)
  ocr/         Tesseract wrapper + OpenCV preprocessing
  postprocess/ Validators, normalizers, DuckDB analytics
  services/    Pipeline orchestration + Prometheus metrics
  utils/       structlog setup
scripts/
  eval.py      Synthetic-fixture evaluation harness
tests/
  fixtures/    Synthetic invoice / ID generator
```

## Roadmap

- Replace synthetic eval set with a small real-world labeled corpus.
- Add a layout-aware model (LayoutLMv3 fine-tuned on FUNSD/CORD) as an
  optional second extractor; gate it behind a feature flag and include
  side-by-side eval numbers.
- Active-learning loop that pushes low-confidence fields to a review queue.
- Multilingual OCR (currently `eng` only).
