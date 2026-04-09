"""Heuristic field extractor.

A pure regex/keyword-based extractor that maps OCR text to a canonical schema
for invoices, simple tax forms, and ID documents. This module deliberately has
no ML dependencies; the previous LayoutLMv3/DocTR placeholder was removed in
the v0.2 refactor because it was never actually wired into the pipeline.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from idp.ocr.tesseract_engine import OCRResult

logger = logging.getLogger(__name__)


@dataclass
class FieldPrediction:
    name: str
    value: Optional[str]
    confidence: float
    source: str = "regex"
    extra: Dict = field(default_factory=dict)


@dataclass
class ExtractionResult:
    document_type: str
    fields: List[FieldPrediction]


# Patterns are intentionally permissive on capture; downstream validators
# enforce strict format. Confidence reflects how distinctive the surrounding
# anchor text is, not OCR confidence.
_PATTERNS: Dict[str, tuple[str, float]] = {
    "invoice_number": (r"invoice\s*(?:no\.?|number|#)\s*[:\-]?\s*([A-Za-z0-9\-]+)", 0.85),
    "invoice_date": (
        r"invoice\s*date\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
        0.8,
    ),
    "due_date": (
        r"due\s*date\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
        0.8,
    ),
    "subtotal_amount": (r"sub[\s\-]?total\s*[:\-]?\s*\$?\s*([0-9][0-9,]*\.?[0-9]*)", 0.8),
    "tax_amount": (r"\btax\s*(?:amount)?\s*[:\-]?\s*\$?\s*([0-9][0-9,]*\.?[0-9]*)", 0.75),
    "total_amount": (r"\btotal\s*(?:due|amount)?\s*[:\-]?\s*\$?\s*([0-9][0-9,]*\.?[0-9]*)", 0.85),
    "tax_id": (r"tax\s*(?:id|number)\s*[:\-]?\s*([0-9A-Za-z\-]{9,15})", 0.7),
    "routing_number": (r"routing\s*(?:no\.?|number)\s*[:\-]?\s*([0-9]{9})\b", 0.8),
    "bank_account": (r"account\s*(?:number|no\.?)\s*[:\-]?\s*([0-9]{6,20})\b", 0.7),
    "id_number": (r"id\s*(?:no\.?|number)\s*[:\-]?\s*([A-Za-z0-9\-]+)", 0.7),
    "expiry_date": (
        r"(?:expiry|expires?)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
        0.7,
    ),
    "birth_date": (
        r"(?:date\s*of\s*birth|dob|birth\s*date)\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4})",
        0.7,
    ),
}

_AMOUNT_FIELDS = {"subtotal_amount", "tax_amount", "total_amount"}
# Real ICAO MRZ lines are 30, 36, or 44 characters. The previous regex was
# hardcoded to 30, which silently dropped passport (44) and ID-1 (30) variants
# living on the same page.
_MRZ_LINE = re.compile(r"([A-Z0-9<]{30}|[A-Z0-9<]{36}|[A-Z0-9<]{44})")


class HeuristicExtractor:
    """Regex-based extractor producing FieldPrediction objects.

    The extractor takes OCR full text plus the structured token list and runs
    a small set of anchor-based regexes. It is intentionally simple so that the
    eval harness can attribute every error to a single rule.
    """

    def extract(self, ocr_result: OCRResult) -> ExtractionResult:
        text = ocr_result.full_text
        fields = self._regex_parse(text)
        fields.extend(self._mrz_parse(text))
        doc_type = self._infer_doc_type(text)
        return ExtractionResult(document_type=doc_type, fields=fields)

    def _regex_parse(self, text: str) -> List[FieldPrediction]:
        results: List[FieldPrediction] = []
        for name, (pattern, conf) in _PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip()
            if name in _AMOUNT_FIELDS:
                value = value.replace(",", "")
            results.append(FieldPrediction(name=name, value=value, confidence=conf))
        return results

    def _mrz_parse(self, text: str) -> List[FieldPrediction]:
        matches = _MRZ_LINE.findall(text)
        out: List[FieldPrediction] = []
        if matches:
            out.append(FieldPrediction(name="mrz_line1", value=matches[0], confidence=0.7))
        if len(matches) >= 2:
            out.append(FieldPrediction(name="mrz_line2", value=matches[1], confidence=0.7))
        return out

    def _infer_doc_type(self, text: str) -> str:
        lowered = text.lower()
        if "invoice" in lowered:
            return "invoice"
        if "passport" in lowered or "identification" in lowered or _MRZ_LINE.search(text):
            return "id_card"
        if "form" in lowered or "irs" in lowered or "1040" in lowered:
            return "tax_form"
        return "unknown"
