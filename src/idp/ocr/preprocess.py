"""PDF → preprocessed page image conversion.

All intermediate files live inside a caller-managed `TemporaryDirectory`. The
previous implementation wrote PNGs into the user's upload directory and never
cleaned them up; the new version returns paths inside `work_dir` and lets the
caller decide when to delete them.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import cv2
import numpy as np
from pdf2image import convert_from_path


@dataclass
class PreprocessConfig:
    dpi: int = 300
    binarize: bool = True
    denoise: bool = True
    deskew: bool = True
    max_pages: int | None = None


@dataclass
class PreprocessResult:
    images: List[Path]
    metadata: dict


def preprocess_pdf(
    pdf_path: Path,
    work_dir: Path,
    config: PreprocessConfig | None = None,
) -> PreprocessResult:
    """Render every page of `pdf_path` to a preprocessed PNG inside `work_dir`."""
    cfg = config or PreprocessConfig()
    work_dir.mkdir(parents=True, exist_ok=True)
    pages = convert_from_path(str(pdf_path), dpi=cfg.dpi)

    image_paths: List[Path] = []
    for idx, pil_image in enumerate(pages):
        if cfg.max_pages is not None and idx >= cfg.max_pages:
            break
        out_path = work_dir / f"{pdf_path.stem}_page{idx}.png"
        pil_image.save(out_path, format="PNG")
        preprocess_image(out_path, cfg)
        image_paths.append(out_path)

    return PreprocessResult(
        images=image_paths,
        metadata={"page_count": len(image_paths), "checksum": checksum(image_paths)},
    )


def preprocess_image(image_path: Path, config: PreprocessConfig) -> Path:
    """In-place preprocess of a single PNG (grayscale → denoise → deskew → binarize)."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(image_path)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if config.denoise:
        gray = cv2.medianBlur(gray, 3)
    if config.deskew:
        gray = _deskew(gray)
    if config.binarize:
        gray = cv2.adaptiveThreshold(
            gray,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY,
            blockSize=31,
            C=5,
        )

    cv2.imwrite(str(image_path), gray)
    return image_path


def _deskew(gray: np.ndarray) -> np.ndarray:
    coords = np.column_stack(np.where(gray < 255))
    if coords.size == 0:
        return gray
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def checksum(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()
