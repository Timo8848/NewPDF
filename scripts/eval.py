"""End-to-end evaluation harness.

Generates a synthetic dataset of invoices and ID cards with known ground truth,
runs the production pipeline (Tesseract OCR + heuristic extractor + validators)
on each sample, and reports per-field precision/recall/F1.

Run from repo root:

    python scripts/eval.py --n-invoices 20 --n-ids 10 --out reports/eval_results.json

The script writes:
  * reports/eval_results.json — full per-sample predictions + metrics
  * reports/eval_results.md   — human-readable summary table

This is the harness that backs every accuracy claim in the README.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List

# Make `tests` importable when running this script directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from idp.models.extractor import HeuristicExtractor  # noqa: E402
from idp.ocr.tesseract_engine import run_tesseract  # noqa: E402
from idp.postprocess import validators  # noqa: E402
from tests.fixtures.synthetic import SyntheticSample, generate_dataset  # noqa: E402


def _normalize(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(",", "")


def evaluate(samples: List[SyntheticSample]) -> Dict:
    extractor = HeuristicExtractor()
    per_field_tp: Dict[str, int] = defaultdict(int)
    per_field_fp: Dict[str, int] = defaultdict(int)
    per_field_fn: Dict[str, int] = defaultdict(int)
    sample_records: List[Dict] = []

    for sample in samples:
        ocr_result = run_tesseract(sample.image_path)
        extraction = extractor.extract(ocr_result)
        predicted = {p.name: p.value for p in extraction.fields}

        all_fields = set(sample.ground_truth) | set(predicted)
        record_fields: Dict[str, Dict] = {}
        for name in all_fields:
            gt = _normalize(sample.ground_truth.get(name))
            pred = _normalize(predicted.get(name))
            status: str
            if gt and pred and gt == pred:
                per_field_tp[name] += 1
                status = "tp"
            elif gt and pred and gt != pred:
                per_field_fp[name] += 1
                per_field_fn[name] += 1
                status = "wrong"
            elif gt and not pred:
                per_field_fn[name] += 1
                status = "missed"
            elif pred and not gt:
                per_field_fp[name] += 1
                status = "spurious"
            else:
                continue
            record_fields[name] = {"gt": gt, "pred": pred, "status": status}

        validation = validators.validate_fields(predicted)
        sample_records.append(
            {
                "image": str(sample.image_path),
                "doc_type_predicted": extraction.document_type,
                "doc_type_truth": sample.doc_type,
                "fields": record_fields,
                "validation_errors": [asdict(e) for e in validation.errors],
                "validation_warnings": [asdict(w) for w in validation.warnings],
            }
        )

    per_field_metrics: Dict[str, Dict] = {}
    total_tp = total_fp = total_fn = 0
    for name in sorted(set(per_field_tp) | set(per_field_fp) | set(per_field_fn)):
        tp = per_field_tp[name]
        fp = per_field_fp[name]
        fn = per_field_fn[name]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_field_metrics[name] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0.0

    return {
        "n_samples": len(samples),
        "per_field": per_field_metrics,
        "micro": {
            "precision": round(micro_p, 3),
            "recall": round(micro_r, 3),
            "f1": round(micro_f1, 3),
        },
        "samples": sample_records,
    }


def write_markdown(results: Dict, path: Path) -> None:
    lines = [
        "# Evaluation Results",
        "",
        f"Samples: **{results['n_samples']}**  ",
        f"Micro precision: **{results['micro']['precision']}**  ",
        f"Micro recall: **{results['micro']['recall']}**  ",
        f"Micro F1: **{results['micro']['f1']}**",
        "",
        "## Per-field metrics",
        "",
        "| Field | TP | FP | FN | Precision | Recall | F1 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in results["per_field"].items():
        lines.append(
            f"| {name} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']} | {m['recall']} | {m['f1']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-invoices", type=int, default=20)
    parser.add_argument("--n-ids", type=int, default=10)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "eval_results.json")
    parser.add_argument("--md", type=Path, default=ROOT / "reports" / "eval_results.md")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="idp_eval_") as tmp:
        samples = generate_dataset(Path(tmp), n_invoices=args.n_invoices, n_ids=args.n_ids)
        results = evaluate(samples)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2, default=str))
    write_markdown(results, args.md)
    print(f"Wrote {args.out} and {args.md}")
    print(json.dumps(results["micro"], indent=2))


if __name__ == "__main__":
    main()
