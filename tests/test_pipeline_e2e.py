"""End-to-end test: synthetic invoice → OCR → extractor → validators.

This is the only test that actually exercises Tesseract. It is skipped if the
binary is not available so contributors without tesseract installed can still
run the rest of the suite.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from idp.models.extractor import HeuristicExtractor
from idp.ocr.tesseract_engine import run_tesseract
from idp.postprocess import validators
from tests.fixtures.synthetic import make_invoice

pytestmark = pytest.mark.skipif(
    shutil.which("tesseract") is None, reason="tesseract binary not installed"
)


def test_invoice_extraction_end_to_end(tmp_path: Path):
    sample = make_invoice(tmp_path / "invoice.png", seed=42)
    ocr = run_tesseract(sample.image_path)
    assert ocr.full_text, "OCR returned empty text"

    extractor = HeuristicExtractor()
    result = extractor.extract(ocr)

    assert result.document_type == "invoice"
    fields = {p.name: p.value for p in result.fields}

    # The exact OCR output may swap a couple of characters; we require the
    # high-signal fields to round-trip and the totals to validate.
    assert fields.get("invoice_number") == sample.ground_truth["invoice_number"]
    assert fields.get("invoice_date") == sample.ground_truth["invoice_date"]
    assert fields.get("total_amount") == sample.ground_truth["total_amount"]

    summary = validators.validate_fields(fields)
    assert summary.is_valid, f"validation errors: {summary.errors}"
