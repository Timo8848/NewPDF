# IDP Architecture

## Scope

This service extracts structured fields from PDFs of invoices and ID
documents. It is intentionally rule-based: Tesseract OCR feeds an anchor
regex extractor, then a validator catches obvious inconsistencies. There is
no learned model in the pipeline.

```
PDF → Preprocess → OCR → Heuristic Extractor → Validator → Analytics → API Response
```

## Components

### 1. Preprocessing (`idp.ocr.preprocess`)

- `pdf2image.convert_from_path` renders each page to a PIL image at a
  configurable DPI (default 300).
- Each page is converted to grayscale, median-blurred (denoise),
  deskewed via `cv2.minAreaRect`, and adaptively thresholded.
- All intermediate PNGs live in a caller-managed `TemporaryDirectory` and
  are cleaned up automatically when the request finishes.

### 2. OCR (`idp.ocr.tesseract_engine`)

- `pytesseract.image_to_data` returns word-level rows; we keep the text,
  bounding box, confidence, and page number per token.
- Output is a single `OCRResult` aggregating all pages.

### 3. Heuristic extractor (`idp.models.extractor`)

- A small dictionary of `(name → (regex, confidence))` pairs anchored on
  label text such as `Invoice Number:`, `Subtotal:`, `Routing Number:`.
- MRZ lines are detected with a separate regex that accepts the three
  ICAO-standard lengths (30 / 36 / 44).
- Document type is inferred from anchor keywords plus the presence of
  an MRZ line.

### 4. Validation (`idp.postprocess.validators`)

- **Format checks** for invoice number, tax ID, routing/account number, ID
  number.
- **Cross-field checks**:
  - `|subtotal + tax − total| ≤ tolerance` (default `0.02`, configurable
    in `ValidationSettings.total_tolerance`).
  - `invoice_date ≤ due_date` (warning, not error).
  - `birth_date ≤ expiry_date`.
- Normalisers parse decimal amounts and ISO/`d/m/y`/`m/d/y` dates.

### 5. Analytics (`idp.postprocess.analytics`)

- A single DuckDB connection per process (`get_connection`) with
  `init_schema` called once at FastAPI startup.
- `persist_run` inserts one row per extracted field per request.
- `aggregate_failures` returns the top-N invalid field names via a
  `GROUP BY` over the same table — used to populate the `analytics` block
  in the API response.

### 6. Service layer (`idp.api.main`, `idp.services.pipeline`)

- FastAPI `lifespan` instantiates the `ExtractionPipeline` and opens the
  DuckDB connection on startup; the connection is closed on shutdown.
- `/extract` saves the upload to a `NamedTemporaryFile`, runs the
  pipeline, and removes the temp file in `finally`.
- Prometheus metrics:
  - `idp_extraction_latency_ms` histogram
  - `idp_validation_failures_total{field}` counter
  - `idp_documents_processed_total{doc_type}` counter
- Structured JSON logs via `structlog` with a `traced` context manager
  per request.

## Evaluation

`scripts/eval.py` is the only source of truth for accuracy numbers:

1. `tests/fixtures/synthetic.py` deterministically renders invoices and
   ID cards as PNGs with a TrueType font. Each sample comes paired with
   its ground-truth field dictionary.
2. The harness runs the production OCR + extractor + validators on every
   sample and compares predictions to ground truth.
3. Per-field TP/FP/FN are aggregated into precision/recall/F1, written to
   `reports/eval_results.json` and `reports/eval_results.md`.
4. CI runs the harness on every push and uploads the results as an
   artifact.

This eval is an **upper bound**: it isolates the regex extractor's
correctness against clean synthetic OCR. It does not measure real-world
OCR error tolerance. Replacing the synthetic dataset with a labeled
corpus is the top item on the roadmap.

## Configuration

`Settings` (Pydantic) bundles:

- `OCRSettings` — tesseract binary path, languages, DPI.
- `ValidationSettings` — tolerance, enforce flags, min confidence.
- `StorageSettings` — DuckDB path.
- `ServiceSettings` — environment, log level, metrics toggle.

Defaults are sensible for local dev; override via env or `.env`.

## What was removed in v0.2

The previous architecture document advertised a LayoutLMv3 / DocTR
extractor that the actual code never executed (the model object was
loaded, then ignored, and the pipeline ran the heuristic parser
unconditionally). The unused imports, dependencies (`torch`,
`torchvision`, `transformers`, `sentencepiece`, `doctr`), and
`LayoutModelSettings` were all deleted in the v0.2 refactor. The
`models/` package now contains only the heuristic extractor.

If a layout-aware model is reintroduced in the future it will be wired
into a real `extract()` path with measured contribution in the eval
report — see `REFACTOR_NOTES.md` for the rationale.
