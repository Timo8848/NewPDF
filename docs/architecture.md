# Intelligent Document Understanding System Architecture

## Overview
This project implements an end-to-end Intelligent Document Processing (IDP) pipeline targeting financial and identity PDFs (invoices, tax returns, ID scans). The pipeline combines deterministic preprocessing, OCR, layout-aware vision-language modeling, rule-based and statistical validation, and a production-ready FastAPI deployment surface.

```
PDF -> Preprocess -> OCR -> Layout-Aware Transformer -> Field Schema -> Validation -> Analytics -> API Response
```

## Components

### 1. Preprocessing & OCR Layer
- **Preprocessing:** Deskew, denoise, binarize, and split PDFs into page images using PDFium (via `pdf2image`) and OpenCV.
- **OCR:** Tesseract 5 accessed through `pytesseract`. Produces text, word-level bounding boxes, and confidence per token.
- **Outputs:** Normalized page images, OCR TSV/JSON, and metadata required for downstream layout models.

### 2. Vision-Language Extraction Layer
- **Layout Model:** Configurable to use Hugging Face `microsoft/layoutlmv3-base` or `doctr` detection/recognition heads.
- **Feature Fusion:** Combines OCR tokens with layout embeddings, bounding boxes, and vision backbone features.
- **Schema Mapping:** Maps detected entities (names, addresses, invoice totals, tax IDs, bank details, MRZ) to canonical schema defined in `src/idp/config/schema.yaml`.
- **Confidence:** Emits per-field confidence, bounding boxes, and provenance (page, token indices).

### 3. Post-Processing & Validation
- **Regex Validation:** Dates, amounts, IDs, MRZ patterns, tax IDs, and routing numbers.
- **Cross-Field Checks:** Subtotal + tax = total, invoice date ≤ due date, ID expiry ≥ issue date, totals align with line items.
- **Normalization:** Standardizes numbers (decimal separators, thousand delimiters) and date formats (ISO-8601).
- **SQL Analytics:** Persists extraction summaries into DuckDB for GROUP BY / HAVING anomaly detection and quality reporting.

### 4. Monitoring & Reporting
- **Metrics:** Prometheus-style counters/histograms exposed at `/metrics` (request latency, validation failures, OCR confidence).
- **Tracing & Logging:** Structured JSON logs with request IDs and correlation IDs. OpenTelemetry hooks ready for vendor export.
- **Performance Report:** `reports/performance.md` tracks accuracy, error classes, confusion, and remediation backlog.

### 5. FastAPI Microservice & Deployment
- **Endpoints:** `/extract` (multipart PDF upload), `/health`, `/metrics` (Prometheus text format).
- **Models:** Pydantic request/response models with field-level metadata and validation status.
- **Containerization:** Dockerfile with multi-stage build, optional GPU acceleration via `--build-arg ENABLE_GPU=true`. `docker-compose.yml` wires service + DuckDB volume + Prometheus.
- **Configuration:** `.env` + `config/settings.yaml` for runtime toggles (OCR language packs, selected layout model, validation thresholds).

## Data Flow
1. Upload PDF → stored as temp artifact.
2. Preprocessing converts PDF pages to normalized PNGs.
3. OCR generates tokens and bounding boxes.
4. Layout model ingests page images + OCR features to predict key-value pairs.
5. Post-processing validates, normalizes, and reconciles fields.
6. Persist summary to DuckDB and return JSON response with confidence, validation flags, and provenance.

## Scalability & Accuracy Strategy
- Batch inference with asynchronous task queue (FastAPI background tasks / Celery ready hook).
- Caching OCR outputs for re-uploads via SHA256 hash.
- Active learning hooks to push low-confidence fields to `reports/error_cases/` for manual labeling.
- Targeting ≥90% field-level accuracy across 300+ labeled docs via data augmentation, schema-specific regex, and high-recall detection + strict validation.

## Security & Compliance
- Temporary storage with auto-cleanup.
- Redacted logging (mask PII fields).
- Configurable S3-compatible storage for input/output artifacts.

## Next Steps
- Add GPU-enabled inference container image.
- Integrate human-in-the-loop review UI.
- Expand test suite with synthetic PDFs covering multilingual edge cases.
