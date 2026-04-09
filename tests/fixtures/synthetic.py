"""Synthetic invoice generator used by tests and the eval harness.

We render a fixed-layout invoice (or ID document) to a PNG using PIL with a
known font. Each generated sample comes paired with the ground-truth field
values so that downstream OCR + extraction can be scored deterministically.

Generating images instead of real PDFs lets us:
  * exercise Tesseract on realistic monospaced text without needing a PDF lib;
  * keep CI hermetic — no fixtures in git, everything is rebuilt on demand;
  * vary noise/skew/font-size to stress preprocessing.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont


@dataclass
class SyntheticSample:
    image_path: Path
    doc_type: str
    ground_truth: Dict[str, str]
    notes: List[str] = field(default_factory=list)


_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",  # macOS
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",  # Debian/Ubuntu
    "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # Last-resort default font is bitmap and produces poor OCR; we accept that
    # in environments without any TrueType font installed.
    return ImageFont.load_default()


def _render_lines(lines: List[str], out_path: Path, font_size: int = 28) -> Path:
    font = _load_font(font_size)
    width = 1100
    line_height = int(font_size * 1.6)
    height = line_height * (len(lines) + 4)
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    y = line_height
    for line in lines:
        draw.text((60, y), line, fill=0, font=font)
        y += line_height
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def make_invoice(out_path: Path, seed: int = 0) -> SyntheticSample:
    rng = random.Random(seed)
    invoice_no = f"INV-{10000 + rng.randint(0, 89999)}"
    subtotal = round(rng.uniform(100, 5000), 2)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    invoice_date = f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    due_date = f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    tax_id = f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}"
    routing = f"{rng.randint(100000000, 999999999)}"
    account = f"{rng.randint(10**9, 10**10 - 1)}"

    lines = [
        "ACME WIDGETS INC.",
        "123 Industrial Way, Springfield",
        "",
        f"Invoice Number: {invoice_no}",
        f"Invoice Date: {invoice_date}",
        f"Due Date: {due_date}",
        "",
        "Description           Qty   Price",
        "Widget A               10   50.00",
        "Widget B                5  120.00",
        "",
        f"Subtotal: ${subtotal:.2f}",
        f"Tax: ${tax:.2f}",
        f"Total: ${total:.2f}",
        "",
        f"Tax ID: {tax_id}",
        f"Routing Number: {routing}",
        f"Account Number: {account}",
    ]
    _render_lines(lines, out_path)

    return SyntheticSample(
        image_path=out_path,
        doc_type="invoice",
        ground_truth={
            "invoice_number": invoice_no,
            "invoice_date": invoice_date,
            "due_date": due_date,
            "subtotal_amount": f"{subtotal:.2f}",
            "tax_amount": f"{tax:.2f}",
            "total_amount": f"{total:.2f}",
            "tax_id": tax_id,
            "routing_number": routing,
            "bank_account": account,
        },
    )


def make_id_card(out_path: Path, seed: int = 0) -> SyntheticSample:
    rng = random.Random(seed)
    id_number = f"ID-{rng.randint(100000, 999999)}"
    birth = f"1990-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    expiry = f"2030-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
    lines = [
        "REPUBLIC OF EXAMPLE - IDENTIFICATION CARD",
        "",
        "Name: JOHN DOE",
        f"ID Number: {id_number}",
        f"Date of Birth: {birth}",
        f"Expiry: {expiry}",
        "",
        "P<EXAJOHN<DOE<<<<<<<<<<<<<<<<<",
        "L898902C36EXA9001011M3001019<",
    ]
    _render_lines(lines, out_path)
    return SyntheticSample(
        image_path=out_path,
        doc_type="id_card",
        ground_truth={
            "id_number": id_number,
            "birth_date": birth,
            "expiry_date": expiry,
        },
    )


def generate_dataset(out_dir: Path, n_invoices: int = 20, n_ids: int = 10) -> List[SyntheticSample]:
    out_dir.mkdir(parents=True, exist_ok=True)
    samples: List[SyntheticSample] = []
    for i in range(n_invoices):
        samples.append(make_invoice(out_dir / f"invoice_{i:03d}.png", seed=i))
    for i in range(n_ids):
        samples.append(make_id_card(out_dir / f"id_{i:03d}.png", seed=1000 + i))
    return samples
