from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pytesseract
from pytesseract import Output

from idp.config import get_settings


@dataclass
class OCRToken:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int]
    page_num: int


@dataclass
class OCRResult:
    tokens: List[OCRToken]
    full_text: str
    metadata: Dict


def run_tesseract(image_path: Path, lang: str | None = None) -> OCRResult:
    settings = get_settings()
    pytesseract.pytesseract.tesseract_cmd = settings.ocr.tesseract_cmd
    lang = lang or "+".join(settings.ocr.languages)
    data = pytesseract.image_to_data(str(image_path), lang=lang, output_type=Output.DICT)
    tokens: List[OCRToken] = []
    text_parts: List[str] = []
    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        if not word:
            continue
        conf = float(data["conf"][i]) / 100.0
        bbox = (
            int(data["left"][i]),
            int(data["top"][i]),
            int(data["left"][i] + data["width"][i]),
            int(data["top"][i] + data["height"][i]),
        )
        page_num = int(data.get("page_num", [1] * len(data["text"]))[i])
        tokens.append(OCRToken(text=word, confidence=conf, bbox=bbox, page_num=page_num))
        text_parts.append(word)
    metadata = {
        "avg_confidence": sum(t.confidence for t in tokens) / max(len(tokens), 1),
        "token_count": len(tokens),
    }
    return OCRResult(tokens=tokens, full_text=" ".join(text_parts), metadata=metadata)


def serialize_ocr_result(result: OCRResult, output_path: Path) -> None:
    payload = {
        "tokens": [
            {
                "text": t.text,
                "confidence": t.confidence,
                "bbox": t.bbox,
                "page_num": t.page_num,
            }
            for t in result.tokens
        ],
        "full_text": result.full_text,
        "metadata": result.metadata,
    }
    output_path.write_text(json.dumps(payload, indent=2))
