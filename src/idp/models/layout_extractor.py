from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

try:  # pragma: no cover - optional dependency
    from transformers import LayoutLMv3ImageProcessor, LayoutLMv3TokenizerFast, LayoutLMv3ForTokenClassification
    import torch
except Exception:  # pragma: no cover
    LayoutLMv3ImageProcessor = None
    LayoutLMv3TokenizerFast = None
    LayoutLMv3ForTokenClassification = None
    torch = None

try:  # pragma: no cover
    from doctr.models import ocr_predictor
except Exception:  # pragma: no cover
    ocr_predictor = None

from idp.config import get_settings
from idp.ocr.tesseract_engine import OCRResult

logger = logging.getLogger(__name__)


@dataclass
class FieldPrediction:
    name: str
    value: str | float | None
    confidence: float
    bbox: tuple[int, int, int, int] | None = None
    page_num: int = 1
    source: str = "heuristic"
    extra: Dict | None = field(default_factory=dict)


@dataclass
class LayoutExtractionResult:
    document_type: str
    fields: List[FieldPrediction]


class LayoutExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        if self.settings.layout.provider == "layoutlmv3" and LayoutLMv3ImageProcessor:
            self._init_layoutlmv3()
        elif self.settings.layout.provider == "doctr" and ocr_predictor:
            self._init_doctr()
        else:
            logger.warning("Falling back to heuristic extractor; optional model deps missing.")

    def _init_layoutlmv3(self) -> None:
        model_name = self.settings.layout.model_name
        if not torch:
            logger.warning("Torch missing; skipping LayoutLMv3 init.")
            return
        self.processor = LayoutLMv3ImageProcessor.from_pretrained(model_name)
        self.tokenizer = LayoutLMv3TokenizerFast.from_pretrained(model_name)
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_name)
        self.model.to(self.settings.layout.device)
        self.model.eval()
        logger.info("Loaded LayoutLMv3 model %s", model_name)

    def _init_doctr(self) -> None:
        self.model = ocr_predictor(pretrained=True)
        logger.info("Loaded DocTR OCR predictor")

    def extract(self, images: Iterable[Path], ocr_result: OCRResult) -> LayoutExtractionResult:
        text = ocr_result.full_text
        if self.model:
            logger.debug("Model-backed extraction placeholder engaged")
            # Full implementation would perform feature extraction and structured predictions.
            # In this template we still run heuristics on the OCR text as a fallback.
        fields = self._heuristic_parse(text)
        doc_type = self._infer_doc_type(text)
        return LayoutExtractionResult(document_type=doc_type, fields=fields)

    def _heuristic_parse(self, text: str) -> List[FieldPrediction]:
        patterns = {
            "invoice_number": r"invoice\s*(?:no\.?|number)[:\s]*([A-Za-z0-9-]+)",
            "total_amount": r"total\s*(?:due|amount)?[:\s]*([$€£]?\s?[0-9,.]+)",
            "tax_amount": r"tax(?:\samount)?[:\s]*([$€£]?\s?[0-9,.]+)",
            "subtotal_amount": r"subtotal[:\s]*([$€£]?\s?[0-9,.]+)",
            "invoice_date": r"invoice\s*date[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})",
            "due_date": r"due\s*date[:\s]*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})",
            "tax_id": r"tax\s*(?:id|number)[:\s]*([A-Za-z0-9-]+)",
            "routing_number": r"routing\s*(?:no\.?|number)[:\s]*([0-9]{9})",
            "bank_account": r"account\s*(?:number|no\.?)[:\s]*([0-9]{6,20})",
            "id_number": r"id\s*(?:no\.?|number)[:\s]*([A-Za-z0-9-]+)",
            "mrz_line1": r"([A-Z0-9<]{30})\n",
            "mrz_line2": r"\n([A-Z0-9<]{30})",
        }
        results: List[FieldPrediction] = []
        lowered = text.lower()
        for field, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if not match:
                continue
            value = match.group(1).strip()
            confidence = 0.6
            if field in {"total_amount", "tax_amount", "subtotal_amount"}:
                value = value.replace(",", "").replace("$", "").strip()
            results.append(FieldPrediction(name=field, value=value, confidence=confidence))
        name_match = re.search(r"(?:bill\s*to|customer)[:\s]*([A-Za-z\s]+)\n", text, re.IGNORECASE)
        if name_match:
            results.append(FieldPrediction(name="customer_name", value=name_match.group(1).strip(), confidence=0.55))
        vendor_match = re.search(r"(?:from|seller)[:\s]*([A-Za-z\s]+)\n", text, re.IGNORECASE)
        if vendor_match:
            results.append(FieldPrediction(name="vendor_name", value=vendor_match.group(1).strip(), confidence=0.55))
        return results

    def _infer_doc_type(self, text: str) -> str:
        lowered = text.lower()
        if "invoice" in lowered:
            return "invoice"
        if "form" in lowered or "irs" in lowered:
            return "tax_form"
        if "passport" in lowered or "identification" in lowered:
            return "id_card"
        return "unknown"
