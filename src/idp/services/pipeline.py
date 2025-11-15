from __future__ import annotations

import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from idp.config import get_settings
from idp.models.layout_extractor import LayoutExtractor
from idp.ocr.preprocess import PreprocessConfig, preprocess_pdf
from idp.ocr.tesseract_engine import OCRResult, OCRToken, run_tesseract
from idp.postprocess import validators
from idp.postprocess.analytics import aggregate_failures, persist_run
from idp.services.metrics import DOCUMENT_PROCESSED, EXTRACTION_LATENCY, VALIDATION_FAILURES
from idp.utils.logging import traced


class ExtractionPipeline:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.layout_extractor = LayoutExtractor()

    def _run_ocr(self, image_paths: List[Path]) -> OCRResult:
        tokens: List[OCRToken] = []
        full_text_parts: List[str] = []
        metadata = {"pages": len(image_paths)}
        for idx, image in enumerate(image_paths, start=1):
            page_result = run_tesseract(image)
            for token in page_result.tokens:
                token.page_num = idx
                tokens.append(token)
            full_text_parts.append(page_result.full_text)
        if tokens:
            metadata["avg_confidence"] = sum(t.confidence for t in tokens) / len(tokens)
        else:
            metadata["avg_confidence"] = 0.0
        return OCRResult(tokens=tokens, full_text="\n".join(full_text_parts), metadata=metadata)

    def extract(self, pdf_path: Path) -> Dict:
        request_id = str(uuid.uuid4())
        with traced("extraction") as span:
            start = time.perf_counter()
            preprocess_result = preprocess_pdf(pdf_path, PreprocessConfig(dpi=self.settings.ocr.dpi))
            ocr_result = self._run_ocr(preprocess_result.images)
            layout_result = self.layout_extractor.extract(preprocess_result.images, ocr_result)
            fields = {pred.name: {"value": pred.value, "confidence": pred.confidence} for pred in layout_result.fields}
            validation = validators.validate_fields({k: v.get("value") for k, v in fields.items()})
            for err in validation.errors:
                VALIDATION_FAILURES.labels(err.field).inc()
            for field_name in fields:
                fields[field_name]["valid"] = all(err.field != field_name for err in validation.errors)
            DOCUMENT_PROCESSED.labels(layout_result.document_type).inc()
            elapsed = (time.perf_counter() - start) * 1000
            EXTRACTION_LATENCY.observe(elapsed)
            response = {
                "request_id": request_id,
                "documents": [
                    {
                        "doc_type": layout_result.document_type,
                        "fields": fields,
                        "validation_summary": {
                            "errors": [err.__dict__ for err in validation.errors],
                            "warnings": [warn.__dict__ for warn in validation.warnings],
                        },
                    }
                ],
                "metrics": {
                    "processing_time_ms": elapsed,
                    "ocr_avg_confidence": ocr_result.metadata.get("avg_confidence", 0.0),
                },
                "analytics": {},
            }
            persist_run(response)
            response["analytics"]["top_failures"] = aggregate_failures()
            return response
