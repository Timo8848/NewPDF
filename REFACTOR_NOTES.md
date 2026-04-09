# v0.2 Refactor Notes — Path A ("make it real, make it small")

**Date:** 2026-04-09
**Goal:** Stop the resume project from over-claiming. Cut the fictional
LayoutLMv3 pipeline, ship a working rule-based extractor with a real eval
harness and CI, so every number in the README is reproducible from the
repo in one command.

This document is the running log of every change made during the refactor.
The corresponding code review (the "锐评") that triggered this work lives in
the conversation history; the high-level diagnosis was:

> The repo advertised a layout-aware transformer pipeline with 93% accuracy
> on 300+ PDFs. The extractor never actually called the model, the 93% was
> hand-typed into a markdown file, there was no eval script, no e2e test,
> and several latent bugs in preprocessing, validation, and DuckDB
> connection handling.

We chose **Path A**: delete the fictional ML layer, ship a small honest
service, build a reproducible eval harness, and rewrite the docs to match
what the code actually does.

---

## 1. Cleanup of repo hygiene

| Change | File(s) |
| --- | --- |
| Added a `.gitignore` covering `.DS_Store`, `__pycache__`, `.venv`, `*.egg-info`, `data/*.duckdb`, `.pytest_cache`, etc. | `.gitignore` |
| `git rm --cached` on every tracked `__pycache__/*.pyc` and the `intelligent_document_understanding.egg-info/` directory that had been committed by accident. | (git index only) |

## 2. Dependency diet

`pyproject.toml` lost the entire ML stack that no code path used:

- `torch`, `torchvision`
- `transformers`, `sentencepiece`
- `doctr`
- `scikit-image`
- `sqlalchemy`, `tenacity`, `rapidfuzz`, `typer` (none were imported)

Added: `reportlab` as a `dev` extra (used by the eval harness for future
PDF rendering — currently we use PIL).

Bumped project version to `0.2.0` and rewrote the project description to
match reality ("Lightweight rule-based PDF field extraction service").

A `[tool.ruff]` block was added so CI has something to lint against.

## 3. Configuration

`src/idp/config/settings.py`:

- Deleted `LayoutModelSettings` (provider, model_name, max_seq_length,
  device, confidence_threshold). Nothing referenced it after the extractor
  rewrite.
- Added `ValidationSettings.total_tolerance` (default `"0.02"`) so the
  cross-field check has a configurable epsilon instead of `==`.
- Trimmed `OCRSettings` (removed unused `enable_psm_auto`, `cache_dir`).
- Trimmed `ServiceSettings` (removed unused `enable_tracing`).

`.env.example` rewritten to drop the `LAYOUT_*` variables.

## 4. Extractor rewrite (the headline change)

Deleted `src/idp/models/layout_extractor.py` entirely. It had ~80 lines of
code that imported `torch`, `transformers.LayoutLMv3*`, and `doctr`,
optionally loaded a checkpoint, and then **fell through to the same regex
parser regardless** — see the original `extract()`:

```python
if self.model:
    logger.debug("Model-backed extraction placeholder engaged")
    # Full implementation would perform feature extraction...
fields = self._heuristic_parse(text)
```

Replaced with `src/idp/models/extractor.py` containing:

- `FieldPrediction` dataclass (kept the public shape so the pipeline didn't
  need to change beyond an import).
- `HeuristicExtractor` class with a single `extract(ocr_result)` entry
  point.
- A `_PATTERNS` dict mapping each field name to `(regex, anchor_confidence)`.
  Anchors were tightened — e.g. `total` no longer matches inside
  `subtotal`, the date regex accepts both ISO and `m/d/yyyy`.
- A separate `_MRZ_LINE` regex that accepts the three legal ICAO MRZ
  lengths (30, 36, 44). The previous `r"([A-Z0-9<]{30})\n"` silently
  dropped passport (44) and TD2 (36) lines.
- `_infer_doc_type` updated to use the MRZ regex as a strong signal for ID
  documents.

`src/idp/models/__init__.py` re-exports `HeuristicExtractor`,
`FieldPrediction`, and `ExtractionResult`.

## 5. Validators — tolerance

`src/idp/postprocess/validators.py`:

- `cross_field_checks` now reads `Settings.validation.total_tolerance` and
  compares `abs((subtotal + tax) - total)` against it instead of using
  `!=`. The previous implementation flagged any sample with a 0.01 rounding
  difference, which accounted for at least half of the "totals mismatch"
  errors in the old performance report.
- Error messages now include the actual difference for easier debugging.
- Promoted `_REGEX_RULES` to module level so it isn't rebuilt on every
  call.

## 6. Preprocessing — temp file leaks

`src/idp/ocr/preprocess.py`:

- **Deleted** the duplicate `convert_pdf_to_images` function that wrote
  PNGs to `pdf_path.parent` and never cleaned them up.
- The single remaining `preprocess_pdf(pdf_path, work_dir, config)` takes
  a caller-managed directory and writes every intermediate PNG inside it.
- The pipeline wraps the call in `tempfile.TemporaryDirectory()` so the
  OS cleans up regardless of how the request exits.

## 7. DuckDB analytics

`src/idp/postprocess/analytics.py`:

- Replaced "open + CREATE TABLE + INSERT + close on every request" with a
  module-level cached connection guarded by a `Lock`.
- `init_schema()` is called once from the FastAPI lifespan startup hook.
- `close_connection()` is called from the lifespan shutdown hook.
- `persist_run` and `aggregate_failures` now share the cached connection.
- This eliminates DuckDB file-lock contention under concurrent requests
  and removes the per-request `CREATE TABLE IF NOT EXISTS` round-trip.

## 8. Pipeline + FastAPI lifespan

`src/idp/services/pipeline.py`:

- `ExtractionPipeline.extract` now wraps the OCR + preprocess phase in a
  single `TemporaryDirectory` so every intermediate artifact is reaped at
  function exit.
- Switched the import to the new `HeuristicExtractor`.

`src/idp/api/main.py`:

- Replaced the **module-level** `pipeline = ExtractionPipeline()` (which
  ran during `pytest` collection and any other import) with a FastAPI
  `lifespan` context manager that:
  1. Calls `init_schema()` to set up the DuckDB table.
  2. Constructs the `ExtractionPipeline` and stores it on `app.state`.
  3. On shutdown, calls `close_connection()`.
- `/extract` now writes the upload to a `NamedTemporaryFile`, captures
  `tmp_path`, and unconditionally `unlink(missing_ok=True)`s it in
  `finally`. The previous version could leak the temp file if the pipeline
  raised before the unlink.

## 9. Docker / compose

`docker-compose.yml`:

- Deleted the dummy `duckdb` service (`alpine` running `tail -f /dev/null`).
  DuckDB is an in-process library; it never needed a sidecar.
- The DuckDB volume is now mounted directly on `idp-api` via `./data`.

`Dockerfile`:

- Bumped base image to `python:3.11-slim`.
- Removed the `POETRY_VIRTUALENVS_CREATE` env (we never used Poetry).
- Reordered layers so `pyproject.toml` + `src` are copied before
  `pip install`, giving better build cache reuse on doc-only changes.
- Image size dropped substantially because `torch` is no longer in the
  dependency tree.

## 10. Synthetic eval harness (the load-bearing piece)

New file: `tests/fixtures/synthetic.py`

- `make_invoice(out_path, seed)` deterministically renders an invoice PNG
  via PIL `ImageDraw` using a TrueType monospace font (Liberation Mono on
  Linux, Courier New / Menlo on macOS).
- `make_id_card(out_path, seed)` does the same for an ID card with an MRZ
  block.
- Each generator returns a `SyntheticSample(image_path, doc_type,
  ground_truth)` so callers can score predictions without having to
  re-derive truth.
- `generate_dataset(out_dir, n_invoices, n_ids)` is a one-call helper.

New file: `scripts/eval.py`

- Generates a synthetic dataset in a `TemporaryDirectory`.
- Runs `run_tesseract` → `HeuristicExtractor.extract` → `validate_fields`
  on every sample.
- Aggregates per-field TP / FP / FN, computes precision / recall / F1, and
  emits both `reports/eval_results.json` (full per-sample records) and
  `reports/eval_results.md` (a human-readable table).
- Configurable via `--n-invoices`, `--n-ids`, `--out`, `--md`.

**Latest run (30 samples):** micro precision **0.955**, recall **1.000**,
F1 **0.977**. The full per-field table is in `reports/eval_results.md`.

The remaining 0.045 of "imprecision" is honest — the MRZ detector returns
a line that the synthetic ID ground truth does not yet include, so it
counts as a false positive. This is documented in
`reports/performance.md` as a follow-up.

## 11. Real end-to-end test

New file: `tests/test_pipeline_e2e.py`

- Uses `make_invoice` to render one invoice into `tmp_path`.
- Runs the real Tesseract OCR + extractor + validators.
- Asserts on three high-signal fields and on `summary.is_valid`.
- Skips automatically if the `tesseract` binary is missing so contributors
  without it can still run the rest of the suite.

Result: full suite goes from **4 trivial tests** to **5 tests including
one real Tesseract end-to-end** that exercises every component in the
pipeline. All 5 pass locally (`pytest -q` → `5 passed in 1.60s`).

## 12. CI

New file: `.github/workflows/ci.yml`

- Installs `tesseract-ocr`, `poppler-utils`, and TrueType fonts on the
  Ubuntu runner.
- Sets up Python 3.11, installs the package with the `dev` extras.
- Runs `ruff check src tests scripts`.
- Runs `pytest -q`.
- Runs `python scripts/eval.py --n-invoices 10 --n-ids 5` and uploads the
  generated `reports/eval_results.*` as a build artifact, so every commit
  has a downloadable accuracy report.

## 13. Documentation rewrites

`README.md` rewritten end to end:

- Removed every reference to LayoutLMv3, DocTR, "vision-language", and the
  unsubstantiated 93% number.
- Honestly describes the pipeline as a Tesseract + regex + validator
  service.
- Reports the real eval numbers and links to `reports/eval_results.md`.
- Documents the v0.2 refactor and points at this file.

`docs/architecture.md` rewritten to match the actual code (no torch, no
LayoutLMv3, no Celery hooks). Adds explicit "What was removed in v0.2"
section.

`reports/performance.md` rewritten to describe methodology instead of
listing made-up numbers. Lists known limitations and a follow-up backlog.

## 14. Files at the end

```
.github/workflows/ci.yml          NEW
.gitignore                        NEW
REFACTOR_NOTES.md                 NEW (this file)
Dockerfile                        rewritten
docker-compose.yml                rewritten
pyproject.toml                    rewritten
README.md                         rewritten
.env.example                      rewritten
docs/architecture.md              rewritten
reports/performance.md            rewritten
reports/eval_results.json         NEW (generated by scripts/eval.py)
reports/eval_results.md           NEW (generated)
scripts/eval.py                   NEW
src/idp/api/main.py               rewritten (lifespan, temp file fix)
src/idp/config/settings.py        rewritten (no LayoutModelSettings)
src/idp/models/__init__.py        rewritten
src/idp/models/extractor.py       NEW (replaces layout_extractor.py)
src/idp/models/layout_extractor.py DELETED
src/idp/ocr/preprocess.py         rewritten (single impl, no leaks)
src/idp/postprocess/analytics.py  rewritten (cached connection)
src/idp/postprocess/validators.py rewritten (tolerance, regex hardening)
src/idp/services/pipeline.py      rewritten (lifespan-friendly, tempdir)
tests/fixtures/__init__.py        NEW
tests/fixtures/synthetic.py       NEW
tests/test_pipeline_e2e.py        NEW
```

## 15. Verification

```
$ pytest -q
5 passed in 1.60s

$ python scripts/eval.py --n-invoices 20 --n-ids 10
{
  "precision": 0.955,
  "recall": 1.0,
  "f1": 0.977
}
```

## 16. Follow-ups (intentionally not done in this pass)

- Replace the synthetic dataset with a small real-world labeled corpus.
- Fold OCR token bounding boxes into the extractor so multi-column tables
  are handled.
- Add MRZ parsing (name / nationality / check digits) and ground truth.
- Multilingual OCR — install at least one extra Tesseract language pack
  in the Docker image and exercise it in CI.
- Optional layout-aware extractor (LayoutLMv3 fine-tuned on FUNSD/CORD)
  with side-by-side eval numbers — this is the honest version of what
  v0.1 pretended to do.
