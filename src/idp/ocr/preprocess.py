from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

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


def convert_pdf_to_images(pdf_path: Path, config: PreprocessConfig) -> List[Path]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        pil_images = convert_from_path(str(pdf_path), dpi=config.dpi)
        image_paths: List[Path] = []
        for idx, img in enumerate(pil_images):
            if config.max_pages and idx >= config.max_pages:
                break
            out_path = Path(tmp_dir) / f"page_{idx}.png"
            img.save(out_path, format="PNG")
            processed = preprocess_image(out_path, config)
            image_paths.append(processed)
        # convert_from_path temp dir deleted here, so copy files elsewhere
        final_paths: List[Path] = []
        for path in image_paths:
            new_path = pdf_path.parent / f"{pdf_path.stem}_page{len(final_paths)}.png"
            new_path.write_bytes(Path(path).read_bytes())
            final_paths.append(new_path)
        return final_paths


def preprocess_image(image_path: Path, config: PreprocessConfig) -> Path:
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
    (h, w) = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def checksum(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def preprocess_pdf(pdf_path: Path, config: PreprocessConfig | None = None) -> PreprocessResult:
    cfg = config or PreprocessConfig()
    pages = convert_from_path(str(pdf_path), dpi=cfg.dpi)
    image_paths: List[Path] = []
    for idx, img in enumerate(pages):
        if cfg.max_pages and idx >= cfg.max_pages:
            break
        tmp = Path(tempfile.mkstemp(suffix=".png")[1])
        img.save(tmp, format="PNG")
        processed = preprocess_image(tmp, cfg)
        image_paths.append(processed)
    meta = {"page_count": len(image_paths), "checksum": checksum(image_paths)}
    return PreprocessResult(images=image_paths, metadata=meta)
