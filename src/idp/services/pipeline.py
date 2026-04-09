from __future__ import annotations

import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List

from idp.config import get_settings
from idp.models.extractor import HeuristicExtractor
from idp.ocr.preprocess import PreprocessConfig, preprocess_pdf
from idp.ocr.tesseract_engine import OCRResult, OCRToken, run_tesseract
from idp.postprocess import validators
from idp.postprocess.analytics import aggregate_failures, persist_run
from idp.services.metrics import DOCUMENT_PROCESSED, EXTRACTION_LATENCY, VALIDATION_FAILURES
from idp.utils.logging import traced


class ExtractionPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.extractor = HeuristicExtractor()

    def _run_ocr(self, image_paths: List[Path]) -> OCRResult:
        tokens: List[OCRToken] = []
        full_text_parts: List[str] = []
        metadata: Dict = {"pages": len(image_paths)}
        for idx, image in enumerate(image_paths, start=1):
            page_result = run_tesseract(image)
            for token in page_result.tokens:
                token.page_num = idx
                tokens.append(token)
            full_text_parts.append(page_result.full_text)
        metadata["avg_confidence"] = (
            sum(t.confidence for t in tokens) / len(tokens) if tokens else 0.0
        )
        return OCRResult(tokens=tokens, full_text="\n".join(full_text_parts), metadata=metadata)

    def extract(self, pdf_path: Path) -> Dict:
        request_id = str(uuid.uuid4())
        with traced("extraction"):
            start = time.perf_counter()

            # Hold every intermediate artifact inside a single tempdir so the OS
            # cleans up regardless of how the request exits.
            with tempfile.TemporaryDirectory(prefix="idp_") as tmp:
                work_dir = Path(tmp)
                preprocess_result = preprocess_pdf(
                    pdf_path, work_dir, PreprocessConfig(dpi=self.settings.ocr.dpi)
                )
                ocr_result = self._run_ocr(preprocess_result.images)

            extraction_result = self.extractor.extract(ocr_result)
            fields = {
                pred.name: {"value": pred.value, "confidence": pred.confidence}
                for pred in extraction_result.fields
            }
            validation = validators.validate_fields(
                {k: v.get("value") for k, v in fields.items()}
            )
            for err in validation.errors:
                VALIDATION_FAILURES.labels(err.field).inc()
            for field_name in fields:
                fields[field_name]["valid"] = all(
                    err.field != field_name for err in validation.errors
                )
            DOCUMENT_PROCESSED.labels(extraction_result.document_type).inc()
            elapsed_ms = (time.perf_counter() - start) * 1000
            EXTRACTION_LATENCY.observe(elapsed_ms)

            response = {
                "request_id": request_id,
                "documents": [
                    {
                        "doc_type": extraction_result.document_type,
                        "fields": fields,
                        "validation_summary": {
                            "errors": [err.__dict__ for err in validation.errors],
                            "warnings": [warn.__dict__ for warn in validation.warnings],
                        },
                    }
                ],
                "metrics": {
                    "processing_time_ms": elapsed_ms,
                    "ocr_avg_confidence": ocr_result.metadata.get("avg_confidence", 0.0),
                },
                "analytics": {},
            }
            persist_run(response)
            response["analytics"]["top_failures"] = aggregate_failures()
            return response
